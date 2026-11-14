import hashlib
import secrets
import os
import json
import re
import requests
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
    text = re.sub(r'(?:با\s+)?وکالت(?:\s+آقای|\s+خانم)?\s+[آ-ی]+\s+[آ-ی]+', '', text)
    text = re.sub(r'(?:با\s+)?وکیل(?:\s+آقای|\s+خانم)?\s+[آ-ی]+\s+[آ-ی]+', '', text)
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


def _generate_case_summary(doc_summaries_list, ollama_url, ollama_model):
    if not doc_summaries_list:
        return "خلاصه‌ای ثبت نشده است."
    if len(doc_summaries_list) == 1:
        return doc_summaries_list[0]

    combined_text = "\n- ".join(doc_summaries_list)
    prompt = f"""شما یک دستیار حقوقی هستید. خلاصه‌های زیر مربوط به اسناد مختلفِ یک پرونده حقوقی مشخص هستند. یک "خلاصه پرونده" جامع (حداکثر ۳ تا ۴ خط) بنویسید که موضوع اصلی این پرونده، اقدامات انجام شده و وضعیت فعلی آن را نشان دهد.

قوانین بسیار مهم:
- ذکر نام افراد در خلاصه پرونده و خلاصه هوشمند مجاز است: می‌توانید نام خواهان و خوانده را ذکر کنید. اگر تعداد افراد بیشتر از دو نفر بود، فقط نام یک نفر از هر طرف را (ترجیحاً کسی که پرونده را ثبت کرده است) ذکر کنید.
- ذکر مبلغ مجاز است: اگر در اسناد مبلغی (مثل مبلغ چک، مهریه، یا خسارت) وجود دارد که به شفافیت پرونده کمک می‌کند، می‌توانید آن را ذکر کنید.
- خلاصه باید با کلمات خودتان بازنویسی شود و کپی برداری مستقیم از جملات متن نباشد.
- نمای کلی از تمام اسناد این پرونده (مثلاً دادخواست، نظریه کارشناس، دادنامه) بدهید.
-در خلاصه داستان، ذکر نام افراد و همینطور مبلغ و آوردن اسم خواهان و خوانده جایز نیست.
خلاصه‌های اسناد این پرونده:
- {combined_text}

خلاصه پرونده:"""

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 300, "temperature": 0.15, "repeat_penalty": 1.2}
    }
    try:
        response = requests.post(
            f"{ollama_url}/api/generate", json=payload, timeout=300, proxies={"http": None, "https": None}
        )
        response.raise_for_status()
        raw_summary = response.json().get("response", "").strip()
        raw_summary = re.sub(r"^(?:\*\*)?\s*خلاصه\s*(?:پرونده)?\s*[:：]?\s*", "", raw_summary)
        raw_summary = re.sub(r"(?:یک\s+)?(?:مرد|زن|شخص|فرد|طرف|طرفین)(?:ی)?\s*(?:به\s+نام\s+)?", "", raw_summary)
        raw_summary = re.sub(r"(?:آقای|خانم|به\s+نام|تحت\s+عنوان)\s+", "", raw_summary)
        raw_summary = re.sub(r"[،,]\s*[،,]", "،", raw_summary)
        return re.sub(r"\s+", " ", raw_summary).strip()
    except Exception as e:
        print("خطا در تولید خلاصه پرونده:", e)
        return " ".join(doc_summaries_list)[:300]


def _generate_story_summary(case_summaries_list, ollama_url, ollama_model):
    if not case_summaries_list:
        return "خلاصه‌ای ثبت نشده است."
    if len(case_summaries_list) == 1:
        return case_summaries_list[0]

    combined_text = "\n- ".join(case_summaries_list)
    prompt = f"""شما یک دستیار حقوقی هستید. خلاصه‌های زیر مربوط به پرونده‌های مختلفی هستند که همگی به یک "داستان حقوقی" واحد مربوط می‌شوند. شما باید یک "خلاصه داستان" کلی (حداکثر ۳ تا ۴ خط) بنویسید که مخاطب را در جریان روند کلی قرار دهد.

قوانین بسیار مهم:
- لحن متن باید به صورت «دوم شخص» باشد (مثلاً: "شما در تاریخ... درخواست طلاق ثبت کردید" یا "شما دادخواست مطالبه مهریه را تنظیم کرده‌اید").
- اصلا و ابدا اسم خواهان و خوانده را نیاورید. به جای اسم آن‌ها از کلمه "شما" (برای کاربر) و "طرف مقابل" استفاده کنید.
- روند کلی را بگویید: چه اقداماتی تا الان انجام شده و چه اقداماتی قرار است انجام شود.
- حتماً تاریخ‌ها و اقدامات کلیدی (مثل تعیین وقت جلسه) را در صورت وجود در خلاصه‌ها ذکر کنید.
- خلاصه باید منسجم و شبیه به یک روایت باشد.
- اسم افراد اصلا نیاید 
خلاصه‌های پرونده‌های این داستان:
- {combined_text}

خلاصه داستان جامع:"""

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 300, "temperature": 0.2, "repeat_penalty": 1.1}
    }
    try:
        response = requests.post(
            f"{ollama_url}/api/generate", json=payload, timeout=300, proxies={"http": None, "https": None}
        )
        response.raise_for_status()
        raw_story = response.json().get("response", "").strip()
        raw_story = re.sub(r"^(?:\*\*)?\s*خلاصه\s*(?:داستان)?\s*[:：]?\s*", "", raw_story)
        raw_story = re.sub(r"(?:آقای|خانم|به\s+نام)\s+[آ-ی]+(?:\s+[آ-ی]+)?", "شما", raw_story)
        raw_story = re.sub(r"[،,]\s*[،,]", "،", raw_story)
        return re.sub(r"\s+", " ", raw_story).strip()
    except Exception as e:
        print("خطا در تولید خلاصه داستان:", e)
        return " ".join(case_summaries_list)[:300]


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
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    file = request.FILES.get("document")
    if not file:
        return Response({"message": "فایلی ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in allowed_extensions:
        return Response({"message": "فرمت فایل مجاز نیست."}, status=status.HTTP_400_BAD_REQUEST)

    file_path = default_storage.save(f"temp/{file.name}", file)
    full_path = default_storage.path(file_path)

    try:
        result = upload_document(full_path, title=request.data.get("title", file.name))
        if result.get("success"):
            return Response({"message": "سند برای پردازش ارسال شد.", "task_id": result.get("task_id")}, status=status.HTTP_200_OK)
        return Response({"message": "خطا در آپلود سند.", "error": result.get("error")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if os.path.exists(full_path):
            os.remove(full_path)


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

    existing = LegalCase.objects.filter(file_hash=file_hash).first()
    if existing:
        return Response({"is_duplicate": True, "message": f"این پرونده قبلاً ثبت شده است (شماره: {existing.case_number})."}, status=status.HTTP_409_CONFLICT)

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

    text = request.data.get("text", "")
    filename = request.data.get("filename", "سند بدون نام")
    paperless_id = request.data.get("paperless_id", "")

    if not text:
        return Response({"message": "متنی ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

    file_hash = request.data.get("file_hash", "")
    ollama_url = "http://localhost:11434"
    ollama_model = "aya:8b"

    extract_text = text[:1500]
    prompt = f"""شما یک دستیار حقوقی فارسی‌زبان هستید. متن زیر را بخوانید و دقیقاً به ترتیب زیر پاسخ دهید:

=== بخش ۱: خلاصه ===
یک خلاصه جامع و دقیق (حداکثر ۳ تا ۴ خط) بنویسید که مشخص کند این سند چیست (مثلاً ابلاغیه، دادنامه، دادخواست، نظریه کارشناس)، چه کسی از چه کسی چه چیزی می‌خواهد، چه مبلغی در آن ذکر شده (در صورت وجود) و چه اقدام بعدی قرار است انجام شود.

قوانین خلاصه:
- ذکر نام افراد (خواهان و خوانده) مجاز است.
- ذکر مبالغ و اعداد مجاز است.
- لحن باید روان، قابل فهم و شبیه به یک خلاصه خبری باشد.
- نام وکیل را نیاورید.

خلاصه: (متن خلاصه را اینجا بنویسید)

=== بخش ۲: اطلاعات ===
موضوع: (موضوع مشخص و واقعی پرونده در حداکثر ۵ کلمه. هرگز دسته‌بندی کلی مثل "حقوقی خانواده" ننویس. مثال: فروش خودرو، الزام به سند، طلاق توافقی)
نوع پرونده: (از لیست: حقوقی خانواده، حقوقی ملکی، حقوقی قراردادها، حقوقی خودرو، کیفری، اجرای اسناد و مفقودی)
شماره پرونده: (شماره یا نامشخص)
شماره دادنامه: (شماره یا نامشخص)
تاریخ سند: (تاریخ یا نامشخص)
مبلغ: (مبلغ یا نامشخص)
خواهان: (نام کامل یا نامشخص.)
خوانده: (نام کامل یا نامشخص.)
دادگاه: (نام دادگاه یا شعبه یا نامشخص)

متن سند:
{extract_text}"""

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 600, "temperature": 0.1, "repeat_penalty": 1.2}
    }

    result = {
        "main_topic": "نامشخص", "case_type": "نامشخص", "case_number": "نامشخص",
        "judgment_number": "نامشخص", "document_date": "نامشخص", "amount": "نامشخص",
        "plaintiff": "نامشخص", "defendants": "نامشخص", "court": "نامشخص", "summary": "خلاصه‌ای تولید نشد."
    }

    try:
        print("SENDING COMBINED REQUEST TO OLLAMA...")
        response1 = requests.post(
            f"{ollama_url}/api/generate", json=payload, timeout=1200, proxies={"http": None, "https": None}
        )
        response1.raise_for_status()
        raw1 = response1.json().get("response", "").strip()

        print("=== OLLAMA RAW RESPONSE ===")
        print(raw1)
        print("=======================================")

        patterns = {
            "main_topic": r"موضوع\s*[:：]\s*(.+?)(?=\n|نوع پرونده|$)",
            "case_type": r"نوع\s*پرونده\s*[:：]\s*(.+?)(?=\n|شماره پرونده|$)",
            "case_number": r"شماره\s*پرونده\s*[:：]\s*(.+?)(?=\n|شماره دادنامه|$)",
            "judgment_number": r"شماره\s*دادنامه\s*[:：]\s*(.+?)(?=\n|تاریخ تنظیم|$)",
            "document_date": r"تاریخ(?:\s*سند|\s*تنظیم)?\s*[:：]\s*(.+?)(?=\n|مبلغ|$)",
            "amount": r"مبلغ\s*[:：]\s*(.+?)(?=\n|خواهان|$)",
            "plaintiff": r"خواهان\s*[:：]\s*(.+?)(?=\n|خوانده|$)",
            "defendants": r"خوانده\s*[:：]\s*(.+?)(?=\n|دادگاه|$)",
            "court": r"دادگاه\s*[:：]\s*(.+?)(?=\n|===|خلاصه|$)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, raw1, re.DOTALL)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip()
                if value and value != "نامشخص":
                    result[key] = value

        if result["plaintiff"]:
            result["plaintiff"] = re.sub(r"\s*فرزند\s+[^\s،\.]+", "", result["plaintiff"]).strip()
        if result["defendants"]:
            result["defendants"] = re.sub(r"\s*فرزند\s+[^\s،\.]+", "", result["defendants"]).strip()

        generic_case_types = [
            "حقوقی خانواده", "حقوقی ملکی", "حقوقی قراردادها",
            "حقوقی خودرو", "کیفری", "اجرای اسناد و مفقودی",
            "حقوقی", "خانواده", "ملکی", "قراردادها", "خودرو"
        ]

        topic_lower = result["main_topic"]
        if any(w in topic_lower for w in ["خودرو", "ماشین", "پلاک", "وانت", "سواری", "کشنده"]):
            result["case_type"] = "حقوقی خودرو"
        elif any(w in topic_lower for w in ["ملک", "املاک", "تخلیه", "تصرف", "آپارتمان", "زمین"]):
            result["case_type"] = "حقوقی ملکی"
        elif any(w in topic_lower for w in ["طلاق", "مهریه", "نفقه", "حضانت", "تمکین"]):
            result["case_type"] = "حقوقی خانواده"
        elif any(w in topic_lower for w in ["چک", "سفته", "قرارداد", "مطالبه", "فسخ", "ثمن"]):
            result["case_type"] = "حقوقی قراردادها"

        if result["main_topic"] in generic_case_types or len(result["main_topic"]) < 3:
            if result["case_type"] and result["case_type"] != "نامشخص":
                result["main_topic"] = f"پرونده {result['case_type']}"
            else:
                result["main_topic"] = "پرونده حقوقی"

        summary_found = False
        parts = raw1.split("=== بخش ۲: اطلاعات ===")
        if len(parts) > 1:
            summary_text = parts[0].replace("=== بخش ۱: خلاصه ===", "").replace("خلاصه:", "").strip()
        else:
            summary_match = re.search(r"^[\s]*(?:\*\*)?\s*خلاصه(?:[\s‌ی]*(?:حقوقی|سند|ساده|پرونده|دعوا|دادنامه))?(?:\*\*)?\s*[:：]?\s*(?:\*\*)?\s*(.+?)(?=\n===|نوع پرونده|شماره پرونده|$)", raw1, re.MULTILINE | re.DOTALL)
            summary_text = summary_match.group(1).strip() if summary_match else ""

        if summary_text and len(summary_text) > 15:
            summary_text = re.sub(r"\s+", " ", summary_text).strip()
            summary_text = _clean_summary_text(summary_text, filename)
            if "موضوع:" in summary_text:
                summary_text = summary_text.split("موضوع:")[0].strip()
            if "شماره پرونده:" in summary_text:
                summary_text = summary_text.split("شماره پرونده:")[0].strip()
            if len(summary_text) > 10:
                result["summary"] = summary_text
                summary_found = True
                print(f"✅ خلاصه هوشمند (سطح ۱) با موفقیت استخراج شد ({len(summary_text)} کاراکتر)")

        if not summary_found:
            print("⚠️ خلاصه تولید نشد. ساخت خلاصه جایگزین از روی اطلاعات...")
            plaintiff = result.get("plaintiff", "نامشخص")
            defendant = result.get("defendants", "نامشخص")
            court = result.get("court", "نامشخص")
            topic = result.get("main_topic", "حقوقی")
            if plaintiff != "نامشخص" and defendant != "نامشخص":
                result["summary"] = f"پرونده‌ای با موضوع {topic} در {court} مطرح شده است. خواهان ({plaintiff}) علیه خوانده ({defendant}) دعوایی را مطرح کرده است."
            else:
                result["summary"] = f"پرونده‌ای با موضوع {topic} در {court} مطرح و در دست بررسی است."

        invalid_topics = ["مرگ", "دعوا", "اختلاف", "نامشخص", ""]
        if result["main_topic"] in invalid_topics:
            result["main_topic"] = "پرونده حقوقی"

        # ⬇️ متغیرها رو قبل از try/except تعریف می‌کنیم ⬇️
        story = None
        new_case = None

        if file_hash:
            try:
                user = UserProfile.objects.filter(mobile=session.mobile).first()

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

                AIProcessingRun.objects.create(target_document=doc, task_type="summarization", model_name="aya:8b", status="completed")

                case_num = result.get("case_number")
                if case_num == "نامشخص" or not case_num:
                    case_num = f"TEMP-{file_hash[:8]}"

                # ⬇️ تعریف case_title قبل از استفاده ⬇️
                case_title = f"پرونده {result.get('case_type') or 'حقوقی'}"

                new_case, _ = Case.objects.get_or_create(
                    user=user, case_number_normalized=case_num,
                    defaults={
                        "case_number_raw": case_num,
                        "court_name": result.get("court"),
                        "case_type": result.get("case_type"),
                        "title": case_title
                    }
                )

                DocumentCaseLink.objects.get_or_create(document=doc, case=new_case)

                plaintiff_name = result.get("plaintiff")
                if plaintiff_name and plaintiff_name != "نامشخص":
                    person, _ = Person.objects.get_or_create(user=user, display_name=plaintiff_name)
                    CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خواهان")

                defendant_name = result.get("defendants")
                if defendant_name and defendant_name != "نامشخص":
                    person, _ = Person.objects.get_or_create(user=user, display_name=defendant_name)
                    CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خوانده")

                linked_docs = DocumentCaseLink.objects.filter(case=new_case)
                doc_summaries = [dl.document.current_summary for dl in linked_docs if dl.document.current_summary]
                case_summary = _generate_case_summary(doc_summaries, ollama_url, ollama_model)
                new_case.current_summary = case_summary
                new_case.save()
                print(f"✅ خلاصه پرونده (سطح ۲) آپدیت شد: {case_summary[:50]}...")

                current_topic = result.get("main_topic", "پرونده حقوقی")

                # ۳-الف
                existing_link = LegalStoryCaseLink.objects.filter(case=new_case).first()
                if existing_link:
                    story = existing_link.legal_story
                    print(f"=== Using EXISTING story of this case: {story.id} ===")

                # ۳-ب
                if not story and plaintiff_name and plaintiff_name != "نامشخص" and defendant_name and defendant_name != "نامشخص":
                    matching_cases = Case.objects.filter(
                        user=user,
                        participants__person__display_name=plaintiff_name,
                        participants__role="خواهان"
                    ).filter(
                        participants__person__display_name=defendant_name,
                        participants__role="خوانده"
                    ).distinct()

                    for c in matching_cases:
                        if c.id == new_case.id:
                            continue
                        link = LegalStoryCaseLink.objects.filter(case=c).first()
                        if link:
                            story = link.legal_story
                            print(f"=== Found story by PARTIES: {story.id} - {story.title} ===")
                            break

                # ۳-ج
                if not story and current_topic and current_topic != "نامشخص":
                    all_stories = LegalStory.objects.filter(user=user)
                    for s in all_stories:
                        if _check_topic_similarity(current_topic, s.title):
                            story = s
                            print(f"=== Found story by TOPIC SIMILARITY: {story.id} - {story.title} ≈ {current_topic} ===")
                            break

                # ۳-د
                if not story:
                    final_title = current_topic if current_topic not in generic_case_types else f"پرونده {result.get('case_type', 'حقوقی')}"
                    story, created = LegalStory.objects.get_or_create(
                        user=user, title=final_title,
                        defaults={
                            "user_context": "ایجاد خودکار",
                            "current_summary": result["summary"],
                            "story_status": "active"
                        }
                    )
                    if created:
                        print(f"=== Created NEW story: {story.id} - {story.title} ===")

                LegalStoryCaseLink.objects.get_or_create(legal_story=story, case=new_case)

                story_case_links = LegalStoryCaseLink.objects.filter(legal_story=story)
                case_summaries_list = [link.case.current_summary for link in story_case_links if link.case.current_summary]
                story_summary = _generate_story_summary(case_summaries_list, ollama_url, ollama_model)

                if story and story_summary:
                    story.current_summary = story_summary
                    story.save()
                    print(f"✅ خلاصه داستان (سطح ۳) آپدیت شد: {story_summary[:50]}...")

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

                if "ابلاغ" in result.get("case_type", "") or "ابلاغ" in result.get("main_topic", "") or "ابلاغ" in raw1:
                    Notice.objects.create(
                        user=user,
                        document_title=filename,
                        story_title=story.title,
                        date=timezone.now().strftime("%Y/%m/%d"),
                        time=timezone.now().strftime("%H:%M"),
                        is_active=True,
                        hearing_date="تعیین نشده",
                        hearing_time=""
                    )
                    print("=== New Notice created automatically ===")

            except Exception as e:
                print("خطا در ذخیره در دیتابیس:", e)

        # ⬇️⬇️⬇️ return بیرون از try/except و if file_hash ⬇️⬇️⬇️
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

    except requests.RequestException as exc:
        return Response({"message": "زمان پردازش طولانی شد یا ارتباط قطع شد.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


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

    # ⬇️ فیکس شد: این for دیگه اضافه تو نرفته ⬇️
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