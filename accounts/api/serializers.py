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
    username = serializers.CharField(required=False)

    class Meta:
        model = PendingUser
        fields = ['email', 'password', 'display_name', 'timezone', 'username']

    def create(self, validated_data):
        email = validated_data.get('email')
        # Auto-generate username from email prefix
        base_username = email.split('@')[0].lower()
        import random
        import string
        
        # Ensure it's unique enough for PendingUser
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        username = f"{base_username}_{random_suffix}"
        
        validated_data['username'] = username
        otp = str(random.randint(100000, 999999))
        validated_data['otp'] = otp
        
        pending_user = super().create(validated_data)
        
        from django.core.mail import EmailMultiAlternatives
        from django.utils.html import strip_tags

        subject = "MyCashBook — Email Verification"
        text_content = f"Hi {pending_user.display_name}, your MyCashBook verification code is: {otp}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                .container {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #1a1a1a 0%, #333333 100%); padding: 40px 20px; text-align: center; }}
                .content {{ padding: 40px; color: #333333; line-height: 1.6; }}
                .otp-box {{ background-color: #f8f9fa; border: 2px dashed #e0e0e0; border-radius: 12px; padding: 20px; text-align: center; margin: 30px 0; }}
                .otp-code {{ font-size: 36px; font-weight: bold; color: #ff9800; letter-spacing: 4px; }}
                .footer {{ background-color: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #999999; }}
                .logo {{ color: #ffffff; font-size: 24px; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 2px; }}
            </style>
        </head>
        <body style="margin: 0; padding: 20px; background-color: #f4f4f4;">
            <div class="container">
                <div class="header">
                    <div class="logo">MyCashBook</div>
                    <div style="color: #ff9800; font-size: 14px; font-weight: 500;">PREMIUM EXPENSE TRACKING</div>
                </div>
                <div class="content">
                    <h2 style="margin-top: 0; color: #1a1a1a;">Account Verification</h2>
                    <p>Hi <strong>{pending_user.display_name}</strong>,</p>
                    <p>Welcome to MyCashBook! We're excited to help you take control of your finances. To get started, please verify your email address using the code below:</p>
                    <div class="otp-box">
                        <div class="otp-code">{otp}</div>
                    </div>
                    <p style="font-size: 14px; color: #666666;">This verification code is valid for <strong>10 minutes</strong>. If you didn't request this, you can safely ignore this email.</p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} MyCashBook. All rights reserved.</p>
                    <p>This is an automated message, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [pending_user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
        
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
