from django.contrib import admin
from django.urls import path, include
from accounts import views


urlpatterns = [

    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "api/",
        include("accounts.urls")
    ),
    path('api/notices/', views.get_user_notices, name='user-notices'),
    path('api/change-password/', views.change_password, name='change-password'),
    path('api/paperless/document/<str:document_id>/preview/', views.paperless_document_preview, name='paperless_document_preview'),
]
