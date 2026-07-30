from django.urls import path

from front_of_house.accounts.views import AdminSpeedView, MeView, SpeedView, TokenView

urlpatterns = [
    path("auth/token", TokenView.as_view(), name="auth-token"),
    path("me", MeView.as_view(), name="me"),
    path("speed", SpeedView.as_view(), name="speed"),
    path("admin/speed", AdminSpeedView.as_view(), name="admin-speed"),
]
