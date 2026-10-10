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
)


router = DefaultRouter()

router.register(
    r"users",
    UserProfileViewSet
)

router.register(
    r"cases",
    LegalCaseViewSet
)


urlpatterns = [

    # -------------------------
    # APIهای قبلی React
    # -------------------------

    path(
        "send-code/",
        send_code,
        name="send-code"
    ),

    path(
        "verify-code/",
        verify_code,
        name="verify-code"
    ),

    path(
        "login/",
        login,
        name="login"
    ),

    path(
        "patients/<str:mobile>/",
        get_patient,
        name="get-patient"
    ),

    path(
        "patients/",
        save_patient,
        name="save-patient"
    ),

    # -------------------------
    # APIهای ViewSet
    # -------------------------

    path(
        "",
        include(router.urls)
    ),
]