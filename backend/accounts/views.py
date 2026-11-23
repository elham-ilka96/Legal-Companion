import hashlib
import time
import secrets
import os
import json
import re
import requests
import httpx
from google import genai
from google.genai import types

from rest_framework import serializers
from django.conf import settings
from datetime import timedelta
from django.db import models
from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse, HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import close_old_connections

from .models import (
    UserProfile, LegalCase, VerificationCode, AuthSession, VerificationRateLimit,
    Note, Document, AIProcessingRun, Case, LegalStory, LegalStoryCaseLink,
    DocumentCaseLink, Person, CaseParticipant, DocumentExtractedFact, Notice,
)

from .serializers import (
    UserProfileSerializer, LegalCaseSerializer, NoteSerializer, LegalStorySerializer,
)

from django.core.files.storage import default_storage
from .paperless_service import upload_document, get_task_status, search_documents
from .prompts import (
    build_document_analysis_prompt,
    build_case_summary_prompt,
    build_story_summary_prompt,
)

def _is_gemini_overloaded(exc):
    """آیا خطا از شلوغی یا محدودیت موقت سرویس Gemini است؟"""
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (429, 503):
        return True
    text = str(exc)
    return "UNAVAILABLE" in text or "503" in text or "RESOURCE_EXHAUSTED" in text


def create_gemini_client():
    """ساخت کلاینت Gemini با دریافت کلید و پراکسی از متغیرهای محیطی."""
    api_key = os.getenv("GEMINI_API_KEY")
    proxy_url = os.getenv("GEMINI_PROXY", "").strip()

    if not api_key:
        raise ValueError("متغیر GEMINI_API_KEY در فایل محیطی تنظیم نشده است.")

    retry_options = types.HttpRetryOptions(
        attempts=5,
        initial_delay=2.0,
        max_delay=30.0,
    )

    http_options = types.HttpOptions(
        client_args={'proxy': proxy_url} if proxy_url else {},
        retry_options=retry_options,
    )

    return genai.Client(
        api_key=api_key,
        http_options=http_options,
    )


def _generate_gemini_text(gemini_client, prompt, model, temperature=0.2, max_tokens=4096):
    """ارسال پرامپت متنی به Gemini و برگرداندن پاسخ پاک‌سازی‌شده."""
    response = gemini_client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    response_text = (response.text or "").strip()
    if not response_text:
        raise ValueError("Gemini پاسخ متنی برنگرداند.")

    try:
        reason = str(response.candidates[0].finish_reason)
    except Exception:
        reason = ""
    if "MAX_TOKENS" in reason:
        raise ValueError(f"خروجی Gemini ناقص ماند (model={model})")

    # اگر متن انگلیسی (فکر کردن مدل) قاطی خروجی شد، قبول نکن
    if len(re.findall(r"[A-Za-z]{3,}", response_text)) > 5:
        raise ValueError(f"خروجی Gemini انگلیسی/نامعتبر بود (model={model})")

    return response_text


def _model_candidates(primary):
    """مدل اصلی + مدل‌های MODEL_FALLBACKS (بدون تکرار)."""
    env_models = os.getenv("MODEL_FALLBACKS", "")
    names = [primary] + [m.strip() for m in env_models.split(",") if m.strip()]
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _generate_gemini_text_with_fallback(gemini_client, prompt, primary_model, temperature=0.2):
    """اگر یک مدل خطا داد (۵۰۳، ۴۰۴ و ...) سراغ مدل بعدی می‌رود."""
    last_exc = None
    for name in _model_candidates(primary_model):
        try:
            return _generate_gemini_text(gemini_client, prompt, name, temperature=temperature)
        except Exception as e:
            print(f"⚠️ مدل {name} برای خلاصه خطا داد: {e}")
            last_exc = e
    raise last_exc or Exception("هیچ مدلی پاسخ نداد.")


def _clip_at_sentence(text, limit=400):
    """متن را بدون بریدن وسط کلمه یا جمله کوتاه می‌کند."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    idx = max(cut.rfind("."), cut.rfind("؟"), cut.rfind("!"))
    if idx > 80:
        return cut[:idx + 1]
    return cut.rsplit(" ", 1)[0] + "…"

def _shorten_story_title(topic, max_words=3):
    """فقط برای عنوان داستان: حداکثر ۳ کلمه، بدون پیشوند و شماره."""
    if not topic:
        return "پرونده حقوقی"

    topic = re.sub(r"\s+", " ", topic).strip()
    topic = re.sub(
        r"^(?:پرونده(?:\s+حقوقی)?|دعوای|دعوا|موضوع|در\s+خصوص|در\s+مورد)\s+",
        "", topic
    ).strip()
    topic = re.sub(r"\s*[\(\[]?\s*[0-9۰-۹/\-_\.]+\s*[\)\]]?\s*$", "", topic).strip()

    words = topic.split()
    if len(words) > max_words:
        topic = " ".join(words[:max_words])

    topic = re.sub(r"[،,\.]+$", "", topic).strip()
    return topic or "پرونده حقوقی"


def _jalali_to_gregorian(jy, jm, jd):
    """تبدیل تاریخ شمسی به میلادی؛ خروجی (سال، ماه، روز) میلادی."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    months = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return gy, gm, gd


def _is_hearing_past(hearing_date_str):
    """آیا تاریخ جلسه (شمسی یا میلادی) گذشته است؟"""
    from datetime import date
    if not hearing_date_str or hearing_date_str in ("تعیین نشده", "نامشخص"):
        return False
    try:
        digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        clean = str(hearing_date_str).translate(digits).replace("-", "/").strip()
        parts = clean.split("/")
        if len(parts) != 3:
            return False
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if y < 100:
            y += 1400
        if y < 1700:  # سال شمسی
            y, m, d = _jalali_to_gregorian(y, m, d)
        return date(y, m, d) < timezone.localdate()
    except Exception:
        return False


# =========================================================
# توابع کمکی
# =========================================================

def validate_mobile(mobile):
    return (
        isinstance(mobile, str)
        and len(mobile) == 11
        and mobile.startswith("09")
        and mobile.isdigit()
    )


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def get_session(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return None
    token_hash = hash_token(token)
    return AuthSession.objects.filter(
        token_hash=token_hash,
        expires_at__gt=timezone.now()
    ).first()


def create_session(mobile, mode):
    token = secrets.token_hex(32)
    AuthSession.objects.create(
        token_hash=hash_token(token),
        mobile=mobile,
        mode=mode,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return token


def _clean_summary_text(raw_summary, filename):
    text = raw_summary
    if filename and filename != "سند بدون نام":
        fname_pattern = re.escape(os.path.splitext(filename)[0])
        text = re.sub(
            rf"^(?:این\s+)?(?:سند\s+|فایل\s+|تصویر\s+)?{fname_pattern}\s*(?:[-،:٫]|\s+است)?\s*",
            "", text, flags=re.IGNORECASE
        ).strip()
    text = re.sub(r'(?:با\s+)?وکالت(?:\s+آقای|\s+خانم)?\s+[آ-ی\u200c]+\s+[آ-ی\u200c]+', '', text)
    text = re.sub(r'(?:با\s+)?وکیل(?:\s+آقای|\s+خانم)?\s+[آ-ی\u200c]+\s+[آ-ی\u200c]+', '', text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[،\.\s]+", "", text)
    max_chars = 400
    if len(text) > max_chars:
        truncated = text[:max_chars]
        last_dot = truncated.rfind('.')
        text = truncated[:last_dot + 1] if last_dot > 100 else truncated + "..."
    return text


def _check_topic_similarity(topic1, topic2):
    if not topic1 or not topic2:
        return False
    if topic1 == topic2:
        return True
    stop_words = ["پرونده", "حقوقی", "درباره", "مربوط", "به", "در", "و", "با", "از"]
    w1 = set([w for w in topic1.split() if w not in stop_words and len(w) > 2])
    w2 = set([w for w in topic2.split() if w not in stop_words and len(w) > 2])
    if not w1 or not w2:
        return False
    return len(w1.intersection(w2)) > 0


# =========================================================
# توابع کمکی: کنترل اسم‌ها
# =========================================================

def _split_name_parts(name_str):
    if not name_str or name_str == "نامشخص":
        return []
    parts = re.split(r"\s+و\s+|،|,|/", name_str)
    return [p.strip() for p in parts if p.strip() and p.strip() != "نامشخص"]


def _strip_honorifics(name):
    if not name:
        return name
    return re.sub(
        r"^(?:حاج\s*آقا|حاج\s*خانم|حاجی|جناب\s*آقای|جناب\s*خانم|جناب|سرکار|آقای|خانم|آقا|خانوم|مهندس|دکتر)\s+",
        "", name
    ).strip()


def _normalize_single_name(name_str):
    if not name_str or name_str == "نامشخص":
        return name_str
    parts = _split_name_parts(name_str)
    if not parts:
        return name_str
    return _strip_honorifics(parts[0])


def _normalize_name_for_matching(name):
    if not name:
        return ""
    name = _strip_honorifics(name)
    name = re.sub(r"\s*فرزند\s+[^\s،\.]+", "", name)
    name = re.sub(r"\([^)]*\)", "", name)
    name = name.replace("\u200c", " ").replace("\u200f", " ").replace("\u200e", " ")
    name = name.replace("ي", "ی").replace("ك", "ک").replace("\u0640", "")
    name = name.replace("ئ", "ی")
    return re.sub(r"\s+", " ", name).strip()


def _names_match(n1, n2):
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    c1 = n1.replace(" ", "")
    c2 = n2.replace(" ", "")
    if c1 == c2:
        return True
    if len(c1) >= 3 and len(c2) >= 3:
        if c1.startswith(c2) or c2.startswith(c1):
            return True
    if len(c1) >= 4 and c1 in c2:
        return True
    if len(c2) >= 4 and c2 in c1:
        return True
    return False


def _replace_name_with_role(text, name_str, role):
    if not text or not name_str:
        return text

    words = name_str.split()
    if not words:
        return text

    if len(name_str) >= 3 and name_str in text:
        text = text.replace(name_str, role)

    first = words[0]
    if first and len(first) >= 2:
        pattern = (
            rf"(?<![آ-ی\u200c]){re.escape(first)}"
            rf"(?:\s+[آ-ی\u200c]{{3,}}){{0,2}}"
            rf"(?![آ-ی\u200c])"
        )
        text = re.sub(pattern, role, text)

    if len(words) >= 2:
        last = words[-1]
        if last and len(last) >= 3 and last != first and last in text:
            text = text.replace(last, role)

    return text


def _get_all_known_names(user):
    if not user:
        return []
    raw_names = list(Person.objects.filter(user=user).values_list("display_name", flat=True))
    result = set()
    for raw in raw_names:
        if not raw:
            continue
        parts = _split_name_parts(raw)
        if parts:
            for p in parts:
                if not p:
                    continue
                result.add(p)
                p_clean = _strip_honorifics(p)
                if p_clean and p_clean != p and len(p_clean) >= 3:
                    result.add(p_clean)
                if p_clean and " " in p_clean:
                    ws = p_clean.split(" ")
                    fw = ws[0]
                    lw = ws[-1]
                    if len(fw) >= 3:
                        result.add(fw)
                    if len(lw) >= 3 and lw != fw:
                        result.add(lw)
        else:
            result.add(raw)
    return list(result)


def _strip_identifiers(text):
    if not text:
        return text
    id_kw = r"(?:پرونده|دادنامه|کلاسه|کلاس|بایگانی|سند|رای|قرار|دادخواست|ابلاغیه|شعبه)"
    value = r"(?:[\d۰-۹/\-_\.]+|نامشخص|نامعلوم|ندارد)"
    patterns = [
        rf"شماره\s*{id_kw}\s*[:：]?\s*{value}",
        rf"کلاس(?:ه)?\s*(?:{id_kw})?\s*[:：]?\s*{value}",
        rf"پرونده\s*شماره\s*[:：]?\s*{value}",
        rf"شماره\s*[:：]\s*{value}",
        rf"((?:شماره|کلاس(?:ه)?)\s*(?:{id_kw})?)\s*$",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^[،,\.\s]+", "", text)
    text = re.sub(r"[،,]\s*[،,]", "،", text)
    text = re.sub(r"\s+([،,\.])", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_case_by_parties(user, plaintiff_name, defendant_name, exclude_id=None):
    if not user:
        return None

    p_norm = _normalize_name_for_matching(plaintiff_name) if plaintiff_name and plaintiff_name != "نامشخص" else ""
    d_norm = _normalize_name_for_matching(defendant_name) if defendant_name and defendant_name != "نامشخص" else ""
    
    if not p_norm and not d_norm:
        return None

    qs = Case.objects.filter(user=user).prefetch_related("participants__person")
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    for c in qs:
        c_p, c_d = [], []
        for part in c.participants.all():
            nm = _normalize_name_for_matching(part.person.display_name or "")
            if not nm:
                continue
            if part.role == "خواهان":
                c_p.append(nm)
            elif part.role == "خوانده":
                c_d.append(nm)
        
        p_match = any(_names_match(p_norm, x) for x in c_p) if p_norm else False
        d_match = any(_names_match(d_norm, x) for x in c_d) if d_norm else False
        
        if p_match or d_match:
            if (p_norm and d_norm) and (p_match and d_match):
                return c
            elif (p_norm and p_match) or (d_norm and d_match):
                return c
                
    return None


def _strict_name_key(name):
    """
    کلید دقیق نام برای تطبیق داستان‌ها.
    - نام باید حداقل دو کلمه (نام + نام خانوادگی) باشد، وگرنه کلید خالی برمی‌گردد.
    - فاصله و نیم‌فاصله نادیده گرفته می‌شود ولی تطبیق کاملاً دقیق است (نه startswith، نه in).
    """
    if not name or name == "نامشخص":
        return ""
    norm = _normalize_name_for_matching(name)
    if len(norm.split()) < 2:
        return ""
    return norm.replace(" ", "")


def _case_strict_name_keys(case):
    """کلید دقیق نام همه‌ی طرف‌های پرونده، بدون توجه به نقش."""
    keys = set()
    for part in case.participants.all():
        k = _strict_name_key(part.person.display_name or "")
        if k:
            keys.add(k)
    return keys


def _normalize_case_number(num):
    """یکسان‌سازی قالب شماره پرونده برای تطبیق (ارقام فارسی/عربی، فاصله، خط‌تیره)."""
    if not num or num == "نامشخص":
        return num
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    s = str(num).translate(digits)
    s = re.sub(r"\s+", "", s)
    s = s.replace("_", "/").replace(".", "/").replace("-", "/")
    s = re.sub(r"/+", "/", s).strip("/")
    return s


def _topic_similarity_percent(t1, t2):
    """درصد شباهت موضوعی بین دو رشته (۰ تا ۱۰۰) با ضریب همپوشانی."""
    if not t1 or not t2:
        return 0.0

    stop_words = {
        "پرونده", "حقوقی", "درباره", "مربوط", "به", "در", "و", "با", "از",
        "که", "این", "آن", "یک", "را", "برای", "تا", "هم", "یا", "اما",
        "شده", "شدن", "است", "بود", "می", "شود",
    }

    def tokens(text):
        text = re.sub(r"[^آ-ی\u200c\w\s]", " ", str(text or ""))
        return {w for w in text.split() if w not in stop_words and len(w) > 2}

    w1, w2 = tokens(t1), tokens(t2)
    if not w1 or not w2:
        return 0.0

    common = w1 & w2
    if not common:
        return 0.0

    # overlap coefficient — سخاوتمندانه‌تر از Jaccard
    return len(common) / min(len(w1), len(w2)) * 100.0


def _find_story_for_case(user, plaintiff_name, defendant_name, topic, exclude_case_id=None):
    """
    پیدا کردن داستانِ متناسب برای یک پرونده‌ی جدید.

    معیارها (هر کدام برقرار بود → همان داستان):
      ۱) تطابق نام هر یک از طرفین (بدون توجه به نقش) — حتی با جابجایی خواهان/خوانده
      ۲) شباهت موضوعی ≥ ۵۰ درصد

    در غیر این صورت، None برمی‌گردد (باید داستان جدید ساخته شود).
    """
    if not user:
        return None

    p_key = _strict_name_key(plaintiff_name) if plaintiff_name and plaintiff_name != "نامشخص" else ""
    d_key = _strict_name_key(defendant_name) if defendant_name and defendant_name != "نامشخص" else ""
    wanted_keys = {k for k in (p_key, d_key) if k}

    stories = LegalStory.objects.filter(user=user).prefetch_related(
        "case_links__case__participants__person"
    )

    best_story = None
    best_topic_score = 0.0

    for story in stories:
        # ۱) تطابق نام — هر طرفی، هر نقشی، هر ترتیبی
        for link in story.case_links.all():
            case = link.case
            if exclude_case_id and case.id == exclude_case_id:
                continue
            if wanted_keys and (wanted_keys & _case_strict_name_keys(case)):
                print(f"[story-match] NAME MATCH: case={case.id} → story={story.id}")
                return story

        # ۲) شباهت موضوعی
        if topic:
            for link in story.case_links.all():
                case = link.case
                if exclude_case_id and case.id == exclude_case_id:
                    continue
                case_topic = (case.case_type or "").strip()
                if not case_topic and case.title:
                    case_topic = case.title.replace("پرونده", "").strip()
                sim = _topic_similarity_percent(topic, case_topic)
                if sim > best_topic_score:
                    best_topic_score = sim
                    best_story = story

    if best_story and best_topic_score >= 50.0:
        print(f"[story-match] TOPIC MATCH: score={best_topic_score:.1f}% → story={best_story.id}")
        return best_story

    return None


def _strip_parenthetical_placeholders(text, user=None):
    if not text:
        return text

    text = re.sub(
        r"\(\s*(?:شما|طرف\s*مقابل|خواهان|خوانده|مدعی|مدعی‌علیه|مدعی علیه)\s*\)",
        "", text
    )

    if user:
        for name in sorted(_get_all_known_names(user), key=len, reverse=True):
            if not name or len(name) < 3:
                continue
            text = re.sub(rf"\(\s*{re.escape(name)}\s*\)", "", text)

    safe_keywords = [
        'دادگاه', 'شعبه', 'پرونده', 'دادنامه', 'شماره', 'تاریخ', 'مبلغ',
        'ریال', 'تومان', 'قرار', 'حکم', 'دادخواست', 'ابلاغیه',
        'نوع', 'ماده', 'تبصره', 'قانون', 'اصل', 'بخش', 'فصل',
        'کارشناس', 'نظریه', 'کارشناسی', 'خواهان', 'خوانده',
    ]

    def should_strip(match):
        content = match.group(1).strip()
        if not content:
            return True
        if re.search(r'[0-9۰-۹]', content):
            return False
        for kw in safe_keywords:
            if kw in content:
                return False
        words = content.split()
        if 1 <= len(words) <= 5 and all(re.match(r'^[آ-ی‌]+$', w) for w in words):
            return True
        return False

    text = re.sub(r"\(([^)]*)\)", lambda m: "" if should_strip(m) else m.group(0), text)

    text = re.sub(r"(شما|طرف\s*مقابل)\s*\(\s*(?:شما|طرف\s*مقابل)\s*\)", r"\1", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+([،,\.])", r"\1", text)
    text = re.sub(r"[،,]\s*[،,]", "،", text)
    return re.sub(r"\s+", " ", text).strip()


def _postprocess_summary_names(summary_text, plaintiff_str, defendant_str, user):
    """
    اسم‌ها عمداً حذف یا جایگزین نمی‌شوند (طبق خواسته‌ی محصول).
    فقط شناسه‌ها (شماره پرونده و ...) پاک و کلمات تکراری یکی می‌شوند.
    """
    if not summary_text:
        return summary_text

    summary_text = re.sub(r"(طرف\s*پرونده\s*){2,}", "طرف پرونده ", summary_text)
    summary_text = re.sub(r"(خواهان\s*){2,}", "خواهان ", summary_text)
    summary_text = re.sub(r"(خوانده\s*){2,}", "خوانده ", summary_text)
    summary_text = re.sub(r"(شما\s*){2,}", "شما ", summary_text)

    return _strip_identifiers(summary_text)


def _prune_summaries_input(summaries, plaintiff_str, defendant_str, user):
    if not user:
        return summaries

    primary_plaintiff = _normalize_single_name(plaintiff_str)
    primary_defendant = _normalize_single_name(defendant_str)
    allowed = set()
    if primary_plaintiff and primary_plaintiff != "نامشخص":
        allowed.add(primary_plaintiff)
    if primary_defendant and primary_defendant != "نامشخص":
        allowed.add(primary_defendant)

    plaintiff_parts = set(_split_name_parts(plaintiff_str))
    defendant_parts = set(_split_name_parts(defendant_str))

    result = []
    for s in summaries:
        for name in _get_all_known_names(user):
            if not name or name in allowed or name not in s:
                continue
            if name in plaintiff_parts:
                s = s.replace(name, "خواهان")
            elif name in defendant_parts:
                s = s.replace(name, "خوانده")
            else:
                s = s.replace(name, "طرف پرونده")
        result.append(s)
    return result


def _redact_all_names_for_story(text, user, plaintiff_str=None, defendant_str=None):
    if not text:
        return text

    if user:
        plaintiff_parts = _split_name_parts(plaintiff_str) if plaintiff_str else []
        defendant_parts = _split_name_parts(defendant_str) if defendant_str else []

        for part in plaintiff_parts:
            text = _replace_name_with_role(text, part, "شما")

        for part in defendant_parts:
            text = _replace_name_with_role(text, part, "طرف مقابل")

        all_names = sorted(_get_all_known_names(user), key=len, reverse=True)
        for name in all_names:
            if not name:
                continue
            is_plaintiff = False
            is_defendant = False
            for p in plaintiff_parts:
                if _names_match(_normalize_name_for_matching(name),
                                _normalize_name_for_matching(p)):
                    is_plaintiff = True
                    break
            if not is_plaintiff:
                for d in defendant_parts:
                    if _names_match(_normalize_name_for_matching(name),
                                    _normalize_name_for_matching(d)):
                        is_defendant = True
                        break

            if is_plaintiff:
                text = _replace_name_with_role(text, name, "شما")
            elif is_defendant:
                text = _replace_name_with_role(text, name, "طرف مقابل")
            else:
                text = _replace_name_with_role(text, name, "طرف پرونده")

        text = re.sub(r"(علیه|شکایت\s+از|شکایت\s+علیه|طرف|خوانده|خواهان)\s+(?:و\s+)?[آ-ی\u200c]{3,}(?:\s+[آ-ی\u200c]{3,})?", r"\1", text)

        text = re.sub(
            r"(?:حاج\s*آقا|حاج\s*خانم|جناب\s*آقای|جناب\s*خانم|آقای|خانم|جناب|سرکار|آقا|خانوم)\s+"
            r"(?=(?:شما|طرف\s*مقابل))",
            "", text
        )

    text = re.sub(r"شما\s+و\s+شما", "شما", text)
    text = re.sub(r"طرف\s*مقابل\s+و\s+طرف\s*مقابل", "طرف مقابل", text)
    text = re.sub(r"شما\s+و\s+طرف\s*مقابل\s+و\s+شما", "شما و طرف مقابل", text)
    text = re.sub(r"طرف\s*مقابل\s+و\s+شما\s+و\s+طرف\s*مقابل", "شما و طرف مقابل", text)
    text = re.sub(r"[،,]\s*[،,]", "،", text)
    text = re.sub(r"^\s*[،,\.]+\s*", "", text)
    text = re.sub(r"\s+([،,\.])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    text = _strip_parenthetical_placeholders(text, user=user)

    return _strip_identifiers(text)


def _final_cleanup_story(text, user, plaintiff_str=None, defendant_str=None):
    if not text:
        return text
        
    text = re.sub(r"(?:خواهان|خوانده|طرف پرونده|شما|طرف مقابل)\s+[آ-ی\u200c]{3,}\s+[آ-ی\u200c]{3,}", lambda m: m.group(0).split()[0], text)
    text = re.sub(r"(?:خواهان|خوانده|طرف پرونده|شما|طرف مقابل)\s+[آ-ی\u200c]{4,}", lambda m: m.group(0).split()[0], text)

    if user:
        all_names = sorted(_get_all_known_names(user), key=len, reverse=True)
        plaintiff_parts = _split_name_parts(plaintiff_str) if plaintiff_str else []
        defendant_parts = _split_name_parts(defendant_str) if defendant_str else []

        for name in all_names:
            if not name or len(name) < 3 or name not in text:
                continue

            is_plaintiff = any(
                _names_match(_normalize_name_for_matching(name), _normalize_name_for_matching(p))
                for p in plaintiff_parts
            )
            is_defendant = any(
                _names_match(_normalize_name_for_matching(name), _normalize_name_for_matching(d))
                for d in defendant_parts
            )

            if is_plaintiff:
                text = text.replace(name, "شما")
            elif is_defendant:
                text = text.replace(name, "طرف مقابل")
            else:
                text = text.replace(name, "طرف پرونده")

    text = re.sub(r"(?:شما\s+){2,}", "شما ", text)
    text = re.sub(r"(?:طرف\s*مقابل\s+){2,}", "طرف مقابل ", text)
    text = re.sub(r"(?:طرف\s*پرونده\s+){2,}", "طرف پرونده ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# =========================================================
# خلاصه پرونده (سطح ۲)
# =========================================================

def _generate_case_summary(doc_summaries_list, gemini_client, gemini_model,
                           user=None, plaintiff_str=None, defendant_str=None):
    if not doc_summaries_list:
        return "خلاصه‌ای ثبت نشده است."

    p_name = plaintiff_str if plaintiff_str and plaintiff_str != "نامشخص" else "نامشخص"
    d_name = defendant_str if defendant_str and defendant_str != "نامشخص" else "نامشخص"

    doc_summaries_list = [_strip_identifiers(s) for s in doc_summaries_list]

    if len(doc_summaries_list) == 1:
        single = doc_summaries_list[0]
        if user:
            single = _postprocess_summary_names(single, plaintiff_str, defendant_str, user)
        else:
            single = _strip_identifiers(single)
        return single

    combined_text = "\n- ".join(doc_summaries_list)
    
    prompt = build_case_summary_prompt(doc_summaries_list, plaintiff_str, defendant_str)

    try:
        raw_summary = _generate_gemini_text_with_fallback(
            gemini_client, prompt, gemini_model, temperature=0.15
        )
        raw_summary = re.sub(r"^(?:\*\*)?\s*خلاصه\s*(?:پرونده)?\s*[:：]?\s*", "", raw_summary)
        raw_summary = re.sub(r"(?:آقای|خانم|به\s+نام|تحت\s+عنوان)\s+", "", raw_summary)
        raw_summary = re.sub(r"[،,]\s*[،,]", "،", raw_summary)
        raw_summary = re.sub(r"\s+", " ", raw_summary).strip()

        if user:
            raw_summary = _postprocess_summary_names(
                raw_summary, plaintiff_str, defendant_str, user
            )
        else:
            raw_summary = _strip_identifiers(raw_summary)
        return raw_summary
    except Exception as e:
        print("خطا در تولید خلاصه پرونده:", e)
        fallback = _clip_at_sentence(" ".join(doc_summaries_list), 400)
        if user:
            fallback = _postprocess_summary_names(
                fallback, plaintiff_str, defendant_str, user
            )
        else:
            fallback = _strip_identifiers(fallback)
        return fallback


# =========================================================
# خلاصه داستان (سطح ۳)
# =========================================================

def _generate_story_summary(case_summaries_list, gemini_client, gemini_model,
                            user=None, plaintiff_str=None, defendant_str=None):
    if not case_summaries_list:
        return "خلاصه‌ای ثبت نشده است."

    case_summaries_list = [_strip_identifiers(s) for s in case_summaries_list]

    if len(case_summaries_list) == 1:
        return case_summaries_list[0]

    combined_text = "\n- ".join(case_summaries_list)
    prompt = build_story_summary_prompt(case_summaries_list)

    try:
        raw_story = _generate_gemini_text_with_fallback(
            gemini_client, prompt, gemini_model, temperature=0.2
        )
        raw_story = re.sub(r"^(?:\*\*)?\s*خلاصه\s*(?:داستان)?\s*[:：]?\s*", "", raw_story)
        raw_story = re.sub(r"[،,]\s*[،,]", "،", raw_story)
        raw_story = re.sub(r"\s+", " ", raw_story).strip()
        return _strip_identifiers(raw_story)
    except Exception as e:
        print("خطا در تولید خلاصه داستان:", e)
        return _strip_identifiers(_clip_at_sentence(" ".join(case_summaries_list), 400))


# =========================================================
# APIهای پایه
# =========================================================

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class NoteViewSet(viewsets.ModelViewSet):
    serializer_class = NoteSerializer

    def get_queryset(self):
        session = get_session(self.request)
        if not session:
            return Note.objects.none()
        user = UserProfile.objects.filter(mobile=session.mobile).first()
        if not user:
            return Note.objects.none()
        return Note.objects.filter(user=user).order_by('-created_at')

    def perform_create(self, serializer):
        session = get_session(self.request)
        user = UserProfile.objects.filter(mobile=session.mobile).first()
        if not user:
            raise serializers.ValidationError("کاربر پیدا نشد.")
        serializer.save(user=user)


class LegalCaseViewSet(viewsets.ModelViewSet):
    queryset = LegalCase.objects.all()
    serializer_class = LegalCaseSerializer


# =========================================================
# احراز هویت
# =========================================================

@api_view(["POST"])
def send_code(request):
    mobile = request.data.get("mobile")
    mode = request.data.get("mode")

    if not validate_mobile(mobile):
        return Response({"message": "شماره موبایل معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
    if mode not in ["signup", "login"]:
        return Response({"message": "حالت ورود نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

    user = UserProfile.objects.filter(mobile=mobile).first()
    if mode == "signup" and user:
        return Response({"message": "این شماره موبایل قبلاً ثبت نام کرده است."}, status=status.HTTP_409_CONFLICT)
    if mode == "login" and not user:
        return Response({"message": "کاربری با این شماره موبایل پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    rate_limit = VerificationRateLimit.objects.filter(mobile=mobile).first()
    if rate_limit:
        elapsed = timezone.now() - rate_limit.sent_at
        if elapsed.total_seconds() < 180:
            remaining = 180 - int(elapsed.total_seconds())
            return Response({"message": "لطفاً کمی صبر کنید.", "remaining": remaining}, status=status.HTTP_429_TOO_MANY_REQUESTS)

    code = str(secrets.randbelow(900000) + 100000)
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    VerificationCode.objects.filter(mobile=mobile).delete()
    VerificationCode.objects.create(mobile=mobile, code_hash=code_hash)
    VerificationRateLimit.objects.update_or_create(mobile=mobile, defaults={"sent_at": timezone.now()})

    print("=" * 50)
    print("DEVELOPMENT VERIFICATION CODE")
    print("Mobile:", mobile)
    print("Code:", code)
    print("=" * 50)

    return Response({"message": "کد تأیید ارسال شد."}, status=status.HTTP_200_OK)


@api_view(["POST"])
def verify_code(request):
    mobile = request.data.get("mobile")
    code = request.data.get("code")
    mode = request.data.get("mode")

    if not validate_mobile(mobile):
        return Response({"message": "شماره موبایل معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
    if not code or len(str(code)) != 6:
        return Response({"message": "کد تأیید باید 6 رقمی باشد."}, status=status.HTTP_400_BAD_REQUEST)

    verification = VerificationCode.objects.filter(mobile=mobile).first()
    if not verification:
        return Response({"message": "کد تأیید پیدا نشد یا منقضی شده است."}, status=status.HTTP_400_BAD_REQUEST)

    elapsed = timezone.now() - verification.created_at
    if elapsed.total_seconds() > 180:
        verification.delete()
        return Response({"message": "کد تأیید منقضی شده است."}, status=status.HTTP_400_BAD_REQUEST)

    submitted_hash = hashlib.sha256(str(code).encode()).hexdigest()
    if submitted_hash != verification.code_hash:
        return Response({"message": "کد تأیید اشتباه است."}, status=status.HTTP_400_BAD_REQUEST)

    verification.delete()
    token = create_session(mobile, mode)

    return Response({"verified": True, "message": "شماره موبایل تأیید شد.", "token": token}, status=status.HTTP_200_OK)


@api_view(["POST"])
def login(request):
    mobile = request.data.get("mobile")
    password = request.data.get("password")

    if not validate_mobile(mobile):
        return Response({"message": "شماره موبایل معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
    if not password:
        return Response({"message": "رمز عبور را وارد کنید."}, status=status.HTTP_400_BAD_REQUEST)

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)
    if not user.password_hash:
        return Response({"message": "برای این حساب رمز عبور ثبت نشده است."}, status=status.HTTP_401_UNAUTHORIZED)
    if not check_password(password, user.password_hash):
        return Response({"message": "شماره موبایل یا رمز عبور اشتباه است."}, status=status.HTTP_401_UNAUTHORIZED)

    token = create_session(mobile, "login")
    return Response({
        "token": token,
        "patient": {
            "id": user.id, "mobile": user.mobile, "name": user.full_name,
            "nationalId": user.national_id, "age": user.age, "gender": user.gender,
            "height": user.height, "weight": user.weight,
            "diseases": user.diseases, "diseaseDetails": user.disease_details,
        }
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_patient(request, mobile):
    session = get_session(request)
    if not session or session.mobile != mobile:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "id": user.id, "mobile": user.mobile, "name": user.full_name,
        "nationalId": user.national_id, "age": user.age, "gender": user.gender,
        "height": user.height, "weight": user.weight,
        "diseases": user.diseases, "diseaseDetails": user.disease_details, "email": user.email,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def save_patient(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    mobile = request.data.get("mobile")
    if session.mobile != mobile:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_403_FORBIDDEN)

    name = request.data.get("name")
    national_id = request.data.get("nationalId")
    age = request.data.get("age")
    gender = request.data.get("gender")
    height = request.data.get("height")
    weight = request.data.get("weight")
    password = request.data.get("password")

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        user = UserProfile(mobile=mobile)

    user.full_name = name or user.full_name
    user.national_id = national_id or user.national_id
    user.age = age or user.age
    user.gender = gender or user.gender
    user.height = height or user.height
    user.weight = weight or user.weight

    if password:
        if len(password) < 8:
            return Response({"message": "رمز عبور باید حداقل 8 کاراکتر باشد."}, status=status.HTTP_400_BAD_REQUEST)
        user.password_hash = make_password(password)

    user.save()
    return Response({
        "message": "اطلاعات با موفقیت ذخیره شد.",
        "patient": {"id": user.id, "mobile": user.mobile, "name": user.full_name, "nationalId": user.national_id, "age": user.age, "gender": user.gender}
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def change_password(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    if not old_password or not new_password:
        return Response({"message": "همه فیلدها الزامی هستند."}, status=status.HTTP_400_BAD_REQUEST)
    if not check_password(old_password, user.password_hash):
        return Response({"message": "رمز عبور فعلی اشتباه است."}, status=status.HTTP_400_BAD_REQUEST)
    if len(new_password) < 8:
        return Response({"message": "رمز جدید باید حداقل ۸ کاراکتر باشد."}, status=status.HTTP_400_BAD_REQUEST)

    user.password_hash = make_password(new_password)
    user.save()
    return Response({"message": "رمز عبور با موفقیت تغییر کرد."}, status=status.HTTP_200_OK)


# =========================================================
# Paperless & Uploads
# =========================================================

@api_view(["POST"])
def upload_to_paperless(request):
    print("=== [UPLOAD] Step 1: Request received ===")
    try:
        session = get_session(request)
        print(f"=== [UPLOAD] Step 2: Session = {session}")
        if not session:
            return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

        file = request.FILES.get("document")
        print(f"=== [UPLOAD] Step 3: File = {file.name if file else 'NONE'}")
        if not file:
            return Response({"message": "فایلی ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
        extension = os.path.splitext(file.name)[1].lower()
        print(f"=== [UPLOAD] Step 4: Extension = {extension}")
        if extension not in allowed_extensions:
            return Response({"message": "فرمت فایل مجاز نیست."}, status=status.HTTP_400_BAD_REQUEST)

        print("=== [UPLOAD] Step 5: Saving file to storage ===")
        file_path = default_storage.save(f"temp/{file.name}", file)
        full_path = default_storage.path(file_path)
        print(f"=== [UPLOAD] Step 6: Saved to {full_path}")

        try:
            print("=== [UPLOAD] Step 7: Calling Paperless API ===")
            result = upload_document(full_path, title=request.data.get("title", file.name))
            print(f"=== [UPLOAD] Step 8: Paperless result = {result}")
            if result.get("success"):
                return Response({"message": "سند برای پردازش ارسال شد.", "task_id": result.get("task_id")}, status=status.HTTP_200_OK)
            return Response({"message": "خطا در آپلود سند.", "error": result.get("error")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if os.path.exists(full_path):
                os.remove(full_path)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"!!! [UPLOAD FATAL ERROR] !!!: {e}")
        return Response(
            {"message": "خطای داخلی در آپلود.", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
def paperless_task_status(request, task_id):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        task_data = get_task_status(task_id)
        return Response(task_data if task_data else {"message": "تسک پیدا نشد."}, status=status.HTTP_200_OK if task_data else 404)
    except Exception as exc:
        return Response({"message": f"خطا: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def paperless_search(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    query = request.query_params.get('q', '')
    if not query:
        return Response({"message": "عبارت جستجو ارسال نشده."}, status=status.HTTP_400_BAD_REQUEST)

    results = search_documents(query)
    if results:
        return Response(results, status=status.HTTP_200_OK)
    return Response({"message": "خطا در جستجو."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def paperless_get_document(request, document_id):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        response = requests.get(
            f"{settings.PAPERLESS_URL}/api/documents/{document_id}/",
            headers={"Authorization": f"Token {settings.PAPERLESS_API_TOKEN}"},
            timeout=15,
        )
        return Response(response.json(), status=response.status_code)
    except Exception:
        return Response({"message": "خطا در ارتباط با Paperless."}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
@xframe_options_exempt
def paperless_document_preview(request, document_id):
    token = request.query_params.get("token")
    if not token:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    session = AuthSession.objects.filter(token_hash=hash_token(token), expires_at__gt=timezone.now()).first()
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        response = requests.get(
            f"{settings.PAPERLESS_URL}/api/documents/{document_id}/download/",
            headers={"Authorization": f"Token {settings.PAPERLESS_API_TOKEN}"},
            timeout=15,
        )
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'application/pdf')
            django_response = HttpResponse(response.content, content_type=content_type)
            django_response["X-Frame-Options"] = "ALLOWALL"
            return django_response
        return Response({"message": "فایل پیدا نشد."}, status=response.status_code)
    except Exception as e:
        return Response({"message": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["POST"])
def check_file_duplicate(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    file_hash = request.data.get("file_hash", "")
    if not file_hash:
        return Response({"message": "هش فایل ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

    existing_doc = Document.objects.filter(sha256_hash=file_hash).first()
    if existing_doc:
        return Response({
            "is_duplicate": True,
            "error_code": "DUPLICATE_FILE",
            "message": "این سند قبلاً آپلود شده است. لطفاً فایل دیگری انتخاب کنید.",
            "document_id": str(existing_doc.id),
            "original_filename": existing_doc.original_filename or "سند بدون نام",
        }, status=status.HTTP_409_CONFLICT)

    return Response({"is_duplicate": False}, status=status.HTTP_200_OK)


# =========================================================
# تحلیل هوشمند سند
# =========================================================
@api_view(["POST"])
def analyze_document_with_ai(request):
    session = get_session(request)
    if not session:
        close_old_connections()
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()

    file_hash = ""
    text = ""
    filename = "سند بدون نام"
    paperless_id = ""

    try:
        text = request.data.get("text", "") or ""
        filename = request.data.get("filename", "سند بدون نام") or "سند بدون نام"
        paperless_id = request.data.get("paperless_id", "") or ""
        file_hash = request.data.get("file_hash", "") or ""
    except Exception:
        pass

    if not text:
        return Response({"message": "متنی ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

    if file_hash:
        existing_doc = Document.objects.filter(sha256_hash=file_hash).first()
        if existing_doc:
            close_old_connections()
            return Response({
                "is_duplicate": True,
                "error_code": "DUPLICATE_FILE",
                "message": "این سند قبلاً آپلود شده است. لطفاً فایل دیگری انتخاب کنید.",
                "document_id": str(existing_doc.id),
                "original_filename": existing_doc.original_filename or "سند بدون نام",
            }, status=status.HTTP_409_CONFLICT)

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = None

    extract_text = text[:10000]
    
    prompt = build_document_analysis_prompt(text)

    result = {
        "main_topic": "نامشخص", "case_type": "نامشخص", "case_number": "نامشخص",
        "judgment_number": "نامشخص", "document_date": "نامشخص", "amount": "نامشخص",
        "plaintiff": "نامشخص", "defendants": "نامشخص", "court": "نامشخص",
        "summary": "خلاصه‌ای تولید نشد.",
        "document_type": "نامشخص",
        "hearing_date": "نامشخص",
        "hearing_time": "نامشخص",
    }

    try:
        client = create_gemini_client()
        print("SENDING REQUEST TO GOOGLE GEMINI API...")
        
        env_models = os.getenv("MODEL_FALLBACKS", "gemini-3.8-flash,gemini-3.5-flash-lite,gemini-flash-latest")
        MODEL_FALLBACKS = [m.strip() for m in env_models.split(",") if m.strip()]
        
        response1 = None
        last_exception = None
        print("MODEL_FALLBACKS at runtime:", MODEL_FALLBACKS)

        for idx, model_name in enumerate(MODEL_FALLBACKS):
            try:
                print(f"Trying Gemini model: {model_name}")
                response1 = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                print(f"✅ Success with model: {model_name}")
                break 
            except Exception as e:
                print(f"⚠️ Model {model_name} failed: {e}")
                last_exception = e
                if idx < len(MODEL_FALLBACKS) - 1 and _is_gemini_overloaded(e):
                    time.sleep(3)
                continue

        if response1 is None:
            raise last_exception or Exception("تمام مدل‌های Gemini با خطا مواجه شدند.")
        
        raw1 = (response1.text or "").strip()
        if not raw1:
            raise ValueError("Gemini پاسخ خالی برگرداند.")
        print("=== GEMINI RAW JSON RESPONSE ===")
        print(raw1)
        print("=================================")

        try:
            parsed_data = json.loads(raw1)
            for key in result.keys():
                if key in parsed_data and parsed_data[key]:
                    result[key] = parsed_data[key]
        except json.JSONDecodeError:
            print("⚠️ Gemini خروجی JSON معتبر نداد.")

        result["plaintiff"] = _normalize_single_name(result["plaintiff"])
        result["defendants"] = _normalize_single_name(result["defendants"])

        if result["main_topic"] in ["نامشخص", "", "مرگ", "دعوا"]:
            result["main_topic"] = result.get("case_type", "پرونده حقوقی")

        if user:
            result["summary"] = _postprocess_summary_names(
                result["summary"], result["plaintiff"], result["defendants"], user
            )
            
        story = None
        new_case = None

        if file_hash:
            try:
                doc, _ = Document.objects.update_or_create(
                    sha256_hash=file_hash,
                    defaults={
                        "user": user,
                        "original_filename": filename,
                        "current_summary": result["summary"],
                        "processing_status": "processed",
                        "external_document_id": paperless_id
                    }
                )

                AIProcessingRun.objects.create(target_document=doc, task_type="summarization", model_name=gemini_model, status="completed")

                case_num_raw = result.get("case_number")
                case_num = _normalize_case_number(case_num_raw) if case_num_raw else "نامشخص"
                if not case_num or case_num == "نامشخص":
                    case_num = f"TEMP-{file_hash[:8]}"

                case_title = f"پرونده {result.get('case_type') or 'حقوقی'}"
                plaintiff_name = result.get("plaintiff")
                defendant_name = result.get("defendants")

                # ۱) تطبیق بر اساس شماره پرونده (با نرمال‌سازی برای سازگاری با داده‌های قدیمی)
                new_case = Case.objects.filter(user=user, case_number_normalized=case_num).first()
                if not new_case and not case_num.startswith("TEMP-"):
                    for c in Case.objects.filter(user=user):
                        if c.case_number_normalized.startswith("TEMP-"):
                            continue
                        if _normalize_case_number(c.case_number_normalized) == case_num:
                            new_case = c
                            break

                # ۲) اگر شماره پرونده نبود، فقط با طرفین مقایسه کن (بکاپ)
                if not new_case:
                    new_case = _find_case_by_parties(user, plaintiff_name, defendant_name)

                if not new_case:
                    new_case = Case.objects.create(
                        user=user,
                        case_number_normalized=case_num,
                        case_number_raw=case_num,
                        court_name=result.get("court"),
                        case_type=result.get("case_type"),
                        title=case_title
                    )
                else:
                    if new_case.case_number_normalized.startswith("TEMP-") and not case_num.startswith("TEMP-"):
                        new_case.case_number_normalized = case_num
                        new_case.case_number_raw = case_num
                    if not new_case.court_name and result.get("court"):
                        new_case.court_name = result.get("court")
                    if not new_case.case_type and result.get("case_type"):
                        new_case.case_type = result.get("case_type")
                    if not new_case.title and case_title:
                        new_case.title = case_title
                    new_case.save()

                DocumentCaseLink.objects.get_or_create(document=doc, case=new_case)

                if plaintiff_name and plaintiff_name != "نامشخص":
                    p_norm = _normalize_name_for_matching(plaintiff_name)
                    already = any(
                        part.role == "خواهان" and _names_match(p_norm, _normalize_name_for_matching(part.person.display_name or ""))
                        for part in new_case.participants.all()
                    )
                    if not already:
                        person, _ = Person.objects.get_or_create(user=user, display_name=plaintiff_name)
                        CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خواهان")

                if defendant_name and defendant_name != "نامشخص":
                    d_norm = _normalize_name_for_matching(defendant_name)
                    already = any(
                        part.role == "خوانده" and _names_match(d_norm, _normalize_name_for_matching(part.person.display_name or ""))
                        for part in new_case.participants.all()
                    )
                    if not already:
                        person, _ = Person.objects.get_or_create(user=user, display_name=defendant_name)
                        CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خوانده")

                linked_docs = DocumentCaseLink.objects.filter(case=new_case)
                doc_summaries = [dl.document.current_summary for dl in linked_docs if dl.document.current_summary]

                case_summary = _generate_case_summary(
                    doc_summaries, client, gemini_model,
                    user=user,
                    plaintiff_str=plaintiff_name,
                    defendant_str=defendant_name,
                )
                new_case.current_summary = case_summary
                new_case.save()

                current_topic = result.get("main_topic", "پرونده حقوقی")

                existing_link = LegalStoryCaseLink.objects.filter(case=new_case).first()
                if existing_link:
                    story = existing_link.legal_story

                if not story:
                    # منطق جدید: هر طرفی از طرفین تطابق داشت، یا شباهت موضوعی ≥ ۵۰٪
                    story = _find_story_for_case(
                        user, plaintiff_name, defendant_name,
                        current_topic,
                        exclude_case_id=new_case.id
                    )

                if not story:
                    story_title = _shorten_story_title(current_topic)
                    story, created = LegalStory.objects.get_or_create(
                        user=user, title=story_title,
                        defaults={
                            "user_context": "ایجاد خودکار",
                            "current_summary": result["summary"],
                            "story_status": "active"
                        }
                    )

                LegalStoryCaseLink.objects.get_or_create(legal_story=story, case=new_case)

                story_case_links = LegalStoryCaseLink.objects.filter(legal_story=story)
                case_summaries_list = [link.case.current_summary for link in story_case_links if link.case.current_summary]

                story_summary = _generate_story_summary(
                    case_summaries_list, client, gemini_model,
                    user=user,
                    plaintiff_str=plaintiff_name,
                    defendant_str=defendant_name,
                )

                if story and story_summary:
                    story.current_summary = story_summary
                    story.save()

                # ---- ثبت ابلاغیه ----
                doc_type = str(result.get("document_type") or "").strip()
                is_notice = (
                    "ابلاغ" in doc_type
                    or "ابلاغ" in (filename or "")
                    or "ابلاغیه" in str(result.get("main_topic") or "")
                )

                if is_notice:
                    now = timezone.now()
                    Notice.objects.update_or_create(
                        user=user,
                        document_title=filename or "سند بدون نام",
                        defaults={
                            "story_title": story.title if story else "",
                            "date": now.strftime("%Y/%m/%d"),
                            "time": now.strftime("%H:%M"),
                            "is_active": True,
                            "hearing_date": result.get("hearing_date") or "تعیین نشده",
                            "hearing_time": result.get("hearing_time") or "",
                        },
                    )
                    print(f"[NOTICE-CREATED] user={user.id} filename={filename} hearing={result.get('hearing_date')}")

                facts_to_save = {
                    "judgment_number": result.get("judgment_number"),
                    "document_date": result.get("document_date"),
                    "amount": result.get("amount"),
                    "plaintiff": result.get("plaintiff"),
                    "defendants": result.get("defendants"),
                    "court": result.get("court"),
                    "case_number": result.get("case_number"),
                }
                for key, value in facts_to_save.items():
                    if value and value != "نامشخص":
                        DocumentExtractedFact.objects.update_or_create(
                            document=doc, field_key=key, defaults={"value_raw": value, "is_current": True}
                        )

            except Exception as e:
                print("خطا در ذخیره در دیتابیس:", e)

        return Response({
            "summary": result["summary"],
            "main_topic": result["main_topic"],
            "case_number": new_case.case_number_raw if new_case else result.get("case_number"),
            "plaintiff": result["plaintiff"],
            "defendants": result["defendants"],
            "court": result["court"],
            "story_id": str(story.id) if story else None,
            "case_id": str(new_case.id) if new_case else None,
            "story_summary": story.current_summary if story else "",
            "case_summary": new_case.current_summary if new_case else "",
            "case_title": new_case.title if new_case and new_case.title else "",
            "document_date": result.get("document_date") or "نامشخص"
        }, status=status.HTTP_200_OK)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        if _is_gemini_overloaded(exc):
            return Response(
                {"error_code": "AI_BUSY", "message": "سرویس هوش مصنوعی فعلاً شلوغ است. چند دقیقه دیگر دوباره تلاش کنید."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {"error_code": "PROCESSING_FAILED", "message": "خطایی در پردازش سند رخ داد. لطفاً دوباره تلاش کنید."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as close_error:
                print("خطا در بستن اتصال Gemini:", close_error)


# =========================================================
# داستان‌ها، پرونده‌ها و ابلاغیه‌ها
# =========================================================

@api_view(["GET", "POST"])
def legal_stories_api(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()

    if request.method == "GET":
        stories = LegalStory.objects.filter(user=user).order_by('-created_at')
        serializer = LegalStorySerializer(stories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "POST":
        title = request.data.get("title")
        if not title:
            return Response({"message": "عنوان الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
        story = LegalStory.objects.create(user=user, title=title, story_status="active")
        return Response({"id": story.id}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def get_story_details(request, story_id):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    story = LegalStory.objects.filter(id=story_id, user=user).first()

    if not story:
        return Response({"message": "داستان پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    cases_data = []
    for link in story.case_links.all():
        c = link.case
        people_data = []
        plaintiff_name = ""
        defendant_name = ""
        for p in c.participants.all():
            people_data.append({"name": p.person.display_name, "role": p.role})
            if p.role == "خواهان" and not plaintiff_name:
                plaintiff_name = p.person.display_name
            if p.role == "خوانده" and not defendant_name:
                defendant_name = p.person.display_name

        if not plaintiff_name or not defendant_name:
            doc_links = DocumentCaseLink.objects.filter(case=c)
            for dl in doc_links:
                if not plaintiff_name:
                    fact_p = dl.document.extracted_facts.filter(field_key="plaintiff", is_current=True).first()
                    if fact_p and fact_p.value_raw and fact_p.value_raw != "نامشخص":
                        plaintiff_name = fact_p.value_raw
                        people_data.append({"name": plaintiff_name, "role": "خواهان"})
                if not defendant_name:
                    fact_d = dl.document.extracted_facts.filter(field_key="defendants", is_current=True).first()
                    if fact_d and fact_d.value_raw and fact_d.value_raw != "نامشخص":
                        defendant_name = fact_d.value_raw
                        people_data.append({"name": defendant_name, "role": "خوانده"})
                if plaintiff_name and defendant_name:
                    break

        documents_data = []
        doc_links = DocumentCaseLink.objects.filter(case=c).order_by('-document__created_at')
        for dl in doc_links:
            doc = dl.document
            facts_data = {}
            for fact in doc.extracted_facts.filter(is_current=True):
                facts_data[fact.field_key] = fact.value_raw

            documents_data.append({
                "id": str(doc.id),
                "filename": doc.original_filename or "سند بدون نام",
                "summary": doc.current_summary or "خلاصه‌ای ثبت نشده است.",
                "date": doc.created_at.strftime("%Y/%m/%d"),
                "paperless_id": doc.external_document_id,
                "facts": facts_data
            })

        cases_data.append({
            "id": str(c.id),
            "title": c.title or f"پرونده {c.case_type or 'حقوقی'}",
            "case_number": c.case_number_raw,
            "court": c.court_name,
            "people": people_data,
            "plaintiff": plaintiff_name,
            "defendant": defendant_name,
            "judgment_subject": c.case_type or "",
            "summary": c.current_summary or "خلاصه‌ای ثبت نشده است.",
            "documents": documents_data
        })

    return Response({
        "id": str(story.id),
        "title": story.title,
        "summary": story.current_summary,
        "cases": cases_data
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_user_notices(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    notices = Notice.objects.filter(user=user).order_by('-created_at')
    data = [{
        "id": n.id,
        "document_title": n.document_title,
        "story_title": n.story_title or "نامشخص",
        "date": n.date or "",
        "time": n.time or "",
        "is_active": n.is_active,
        "hearing_date": n.hearing_date or "تعیین نشده",
        "hearing_time": n.hearing_time or "",
        "is_expired": _is_hearing_past(n.hearing_date),
    } for n in notices]

    return Response(data, status=status.HTTP_200_OK)


@api_view(["POST"])
def confirm_categorization(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    updates = request.data.get("updates", [])

    for update in updates:
        story_id = update.get("story_id")
        case_id = update.get("case_id")

        new_topic = update.get("main_topic")
        new_story_summary = update.get("story_summary")

        new_case_title = update.get("case_title")
        new_case_number = update.get("case_number")
        new_case_summary = update.get("case_summary")

        if story_id and (new_topic or new_story_summary):
            story = LegalStory.objects.filter(id=story_id, user=user).first()
            if story:
                if new_topic:
                    story.title = new_topic
                if new_story_summary:
                    story.current_summary = new_story_summary
                story.save()

        if case_id and (new_case_title or new_case_number or new_case_summary):
            case = Case.objects.filter(id=case_id, user=user).first()
            if case:
                if new_case_title:
                    case.title = new_case_title
                if new_case_number:
                    case.case_number_normalized = new_case_number
                    case.case_number_raw = new_case_number
                if new_case_summary:
                    case.current_summary = new_case_summary
                case.save()

    return Response({"message": "تغییرات با موفقیت ذخیره شد."}, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_all_cases(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    cases = LegalCase.objects.filter(user=user).order_by('-created_at')
    data = [{"id": c.id, "case_number": c.case_number, "title": c.title, "topic": c.topic, "status": c.status, "court": c.court, "summary": c.summary} for c in cases]
    return Response(data, status=status.HTTP_200_OK)