
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import LoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/accounts/login/", LoginView.as_view(), name="login"),
    path("api/accounts/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
