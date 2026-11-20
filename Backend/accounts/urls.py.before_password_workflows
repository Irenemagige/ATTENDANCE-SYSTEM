from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import views
from accounts import fingerprint_views

router = DefaultRouter()
router.register("users", views.UserManagementViewSet, basename="managed-user")
router.register("groups", views.GroupViewSet, basename="managed-group")
router.register("permissions", views.PermissionViewSet, basename="managed-permission")

urlpatterns = [
    path("auth/login/", views.login, name="login"),
    path("auth/refresh/", views.refresh, name="refresh"),
    path("auth/me/", views.me, name="me"),
    path("auth/device-login/", views.device_login, name="device_login"),
    path("auth/generate-otp/", views.generate_otp, name="generate_otp"),
    path("auth/verify-otp/", views.verify_otp, name="verify_otp"),
    path("auth/verify-device-otp/", views.verify_device_otp, name="verify_device_otp"),
    path("auth/fingerprint/verify/", fingerprint_views.fingerprint_verify, name="fingerprint_verify"),
    path("auth/test/", views.test, name="test"),
    path("user-management/", include(router.urls)),
]
