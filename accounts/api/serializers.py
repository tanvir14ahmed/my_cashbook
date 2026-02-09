from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from accounts.models import Profile, PendingUser
import random
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['display_name', 'timezone']

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = PendingUser
        fields = ['username', 'email', 'password', 'timezone']

    def create(self, validated_data):
        otp = str(random.randint(1000, 9999))
        validated_data['otp'] = otp
        pending_user = PendingUser.objects.create(**validated_data)
        
        # Send OTP Email (simplified for now, using logic from views.py)
        subject = "MyCashBook Email Verification OTP"
        message = f"Your OTP is {otp}"
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

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get(self.username_field)
        
        # Check if the provided username is actually an email
        try:
            user = User.objects.get(email=username_or_email)
            attrs[self.username_field] = user.username
        except User.DoesNotExist:
            pass
            
        return super().validate(attrs)
