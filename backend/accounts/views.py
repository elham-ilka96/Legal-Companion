import hashlib
import secrets
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
)
from .serializers import UserProfileSerializer, LegalCaseSerializer


# =========================================================
# توابع کمکی
# =========================================================

def validate_mobile(mobile):
    """
    بررسی شماره موبایل ایران
    مثال صحیح:
    09123456789
    """

    return (
        isinstance(mobile, str)
        and len(mobile) == 11
        and mobile.startswith("09")
        and mobile.isdigit()
    )


def hash_token(token):
    """
    تبدیل Token به SHA256
    """
    return hashlib.sha256(token.encode()).hexdigest()


def get_session(request):
    """
    گرفتن Session از Header:

    Authorization: Bearer TOKEN
    """

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
    """
    ساخت Token جدید برای کاربر
    """

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

    # بررسی موبایل
    if not validate_mobile(mobile):

        return Response(
            {
                "message": "شماره موبایل معتبر نیست."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # mode باید signup یا login باشد
    if mode not in ["signup", "login"]:

        return Response(
            {
                "message": "حالت ورود نامعتبر است."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # بررسی وجود کاربر
    user = UserProfile.objects.filter(
        mobile=mobile
    ).first()

    # اگر ثبت نام است، کاربر نباید قبلاً وجود داشته باشد
    if mode == "signup" and user:

        return Response(
            {
                "message": "این شماره موبایل قبلاً ثبت نام کرده است."
            },
            status=status.HTTP_409_CONFLICT
        )

    # اگر login است، کاربر باید وجود داشته باشد
    if mode == "login" and not user:

        return Response(
            {
                "message": "کاربری با این شماره موبایل پیدا نشد."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # =====================================================
    # جلوگیری از ارسال کد بیشتر از هر 3 دقیقه
    # =====================================================

    rate_limit = VerificationRateLimit.objects.filter(
        mobile=mobile
    ).first()

    if rate_limit:

        elapsed = timezone.now() - rate_limit.sent_at

        if elapsed.total_seconds() < 180:

            remaining = 180 - int(elapsed.total_seconds())

            return Response(
                {
                    "message": "لطفاً کمی صبر کنید.",
                    "remaining": remaining
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    # =====================================================
    # تولید کد 6 رقمی
    # =====================================================

    code = str(secrets.randbelow(900000) + 100000)

    code_hash = hashlib.sha256(
        code.encode()
    ).hexdigest()

    # حذف کدهای قبلی
    VerificationCode.objects.filter(
        mobile=mobile
    ).delete()

    # ذخیره کد جدید
    VerificationCode.objects.create(
        mobile=mobile,
        code_hash=code_hash
    )

    # ثبت زمان ارسال
    VerificationRateLimit.objects.update_or_create(
        mobile=mobile,
        defaults={
            "sent_at": timezone.now()
        }
    )

    # =====================================================
    # فعلاً SMS واقعی نداریم
    # کد در Terminal چاپ می‌شود
    # =====================================================

    print("")
    print("=" * 50)
    print("DEVELOPMENT VERIFICATION CODE")
    print("Mobile:", mobile)
    print("Code:", code)
    print("=" * 50)
    print("")

    return Response(
        {
            "message": "کد تأیید ارسال شد."
        },
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
            {
                "message": "شماره موبایل معتبر نیست."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not code or len(str(code)) != 6:

        return Response(
            {
                "message": "کد تأیید باید 6 رقمی باشد."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # پیدا کردن کد
    verification = VerificationCode.objects.filter(
        mobile=mobile
    ).first()

    if not verification:

        return Response(
            {
                "message": "کد تأیید پیدا نشد یا منقضی شده است."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # بررسی زمان
    elapsed = timezone.now() - verification.created_at

    if elapsed.total_seconds() > 180:

        verification.delete()

        return Response(
            {
                "message": "کد تأیید منقضی شده است."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Hash کردن کد وارد شده
    submitted_hash = hashlib.sha256(
        str(code).encode()
    ).hexdigest()

    # مقایسه
    if submitted_hash != verification.code_hash:

        return Response(
            {
                "message": "کد تأیید اشتباه است."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # کد یکبار مصرف است
    verification.delete()

    # ساخت Session
    token = create_session(
        mobile,
        mode
    )

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
            {
                "message": "شماره موبایل معتبر نیست."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not password:

        return Response(
            {
                "message": "رمز عبور را وارد کنید."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    user = UserProfile.objects.filter(
        mobile=mobile
    ).first()

    if not user:

        return Response(
            {
                "message": "کاربر پیدا نشد."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # بررسی رمز
    if not user.password_hash:

        return Response(
            {
                "message": "برای این حساب رمز عبور ثبت نشده است."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not check_password(
        password,
        user.password_hash
    ):

        return Response(
            {
                "message": "شماره موبایل یا رمز عبور اشتباه است."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    # ساخت Token
    token = create_session(
        mobile,
        "login"
    )

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
            {
                "message": "دسترسی غیرمجاز."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    # کاربر فقط اطلاعات خودش را می‌تواند ببیند
    if session.mobile != mobile:

        return Response(
            {
                "message": "دسترسی غیرمجاز."
            },
            status=status.HTTP_403_FORBIDDEN
        )

    user = UserProfile.objects.filter(
        mobile=mobile
    ).first()

    if not user:

        return Response(
            {
                "message": "کاربر پیدا نشد."
            },
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
            {
                "message": "دسترسی غیرمجاز."
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    mobile = request.data.get("mobile")

    # موبایل باید با Token یکی باشد
    if session.mobile != mobile:

        return Response(
            {
                "message": "دسترسی غیرمجاز."
            },
            status=status.HTTP_403_FORBIDDEN
        )

    name = request.data.get("name")
    national_id = request.data.get("nationalId")
    age = request.data.get("age")
    gender = request.data.get("gender")
    height = request.data.get("height")
    weight = request.data.get("weight")
    password = request.data.get("password")

    # -----------------------------
    # diseases
    # -----------------------------

    diseases = request.data.get("diseases", [])

    if isinstance(diseases, str):

        import json

        try:
            diseases = json.loads(diseases)
        except Exception:
            diseases = []

    # -----------------------------
    # diseaseDetails
    # -----------------------------

    disease_details = request.data.get(
        "diseaseDetails",
        {}
    )

    if isinstance(disease_details, str):

        import json

        try:
            disease_details = json.loads(
                disease_details
            )
        except Exception:
            disease_details = {}

    # -----------------------------
    # پیدا کردن کاربر
    # -----------------------------

    user = UserProfile.objects.filter(
        mobile=mobile
    ).first()

    # اگر signup است، کاربر جدید ساخته می‌شود
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

    # -----------------------------
    # ذخیره رمز عبور
    # -----------------------------

    if password:

        if len(password) < 8:

            return Response(
                {
                    "message": "رمز عبور باید حداقل 8 کاراکتر باشد."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        user.password_hash = make_password(
            password
        )

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