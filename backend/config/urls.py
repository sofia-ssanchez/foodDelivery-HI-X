from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/", include("orders.urls")),
    path("api/delivery/", include("delivery.urls")),
    path("api/pricing/", include("pricing.urls")),
]
