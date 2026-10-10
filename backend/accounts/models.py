from django.db import models


class UserProfile(models.Model):
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, unique=True)

    # اطلاعات شخصی
    national_id = models.CharField(max_length=20, blank=True, null=True)
    age = models.CharField(max_length=10, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    height = models.CharField(max_length=10, blank=True, null=True)
    weight = models.CharField(max_length=10, blank=True, null=True)

    # اطلاعات حساب
    email = models.EmailField(blank=True, null=True)
    password_hash = models.CharField(max_length=255, blank=True, null=True)

    # اطلاعات پزشکی/تکمیلی در صورت نیاز
    diseases = models.JSONField(default=list, blank=True)
    disease_details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class LegalCase(models.Model):
    CASE_STATUS_CHOICES = [
        ('active', 'فعال'),
        ('closed', 'بسته شده'),
        ('pending', 'در انتظار'),
    ]

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='legal_cases'
    )

    title = models.CharField(max_length=200)
    case_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=CASE_STATUS_CHOICES,
        default='active'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# -----------------------------
# کد تأیید موبایل
# -----------------------------

class VerificationCode(models.Model):
    mobile = models.CharField(max_length=15)
    code_hash = models.CharField(max_length=64)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.mobile


# -----------------------------
# Session ورود کاربر
# -----------------------------

class AuthSession(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    mobile = models.CharField(max_length=15)

    mode = models.CharField(
        max_length=20,
        choices=[
            ('signup', 'ثبت نام'),
            ('login', 'ورود'),
        ]
    )

    expires_at = models.DateTimeField()

    def __str__(self):
        return self.mobile


# -----------------------------
# محدودیت ارسال کد
# -----------------------------

class VerificationRateLimit(models.Model):
    mobile = models.CharField(max_length=15, unique=True)
    sent_at = models.DateTimeField()

    def __str__(self):
        return self.mobile