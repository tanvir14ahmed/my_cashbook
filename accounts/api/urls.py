from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    VerifyOTPView,
    ResendOTPView,
    ProfileView,
    ChangePasswordView,
    ForgotPasswordView,
    ResetPasswordView,
    CustomTokenObtainPairView,
)

urlpatterns = [
    # ── Authentication ──────────────────────────────
    path('login/',    CustomTokenObtainPairView.as_view(), name='api_login'),
    path('refresh/',  TokenRefreshView.as_view(),          name='api_token_refresh'),

    # ── Registration (OTP flow) ──────────────────────
    path('register/',   RegisterView.as_view(),   name='api_register'),
    path('verify-otp/', VerifyOTPView.as_view(),  name='api_verify_otp'),
    path('resend-otp/', ResendOTPView.as_view(),  name='api_resend_otp'),

    # ── Profile ──────────────────────────────────────
    path('profile/', ProfileView.as_view(), name='api_profile'),   # GET + PATCH

    # ── Password ─────────────────────────────────────
    path('change-password/', ChangePasswordView.as_view(), name='api_change_password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='api_forgot_password'),
    path('reset-password/',  ResetPasswordView.as_view(),  name='api_reset_password'),
]
