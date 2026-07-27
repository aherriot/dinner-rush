from django.urls import path

from gateway.accounts.views import AdminSpeedView, MeView, TokenView

urlpatterns = [
    path("auth/token", TokenView.as_view(), name="auth-token"),
    path("me", MeView.as_view(), name="me"),
    path("admin/speed", AdminSpeedView.as_view(), name="admin-speed"),
]
