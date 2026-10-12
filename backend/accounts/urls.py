
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserProfileViewSet,
    LegalCaseViewSet,
    send_code,
    verify_code,
    login,
    get_patient,
    save_patient,
    upload_to_paperless,
    paperless_task_status,
    paperless_search,
)


# =========================================================
# مسیرهای ViewSet
# =========================================================

router = DefaultRouter()

router.register(
    r"users",
    UserProfileViewSet
)

router.register(
    r"cases",
    LegalCaseViewSet
)


# =========================================================
# تمام مسیرهای API پروژه
# =========================================================

urlpatterns = [
    # ورود و ثبت‌نام
    path("send-code/", send_code, name="send-code"),
    path("verify-code/", verify_code, name="verify-code"),
    path("login/", login, name="login"),

    # اطلاعات کاربر
    path(
        "patients/<str:mobile>/",
        get_patient,
        name="get-patient",
    ),
    path(
        "patients/",
        save_patient,
        name="save-patient",
    ),

    # آپلود و مدیریت اسناد Paperless
    path(
        "paperless/upload/",
        upload_to_paperless,
        name="paperless-upload",
    ),
    path(
        "paperless/task/<str:task_id>/",
        paperless_task_status,
        name="paperless-task-status",
    ),
    path(
        "paperless/search/",
        paperless_search,
        name="paperless-search",
    ),

    # مسیرهای خودکار ViewSet
    path("", include(router.urls)),
]
