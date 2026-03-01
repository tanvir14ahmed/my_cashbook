from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from accounts.models import Profile, PendingUser
import random
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────
# READ Serializers
# ─────────────────────────────────────────────

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['display_name', 'timezone']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']


# ─────────────────────────────────────────────
# AUTH: Register & OTP
# ─────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = PendingUser
        # FIX: Added 'display_name' — required for Flutter sign-up form
        fields = ['username', 'email', 'password', 'display_name', 'timezone']

    def create(self, validated_data):
        otp = str(random.randint(100000, 999999))
        validated_data['otp'] = otp
        pending_user = PendingUser.objects.create(**validated_data)

        subject = "MyCashBook Email Verification OTP"
        message = f"Your OTP is {otp}. It expires in 10 minutes."
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [pending_user.email],
            fail_silently=True,
        )
        return pending_user


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()


# ─────────────────────────────────────────────
# AUTH: Login (Custom — supports email or username)
# ─────────────────────────────────────────────

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field)

        # Allow login with email address
        try:
            user = User.objects.get(email=username_or_email)
            attrs[self.username_field] = user.username
        except User.DoesNotExist:
            pass

        return super().validate(attrs)


# ─────────────────────────────────────────────
# PROFILE: Update
# ─────────────────────────────────────────────

class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Used for PATCH /api/v1/auth/profile/
    Allows updating display_name and timezone only.
    """
    class Meta:
        model = Profile
        fields = ['display_name', 'timezone']


# ─────────────────────────────────────────────
# PASSWORD: Change (while logged in)
# ─────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


# ─────────────────────────────────────────────
# PASSWORD: Forgot / Reset (OTP-based)
# ─────────────────────────────────────────────

class ForgotPasswordSerializer(serializers.Serializer):
    """Step 1: User submits email → OTP is sent."""
    email = serializers.EmailField()


class VerifyForgotOTPSerializer(serializers.Serializer):
    """Step 2: User submits email + OTP → gets a temporary reset token."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class ResetPasswordSerializer(serializers.Serializer):
    """Step 3: User submits new password + reset token."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=6)
