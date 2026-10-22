import hashlib
import secrets
import os
import json
import requests
from django.conf import settings
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import (
    UserProfile,
    LegalCase,
    VerificationCode,
    AuthSession,
    VerificationRateLimit,
    Note,
)
from .serializers import (
    UserProfileSerializer,
    LegalCaseSerializer,
    NoteSerializer,  
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
        return Response(
            {"message": "شماره موبایل معتبر نیست."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if mode not in ["signup", "login"]:
        return Response(
            {"message": "حالت ورود نامعتبر است."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = UserProfile.objects.filter(mobile=mobile).first()

    if mode == "signup" and user:
        return Response(
            {"message": "این شماره موبایل قبلاً ثبت نام کرده است."},
            status=status.HTTP_409_CONFLICT
        )

    if mode == "login" and not user:
        return Response(
            {"message": "کاربری با این شماره موبایل پیدا نشد."},
            status=status.HTTP_404_NOT_FOUND
        )

    rate_limit = VerificationRateLimit.objects.filter(mobile=mobile).first()
    if rate_limit:
        elapsed = timezone.now() - rate_limit.sent_at
        if elapsed.total_seconds() < 180:
            remaining = 180 - int(elapsed.total_seconds())
            return Response(
                {"message": "لطفاً کمی صبر کنید.", "remaining": remaining},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    code = str(secrets.randbelow(900000) + 100000)
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    VerificationCode.objects.filter(mobile=mobile).delete()
    VerificationCode.objects.create(mobile=mobile, code_hash=code_hash)
    VerificationRateLimit.objects.update_or_create(
        mobile=mobile,
        defaults={"sent_at": timezone.now()}
    )

    print("")
    print("=" * 50)
    print("DEVELOPMENT VERIFICATION CODE")
    print("Mobile:", mobile)
    print("Code:", code)
    print("=" * 50)
    print("")

    return Response(
        {"message": "کد تأیید ارسال شد."},
        status=status.HTTP_200_OK
    )


# =========================================================
# بررسی کد تأیید
# =========================================================

@api_view(["POST"])
def verify_code(request):
    mobile = request.data.get("mobile")
    code = request.data.get("code")
    mode = request.data.get("mode")

    if not validate_mobile(mobile):
        return Response(
            {"message": "شماره موبایل معتبر نیست."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not code or len(str(code)) != 6:
        return Response(
            {"message": "کد تأیید باید 6 رقمی باشد."},
            status=status.HTTP_400_BAD_REQUEST
        )

    verification = VerificationCode.objects.filter(mobile=mobile).first()
    if not verification:
        return Response(
            {"message": "کد تأیید پیدا نشد یا منقضی شده است."},
            status=status.HTTP_400_BAD_REQUEST
        )

    elapsed = timezone.now() - verification.created_at
    if elapsed.total_seconds() > 180:
        verification.delete()
        return Response(
            {"message": "کد تأیید منقضی شده است."},
            status=status.HTTP_400_BAD_REQUEST
        )

    submitted_hash = hashlib.sha256(str(code).encode()).hexdigest()
    if submitted_hash != verification.code_hash:
        return Response(
            {"message": "کد تأیید اشتباه است."},
            status=status.HTTP_400_BAD_REQUEST
        )

    verification.delete()
    token = create_session(mobile, mode)

    return Response(
        {
            "verified": True,
            "message": "شماره موبایل تأیید شد.",
            "token": token
        },
        status=status.HTTP_200_OK
    )


# =========================================================
# Login با شماره موبایل + رمز عبور
# =========================================================

@api_view(["POST"])
def login(request):
    mobile = request.data.get("mobile")
    password = request.data.get("password")

    if not validate_mobile(mobile):
        return Response(
            {"message": "شماره موبایل معتبر نیست."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not password:
        return Response(
            {"message": "رمز عبور را وارد کنید."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        return Response(
            {"message": "کاربر پیدا نشد."},
            status=status.HTTP_404_NOT_FOUND
        )

    if not user.password_hash:
        return Response(
            {"message": "برای این حساب رمز عبور ثبت نشده است."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not check_password(password, user.password_hash):
        return Response(
            {"message": "شماره موبایل یا رمز عبور اشتباه است."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    token = create_session(mobile, "login")

    return Response(
        {
            "token": token,
            "patient": {
                "id": user.id,
                "mobile": user.mobile,
                "name": user.full_name,
                "nationalId": user.national_id,
                "age": user.age,
                "gender": user.gender,
                "height": user.height,
                "weight": user.weight,
                "diseases": user.diseases,
                "diseaseDetails": user.disease_details,
            }
        },
        status=status.HTTP_200_OK
    )


# =========================================================
# گرفتن اطلاعات بیمار
# =========================================================

@api_view(["GET"])
def get_patient(request, mobile):
    session = get_session(request)
    if not session:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if session.mobile != mobile:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_403_FORBIDDEN
        )

    user = UserProfile.objects.filter(mobile=mobile).first()
    if not user:
        return Response(
            {"message": "کاربر پیدا نشد."},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response(
        {
            "id": user.id,
            "mobile": user.mobile,
            "name": user.full_name,
            "nationalId": user.national_id,
            "age": user.age,
            "gender": user.gender,
            "height": user.height,
            "weight": user.weight,
            "diseases": user.diseases,
            "diseaseDetails": user.disease_details,
            "email": user.email,
        },
        status=status.HTTP_200_OK
    )


# =========================================================
# ثبت / بروزرسانی اطلاعات بیمار
# =========================================================

@api_view(["POST"])
def save_patient(request):
    session = get_session(request)
    if not session:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    mobile = request.data.get("mobile")
    if session.mobile != mobile:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_403_FORBIDDEN
        )

    name = request.data.get("name")
    national_id = request.data.get("nationalId")
    age = request.data.get("age")
    gender = request.data.get("gender")
    height = request.data.get("height")
    weight = request.data.get("weight")
    password = request.data.get("password")

    diseases = request.data.get("diseases", [])
    if isinstance(diseases, str):
        try:
            diseases = json.loads(diseases)
        except Exception:
            diseases = []

    disease_details = request.data.get("diseaseDetails", {})
    if isinstance(disease_details, str):
        try:
            disease_details = json.loads(disease_details)
        except Exception:
            disease_details = {}

    user = UserProfile.objects.filter(mobile=mobile).first()

    if not user:
        user = UserProfile(
            mobile=mobile,
            full_name=name or "",
            national_id=national_id,
            age=age,
            gender=gender,
            height=height,
            weight=weight,
            diseases=diseases,
            disease_details=disease_details,
        )
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
            return Response(
                {"message": "رمز عبور باید حداقل 8 کاراکتر باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.password_hash = make_password(password)

    user.save()

    return Response(
        {
            "message": "اطلاعات با موفقیت ذخیره شد.",
            "patient": {
                "id": user.id,
                "mobile": user.mobile,
                "name": user.full_name,
                "nationalId": user.national_id,
                "age": user.age,
                "gender": user.gender,
                "height": user.height,
                "weight": user.weight,
                "diseases": user.diseases,
                "diseaseDetails": user.disease_details,
            }
        },
        status=status.HTTP_200_OK
    )


# =========================================================
# آپلود سند به Paperless
# =========================================================

@api_view(["POST"])
def upload_to_paperless(request):
    session = get_session(request)
    if not session:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    file = request.FILES.get("document")
    if not file:
        return Response(
            {"message": "فایلی ارسال نشده است."},
            status=status.HTTP_400_BAD_REQUEST
        )

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in allowed_extensions:
        return Response(
            {"message": "فرمت فایل مجاز نیست."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if file.size == 0 or file.size > 10 * 1024 * 1024:
        return Response(
            {"message": "حجم فایل باید بیشتر از صفر و حداکثر ۱۰ مگابایت باشد."},
            status=status.HTTP_400_BAD_REQUEST
        )

    file_path = default_storage.save(f"temp/{file.name}", file)
    full_path = default_storage.path(file_path)

    try:
        result = upload_document(
            full_path,
            title=request.data.get("title", file.name)
        )
        if result.get("success"):
            return Response(
                {
                    "message": "سند برای پردازش به Paperless ارسال شد.",
                    "task_id": result.get("task_id")
                },
                status=status.HTTP_200_OK
            )
        return Response(
            {
                "message": "خطا در آپلود سند.",
                "error": result.get("error", "خطای نامشخص")
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
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
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        task_data = get_task_status(task_id)
    except Exception as exc:
        return Response(
            {"message": f"خطا در دریافت وضعیت تسک: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    if task_data:
        return Response(task_data, status=status.HTTP_200_OK)
    return Response(
        {"message": "تسک پیدا نشد."},
        status=status.HTTP_404_NOT_FOUND
    )


# =========================================================
# جستجو در اسناد Paperless
# =========================================================

@api_view(["GET"])
def paperless_search(request):
    session = get_session(request)
    if not session:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    query = request.query_params.get('q', '')
    if not query:
        return Response(
            {"message": "عبارت جستجو ارسال نشده."},
            status=status.HTTP_400_BAD_REQUEST
        )

    results = search_documents(query)
    if results:
        return Response(results, status=status.HTTP_200_OK)
    return Response(
        {"message": "خطا در جستجو."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


# =========================================================
# دریافت یک سند از Paperless
# =========================================================

@api_view(["GET"])
def paperless_get_document(request, document_id):
    session = get_session(request)
    if not session:
        return Response(
            {"message": "دسترسی غیرمجاز."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        response = requests.get(
            f"{settings.PAPERLESS_URL}/api/documents/{document_id}/",
            headers={"Authorization": f"Token {settings.PAPERLESS_API_TOKEN}"},
            timeout=15,
        )
        if response.status_code == 200:
            return Response(response.json(), status=status.HTTP_200_OK)
        return Response(
            {"message": "سند پیدا نشد."},
            status=status.HTTP_404_NOT_FOUND
        )
    except requests.RequestException:
        return Response(
            {"message": "خطا در ارتباط با Paperless هنگام دریافت سند."},
            status=status.HTTP_502_BAD_GATEWAY
        )
    except ValueError:
        return Response(
            {"message": "پاسخ سند از Paperless قابل خواندن نیست."},
            status=status.HTTP_502_BAD_GATEWAY
        )