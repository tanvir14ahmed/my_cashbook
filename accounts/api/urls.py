from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, VerifyOTPView, ProfileView, CustomTokenObtainPairView

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='api_login'),
    path('refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('register/', RegisterView.as_view(), name='api_register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='api_verify_otp'),
    path('profile/', ProfileView.as_view(), name='api_profile'),
]
