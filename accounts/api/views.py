from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from accounts.models import PendingUser, Profile, UserProfile
from django.utils import timezone
import random

from .serializers import (
    UserSerializer,
    RegisterSerializer,
    OTPSerializer,
    ResendOTPSerializer,
    CustomTokenObtainPairSerializer,
    UpdateProfileSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    VerifyForgotOTPSerializer,
    ResetPasswordSerializer,
)


# ─────────────────────────────────────────────
# AUTH: Register → OTP → Activate
# ─────────────────────────────────────────────

class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Remove any previous pending registration with same email
        PendingUser.objects.filter(email=request.data.get('email', '')).delete()
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "OTP sent to your email."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']

            try:
                pending = PendingUser.objects.get(email=email, otp=otp)
            except PendingUser.DoesNotExist:
                return Response({"error": "Invalid OTP or email."}, status=status.HTTP_400_BAD_REQUEST)

            if pending.is_expired():
                pending.delete()
                return Response({"error": "OTP expired. Please register again."}, status=status.HTTP_400_BAD_REQUEST)

            # Create user, handle duplicate usernames
            username = pending.username
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}_{get_random_string(4, allowed_chars='0123456789')}"

            user = User.objects.create_user(
                username=username,
                email=pending.email,
                password=pending.password
            )

            Profile.objects.create(
                user=user,
                display_name=pending.display_name,
                timezone=pending.timezone
            )

            pending.delete()

            # Return JWT tokens immediately so Flutter can log the user in
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Account created successfully.",
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                pending = PendingUser.objects.get(email=email)
            except PendingUser.DoesNotExist:
                return Response({"error": "No pending registration for this email."}, status=status.HTTP_404_NOT_FOUND)

            # Generate new OTP and reset timer
            new_otp = str(random.randint(100000, 999999))
            pending.otp = new_otp
            pending.created_at = timezone.now()
            pending.save()

            send_mail(
                "MyCashBook — Resend OTP",
                f"Your new OTP is {new_otp}. It expires in 10 minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
            return Response({"message": "New OTP sent to your email."})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# AUTH: Login
# ─────────────────────────────────────────────

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ─────────────────────────────────────────────
# PROFILE: Get & Update
# ─────────────────────────────────────────────

class ProfileView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Ensure profile exists for existing users
        Profile.objects.get_or_create(user=request.user, defaults={'display_name': request.user.username})
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update display_name and/or timezone."""
        profile, _ = Profile.objects.get_or_create(user=request.user, defaults={'display_name': request.user.username})
        serializer = UpdateProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated.",
                "user": UserSerializer(request.user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# PASSWORD: Change (while logged in)
# ─────────────────────────────────────────────

class ChangePasswordView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response({"message": "Password changed successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# PASSWORD: Forgot (OTP-based, 3-step flow)
# ─────────────────────────────────────────────

class ForgotPasswordView(views.APIView):
    """Step 1: Submit email → OTP is sent."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Don't reveal whether email exists for security
                return Response({"message": "If this email exists, an OTP has been sent."})

            otp = str(random.randint(100000, 999999))
            user_profile, _ = UserProfile.objects.get_or_create(user=user)
            user_profile.otp = otp
            user_profile.otp_created_at = timezone.now()
            user_profile.save()

            send_mail(
                "MyCashBook — Password Reset OTP",
                f"Your password reset OTP is {otp}. It expires in 10 minutes.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
            return Response({"message": "If this email exists, an OTP has been sent."})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(views.APIView):
    """Step 2+3: Submit email + OTP + new_password → reset password."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            otp = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']

            try:
                user = User.objects.get(email=email)
                user_profile = UserProfile.objects.get(user=user)
            except (User.DoesNotExist, UserProfile.DoesNotExist):
                return Response({"error": "Invalid request."}, status=status.HTTP_400_BAD_REQUEST)

            # Check OTP
            if user_profile.otp != otp:
                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

            # Check expiry (10 minutes)
            if user_profile.otp_created_at and (timezone.now() - user_profile.otp_created_at).seconds > 600:
                return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

            # Set new password and clear OTP
            user.set_password(new_password)
            user.save()
            user_profile.otp = None
            user_profile.otp_created_at = None
            user_profile.save()

            return Response({"message": "Password reset successfully. Please log in."})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
