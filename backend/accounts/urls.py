from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

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
    paperless_get_document,
    NoteViewSet,
    analyze_document_with_ai,
    check_file_duplicate,
    get_all_cases,
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

router.register(
    r"notes",
    NoteViewSet,
    basename="note"
)  


# =========================================================
# تمام مسیرهای API پروژه
# =========================================================

urlpatterns = [
    # ورود و ثبت‌نام
    path("send-code/", send_code, name="send-code"),
    path("verify-code/", verify_code, name="verify-code"),
    path("login/", login, name="login"),
    path("legal-stories/", views.legal_stories_api, name="legal-stories"),
    path("legal-stories/<uuid:story_id>/", views.get_story_details, name="get-story-details"),

    # اطلاعات کاربر
    path("patients/<str:mobile>/", get_patient, name="get-patient"),
    path("patients/", save_patient, name="save-patient"),

    # آپلود و مدیریت اسناد Paperless
    path("paperless/upload/", upload_to_paperless, name="paperless-upload"),
    path("paperless/task/<str:task_id>/", paperless_task_status, name="paperless-task-status"),
    path("paperless/search/", paperless_search, name="paperless-search"),
    path("paperless/document/<int:document_id>/", paperless_get_document, name="paperless-document"),

    # مسیرهای خودکار ViewSet
    path("", include(router.urls)),

    # تحلیل هوش مصنوعی
    path("ai/analyze/", analyze_document_with_ai, name="ai-analyze"),
    path("check-file-duplicate/", check_file_duplicate, name="check-file-duplicate"),
    path('api/notices/', views.get_user_notices, name='user-notices'),
    # ⬇️ مسیر جدید (بدون خطا)
    path("all-cases/", get_all_cases, name="get-all-cases"),
    path('api/notices/', views.get_user_notices, name='user-notices'),
    path('api/paperless/document/<str:document_id>/preview/', views.paperless_document_preview, name='paperless_document_preview'),
]