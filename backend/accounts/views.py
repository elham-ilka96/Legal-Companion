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
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Notice
# ⬇️ ایمپورت تمام مدل‌ها (شامل مدل جدید DocumentExtractedFact)
from .models import (
    UserProfile,
    LegalCase,
    VerificationCode,
    AuthSession,
    VerificationRateLimit,
    Note,
    Document,
    AIProcessingRun,
    Case,
    LegalStory,
    LegalStoryCaseLink,
    DocumentCaseLink,
    Person,
    CaseParticipant,
    DocumentExtractedFact,
)

from .serializers import (
    UserProfileSerializer,
    LegalCaseSerializer,
    NoteSerializer,
    LegalStorySerializer,
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
    session = AuthSession.objects.filter(
        token_hash=token_hash,
        expires_at__gt=timezone.now()
    ).first()
    return session


def create_session(mobile, mode):
    token = secrets.token_hex(32)
    AuthSession.objects.create(
        token_hash=hash_token(token),
        mobile=mobile,
        mode=mode,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return token


# =========================================================
# UserProfile API
# =========================================================

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


# =========================================================
# Note API (یادداشت‌ها)
# =========================================================

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


# =========================================================
# LegalCase API
# =========================================================

class LegalCaseViewSet(viewsets.ModelViewSet):
    queryset = LegalCase.objects.all()
    serializer_class = LegalCaseSerializer


# =========================================================
# ارسال کد تأیید
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

    print("")
    print("=" * 50)
    print("DEVELOPMENT VERIFICATION CODE")
    print("Mobile:", mobile)
    print("Code:", code)
    print("=" * 50)
    print("")

    return Response({"message": "کد تأیید ارسال شد."}, status=status.HTTP_200_OK)


# =========================================================
# بررسی کد تأیید
# =========================================================

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


# =========================================================
# Login با شماره موبایل + رمز عبور
# =========================================================

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


# =========================================================
# گرفتن اطلاعات بیمار
# =========================================================

@api_view(["GET"])
def get_patient(request, mobile):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    if session.mobile != mobile:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_403_FORBIDDEN)

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        "id": user.id, "mobile": user.mobile, "name": user.full_name,
        "nationalId": user.national_id, "age": user.age, "gender": user.gender,
        "height": user.height, "weight": user.weight,
        "diseases": user.diseases, "diseaseDetails": user.disease_details, "email": user.email,
    }, status=status.HTTP_200_OK)


# =========================================================
# ثبت / بروزرسانی اطلاعات بیمار
# =========================================================

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

    diseases = request.data.get("diseases", [])
    if isinstance(diseases, str):
        try: diseases = json.loads(diseases)
        except Exception: diseases = []

    disease_details = request.data.get("diseaseDetails", {})
    if isinstance(disease_details, str):
        try: disease_details = json.loads(disease_details)
        except Exception: disease_details = {}

    user = UserProfile.objects.filter(mobile=mobile).first()

    if not user:
        user = UserProfile(mobile=mobile, full_name=name or "", national_id=national_id, age=age, gender=gender, height=height, weight=weight, diseases=diseases, disease_details=disease_details)
    else:
        user.full_name = name or user.full_name
        user.national_id = national_id
        user.age = age
        user.gender = gender
        user.height = height
        user.weight = weight
        user.diseases = diseases
        user.disease_details = disease_details

    if password:
        if len(password) < 8:
            return Response({"message": "رمز عبور باید حداقل 8 کاراکتر باشد."}, status=status.HTTP_400_BAD_REQUEST)
        user.password_hash = make_password(password)

    user.save()

    return Response({
        "message": "اطلاعات با موفقیت ذخیره شد.",
        "patient": {"id": user.id, "mobile": user.mobile, "name": user.full_name, "nationalId": user.national_id, "age": user.age, "gender": user.gender, "height": user.height, "weight": user.weight, "diseases": user.diseases, "diseaseDetails": user.disease_details}
    }, status=status.HTTP_200_OK)


# =========================================================
# آپلود سند به Paperless
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

    if file.size == 0 or file.size > 10 * 1024 * 1024:
        return Response({"message": "حجم فایل باید بیشتر از صفر و حداکثر ۱۰ مگابایت باشد."}, status=status.HTTP_400_BAD_REQUEST)

    file_path = default_storage.save(f"temp/{file.name}", file)
    full_path = default_storage.path(file_path)

    try:
        result = upload_document(full_path, title=request.data.get("title", file.name))
        if result.get("success"):
            return Response({"message": "سند برای پردازش به Paperless ارسال شد.", "task_id": result.get("task_id")}, status=status.HTTP_200_OK)
        return Response({"message": "خطا در آپلود سند.", "error": result.get("error", "خطای نامشخص")}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if os.path.exists(full_path):
            os.remove(full_path)


# =========================================================
# وضعیت تسک Paperless
# =========================================================

@api_view(["GET"])
def paperless_task_status(request, task_id):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        task_data = get_task_status(task_id)
    except Exception as exc:
        return Response({"message": f"خطا در دریافت وضعیت تسک: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    if task_data:
        return Response(task_data, status=status.HTTP_200_OK)
    return Response({"message": "تسک پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)


# =========================================================
# جستجو در اسناد Paperless
# =========================================================

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


# =========================================================
# دریافت یک سند از Paperless
# =========================================================

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
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        return Response({"message": "سند پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)
    except requests.RequestException:
        return Response({"message": "خطا در ارتباط با Paperless هنگام دریافت سند."}, status=status.HTTP_502_BAD_GATEWAY)
    except ValueError:
        return Response({"message": "پاسخ سند از Paperless قابل خواندن نیست."}, status=status.HTTP_502_BAD_GATEWAY)


# =========================================================
# پیش‌نمایش / دانلود فایل سند از Paperless ⬅️ (جدید)
# =========================================================
@api_view(["GET"])
def paperless_document_preview(request, document_id):
    # چون iframe نمی‌تونه هدر بفرسته، توکن رو از پارامترهای آدرس می‌خونیم
    token = request.query_params.get("token")
    if not token:
        return Response({"message": "دسترسی غیرمجاز. توکن ارسال نشده."}, status=status.HTTP_401_UNAUTHORIZED)
        
    token_hash = hash_token(token)
    session = AuthSession.objects.filter(token_hash=token_hash, expires_at__gt=timezone.now()).first()
    
    if not session:
        return Response({"message": "دسترسی غیرمجاز. توکن منقضی شده است."}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        response = requests.get(
            f"{settings.PAPERLESS_URL}/api/documents/{document_id}/download/",
            headers={"Authorization": f"Token {settings.PAPERLESS_API_TOKEN}"},
            timeout=15,
        )
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', 'application/pdf')
            django_response = HttpResponse(response.content, content_type=content_type)
            django_response["X-Frame-Options"] = "ALLOWALL"  # ⬅️ این خط برای دور زدن محدودیت مرورگر
            return django_response
        
        
        return Response({"message": "خطا در دریافت فایل از Paperless."}, status=response.status_code)
    except requests.RequestException as e:
        return Response({"message": f"خطا در ارتباط با Paperless: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)
       

# =========================================================
# بررسی تکراری بودن فایل (بر اساس hash) - قبل از آپلود
# =========================================================

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
        return Response({"is_duplicate": True, "message": f"این پرونده قبلاً در سیستم ثبت شده است (شماره پرونده: {existing.case_number}).", "existing_case_id": existing.id}, status=status.HTTP_409_CONFLICT)

    return Response({"is_duplicate": False}, status=status.HTTP_200_OK)


# =========================================================
# تحلیل هوشمند سند با Ollama (خلاصه + استخراج اطلاعات)
# =========================================================

@api_view(["POST"])
def analyze_document_with_ai(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    text = request.data.get("text", "")
    filename = request.data.get("filename", "سند بدون نام") # ⬅️ اضافه شد
    paperless_id = request.data.get("paperless_id", "") # ⬅️ اضافه شد
    
    if not text:
        return Response({"message": "متنی ارسال نشده است."}, status=status.HTTP_400_BAD_REQUEST)

    file_hash = request.data.get("file_hash", "")

    ollama_url = "http://localhost:11434"
    ollama_model = "aya:8b"

    # =========================================================
    # مرحله ۱: استخراج اطلاعات
    # =========================================================
    extract_text = text[:800]
    extract_prompt = f"""شما یک دستیار حقوقی فارسی‌زبان هستید. متن زیر را بخوانید و اطلاعات خواسته‌شده را استخراج کنید.

پاسخ را دقیقاً به این شکل و خط به خط بنویسید:
موضوع: (موضوع اصلی پرونده در حداکثر ۵ کلمه)
نوع پرونده: (از لیست زیر دقیقاً یکی را انتخاب کنید)
شماره پرونده: (شماره یا نامشخص)
شماره دادنامه: (شماره یا نامشخص)
تاریخ تنظیم: (تاریخ یا نامشخص)
مبلغ: (مبلغ یا نامشخص)
خواهان: (نام یا نامشخص)
خوانده: (نام یا نامشخص)
دادگاه: (نام دادگاه یا شعبه یا نامشخص)

لیست انواع پرونده:
- حقوقی خانواده (طلاق، مهریه، نفقه، حضانت، تمکین)
- حقوقی ملکی و املاک (الزام به سند، تخلیه، تصرف عدوانی)
- حقوقی قراردادها و مالی (چک، سفته، مطالبه ثمن، فسخ قرارداد)
- حقوقی خودرو (سند خودرو، فسخ معامله خودرو)
- کیفری (کلاهبرداری، سرقت، جعل، توهین، تهدید)
- اجرای اسناد و مفقودی (اجرای چک، مفقودی)

متن سند:
{extract_text}"""

    extract_payload = {
        "model": ollama_model,
        "prompt": extract_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_predict": 250, "temperature": 0.1, "repeat_penalty": 1.2}
    }

    result = {
        "main_topic": "نامشخص", "case_type": "نامشخص", "case_number": "نامشخص",
        "judgment_number": "نامشخص", "document_date": "نامشخص", "amount": "نامشخص",
        "plaintiff": "نامشخص", "defendants": "نامشخص", "court": "نامشخص", "summary": ""
    }

    try:
        print("SENDING REQUEST TO OLLAMA (EXTRACT)...")
        response1 = requests.post(
            f"{ollama_url}/api/generate", json=extract_payload, timeout=300, proxies={"http": None, "https": None}
        )
        response1.raise_for_status()
        raw1 = response1.json().get("response", "").strip()

        print("=== OLLAMA RAW RESPONSE (EXTRACT) ===")
        print(raw1)
        print("=======================================")

        # الگوهای Regex برای استخراج تمام فیلدها
        patterns = {
            "main_topic": r"موضوع\s*[:：]\s*(.+?)(?=\n|نوع پرونده|$)",
            "case_type": r"نوع\s*پرونده\s*[:：]\s*(.+?)(?=\n|شماره پرونده|$)",
            "case_number": r"شماره\s*پرونده\s*[:：]\s*(.+?)(?=\n|شماره دادنامه|$)",
            "judgment_number": r"شماره\s*دادنامه\s*[:：]\s*(.+?)(?=\n|تاریخ تنظیم|$)",
            "document_date": r"تاریخ\s*تنظیم\s*[:：]\s*(.+?)(?=\n|مبلغ|$)",
            "amount": r"مبلغ\s*[:：]\s*(.+?)(?=\n|خواهان|$)",
            "plaintiff": r"خواهان\s*[:：]\s*(.+?)(?=\n|خوانده|$)",
            "defendants": r"خوانده\s*[:：]\s*(.+?)(?=\n|دادگاه|$)",
            "court": r"دادگاه\s*[:：]\s*(.+?)(?=\n|$)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, raw1, re.DOTALL)
            if match:
                value = re.sub(r"\s+", " ", match.group(1)).strip()
                if value and value != "نامشخص":
                    result[key] = value

        # فیلتر موضوع‌های نامربوط
        invalid_topics = ["مرگ", "دعوا", "اختلاف", "نامشخص", ""]
        if result["main_topic"] in invalid_topics:
            result["main_topic"] = "پرونده حقوقی"

        if len(result["main_topic"]) > 40:
            result["main_topic"] = re.sub(r"فرزند\s+[^،\n]+", "", result["main_topic"]).strip()
            result["main_topic"] = re.sub(r"بین\s+", "", result["main_topic"]).strip()
            words = result["main_topic"].split()
            if len(words) > 5:
                result["main_topic"] = " ".join(words[:5])

        # =========================================================
        # مرحله ۲: خلاصه‌سازی
        # =========================================================
        summary_text = text[:1500]
        summary_prompt = f"""شما یک حقوقدان فارسی‌زبان هستید. متن زیر را بخوانید و یک خلاصه حقوقی بسیار کوتاه (حداکثر ۲ جمله) بنویسید.
قوانین: فقط موضوع اصلی و خواسته را بنویسید. هیچ آدرس، شماره، تاریخ یا کلمه انگلیسی نیاورید. از خودتان چیزی نسازید.

متن سند:
{summary_text}

خلاصه حقوقی:"""

        summary_payload = {
            "model": ollama_model, "prompt": summary_prompt, "stream": False, "keep_alive": "30m",
            "options": {"num_predict": 100, "temperature": 0.2, "repeat_penalty": 1.3}
        }

        print("SENDING REQUEST TO OLLAMA (SUMMARY)...")
        response2 = requests.post(
            f"{ollama_url}/api/generate", json=summary_payload, timeout=300, proxies={"http": None, "https": None}
        )
        response2.raise_for_status()
        raw2 = response2.json().get("response", "").strip()

        print("=== OLLAMA RAW RESPONSE (SUMMARY) ===")
        print(raw2)
        print("=======================================")

        if raw2:
            summary_clean = raw2.strip()
            summary_clean = re.sub(r"^خلاصه\s*حقوقی\s*[:：]\s*", "", summary_clean)
            summary_clean = re.sub(r"[^\u0600-\u06FF\s\.\،\؟\!\:\;\-\n]", "", summary_clean)
            summary_clean = re.sub(r"\s+", " ", summary_clean).strip()
            
            unwanted_phrases = [r"پلاک\s*\d+", r"طبقه\s*\d+", r"واحد\s*\d+", r"خیابان\s*[^،\.]+", r"کوچه\s*[^،\.]+", r"دفتر\s*وکالت"]
            for phrase in unwanted_phrases:
                summary_clean = re.sub(phrase, "", summary_clean)
            
            summary_clean = re.sub(r"\s+", " ", summary_clean).strip()
            result["summary"] = summary_clean if summary_clean else "خلاصه‌ای تولید نشد."
        else:
            result["summary"] = "خلاصه‌ای تولید نشد."

        # =========================================================
        # ذخیره در دیتابیس‌های جدید (تفهیم)
        # =========================================================
        if file_hash:
            try:
                user = UserProfile.objects.filter(mobile=session.mobile).first()
                
                # ۱. ذخیره سند
                doc, _ = Document.objects.update_or_create(
                    sha256_hash=file_hash,
                    defaults={
                        "user": user, 
                        "original_filename": filename, # ⬅️ تغییر کرد
                        "current_summary": result["summary"], 
                        "processing_status": "processed",
                        "external_document_id": paperless_id # ⬅️ اضافه شد
                    }
                )
                
                AIProcessingRun.objects.create(target_document=doc, task_type="summarization", model_name="aya:8b", status="completed")

                # ۲. ساخت یا پیدا کردن پرونده
                case_num = result.get("case_number")
                if case_num == "نامشخص" or not case_num:
                    case_num = f"TEMP-{file_hash[:8]}"

                new_case, _ = Case.objects.get_or_create(
                    user=user, case_number_normalized=case_num,
                    defaults={"case_number_raw": case_num, "court_name": result.get("court"), "case_type": result.get("case_type"), "current_summary": result["summary"]}
                )

                # ۳. اتصال سند به پرونده
                DocumentCaseLink.objects.get_or_create(document=doc, case=new_case)

                # ۴. ثبت خواهان و خوانده در جدول اشخاص
                plaintiff_name = result.get("plaintiff")
                if plaintiff_name and plaintiff_name != "نامشخص":
                    person, _ = Person.objects.get_or_create(user=user, display_name=plaintiff_name)
                    CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خواهان")

                defendant_name = result.get("defendants")
                if defendant_name and defendant_name != "نامشخص":
                    person, _ = Person.objects.get_or_create(user=user, display_name=defendant_name)
                    CaseParticipant.objects.get_or_create(case=new_case, person=person, role="خوانده")

                # ۵. ساخت یا پیدا کردن داستان حقوقی
                topic = result.get("main_topic", "پرونده حقوقی")
                story, _ = LegalStory.objects.get_or_create(
                    user=user, title=topic,
                    defaults={"user_context": "ایجاد خودکار", "current_summary": result["summary"], "story_status": "active"}
                )

                # ۶. اتصال پرونده به داستان
                LegalStoryCaseLink.objects.get_or_create(legal_story=story, case=new_case)

                # ⬇️ ۷. ذخیره فکت‌های استخراج‌شده در جدول DocumentExtractedFact ⬇️
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
                            document=doc,
                            field_key=key,
                            defaults={"value_raw": value, "is_current": True}
                        )
                print("=== Extracted Facts saved to DB ===")
                # ⬆️ پایان ذخیره فکت‌ها ⬆️

                print("=== Document, Case, Person, and LegalStory connected successfully ===")
            except Exception as e:
                print("خطا در ذخیره در جداول جدید:", e)

        # برگرداندن پاسخ به فرانت‌اند
        return Response({
            "summary": result["summary"], "main_topic": result["main_topic"], "case_number": result.get("case_number"),
            "plaintiff": result["plaintiff"], "defendants": result["defendants"], "court": result["court"],
            "story_id": str(story.id) if 'story' in locals() else None,
            "case_id": str(new_case.id) if 'new_case' in locals() else None,
        }, status=status.HTTP_200_OK)

    except requests.RequestException as exc:
        return Response({"message": "خطا در ارتباط با Ollama.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except (ValueError, TypeError) as exc:
        return Response({"message": "پاسخ هوش مصنوعی قابل پردازش نیست.", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


# =========================================================
# APIهای داستان‌های حقوقی
# =========================================================

@api_view(["GET", "POST"])
def legal_stories_api(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        stories = LegalStory.objects.filter(user=user).order_by('-created_at')
        serializer = LegalStorySerializer(stories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == "POST":
        title = request.data.get("title")
        context = request.data.get("user_context", "")
        if not title:
            return Response({"message": "عنوان داستان الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        story = LegalStory.objects.create(user=user, title=title, user_context=context, story_status="active")
        return Response({"message": "داستان حقوقی با موفقیت ساخته شد.", "id": story.id}, status=status.HTTP_201_CREATED)


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
        
        # دریافت اسناد و فکت‌های هر سند (مرتب‌شده بر اساس تاریخ نزولی)
        documents_data = []
        doc_links = DocumentCaseLink.objects.filter(case=c).order_by('-document__created_at')
        for dl in doc_links:
            doc = dl.document
            
            # دریافت فکت‌های این سند
            facts_data = {}
            for fact in doc.extracted_facts.filter(is_current=True):
                facts_data[fact.field_key] = fact.value_raw

            documents_data.append({
                "id": str(doc.id),
                "filename": doc.original_filename or "سند بدون نام",
                "summary": doc.current_summary or "خلاصه‌ای ثبت نشده است.",
                "date": doc.created_at.strftime("%Y/%m/%d"),
                "paperless_id": doc.external_document_id,
                "facts": facts_data # ⬅️ ارسال فکت‌ها
            })

        cases_data.append({
            "id": str(c.id),
            "title": f"پرونده {c.case_type or 'حقوقی'}",
            "case_number": c.case_number_raw,
            "court": c.court_name,
            "people": people_data,
            "plaintiff": plaintiff_name,                # ⬅️ اضافه شد
            "defendant": defendant_name,                # ⬅️ اضافه شد
            "judgment_subject": c.case_type or "",      # ⬅️ اضافه شد
            "documents": documents_data
        })

    return Response({
        "id": str(story.id),
        "title": story.title,
        "summary": story.current_summary,
        "cases": cases_data
    }, status=status.HTTP_200_OK)


# =========================================================
# دریافت لیست تمام پرونده‌ها (سازگاری با نسخه قبلی)
# =========================================================

@api_view(["GET"])
def get_all_cases(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    cases = LegalCase.objects.filter(user=user).order_by('-created_at')
    data = [{"id": c.id, "case_number": c.case_number, "title": c.title, "topic": c.topic, "status": c.status, "court": c.court, "summary": c.summary} for c in cases]
    return Response(data, status=status.HTTP_200_OK)

# ⬅️ ایمپورت مدل ابلاغیه

@api_view(["GET"])
def get_user_notices(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    
    # گرفتن تمام ابلاغیه‌های این کاربر
    notices = Notice.objects.filter(user=user).order_by('-created_at')
    
    # تبدیل به فرمت JSON برای فرستادن به ری‌اکت
    data = [
        {
            "id": n.id,
            "document_title": n.title, # یا هر اسمی که داری
            "story_title": n.story.title if n.story else "نامشخص",
            "date": n.created_at.strftime("%Y/%m/%d"),
            "time": n.created_at.strftime("%H:%M"),
            "is_active": n.is_active, # فرض کنیم این فیلد رو داری
            "hearing_date": "بیست آذر", # باید از دیتابیس بیاد
            "hearing_time": "ساعت نه",   # باید از دیتابیس بیاد
        }
        for n in notices
    ]
    return Response(data, status=status.HTTP_200_OK)
@api_view(["GET"])
def get_user_notices(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

    # دریافت ابلاغیه‌های این کاربر از دیتابیس
    notices = Notice.objects.filter(user=user).order_by('-created_at')
    
    # آماده‌سازی داده‌ها برای ارسال به فرانت‌اند
    data = []
    for n in notices:
        data.append({
            "id": n.id,
            "document_title": n.document_title,
            "story_title": n.story_title or "نامشخص",
            "date": n.date or "",
            "time": n.time or "",
            "is_active": n.is_active,
            "hearing_date": n.hearing_date or "تعیین نشده",
            "hearing_time": n.hearing_time or "",
        })
        
    return Response(data, status=status.HTTP_200_OK)

@api_view(["POST"])
def change_password(request):
    session = get_session(request)
    if not session:
        return Response({"message": "دسترسی غیرمجاز."}, status=status.HTTP_401_UNAUTHORIZED)

    user = UserProfile.objects.filter(mobile=session.mobile).first()
    if not user:
        return Response({"message": "کاربر پیدا نشد."}, status=status.HTTP_404_NOT_FOUND)

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
