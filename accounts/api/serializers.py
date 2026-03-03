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
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>MyCashBook OTP Verification</title>
        </head>
        <body style="font-family: Arial, sans-serif; background-color: #f7f7f7; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333333; text-align: center;">MyCashBook Account Verification</h2>
                <p>Hi <strong>{pending_user.display_name}</strong>,</p>
                <p>Thank you for signing up for <strong>MyCashBook</strong>! To complete your registration, please use the OTP below:</p>
                <p style="text-align: center; font-size: 28px; font-weight: bold; color: #2E86C1; letter-spacing: 2px; margin: 30px 0;">
                    {otp}
                </p>
                <p style="font-size: 14px; color: #555555;">This OTP is valid for <strong>10 minutes</strong>. Please do not share it with anyone.</p>
                <hr style="border: none; border-top: 1px solid #eeeeee; margin: 20px 0;">
                <p style="font-size: 12px; color: #999999; text-align: center;">
                    MyCashBook – Track your expenses wisely<br>
                    &copy; {timezone.now().year} MyCashBook. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
        send_mail(
            subject,
            f"Your OTP is {otp}",
            settings.DEFAULT_FROM_EMAIL,
            [pending_user.email],
            fail_silently=True,
            html_message=html_content,
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
