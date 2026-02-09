from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from accounts.models import PendingUser, Profile
from .serializers import UserSerializer, RegisterSerializer, OTPSerializer, CustomTokenObtainPairSerializer
from django.utils.crypto import get_random_string

class RegisterView(views.APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
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
                return Response({"error": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Create user
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
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "User registered successfully.",
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(views.APIView):
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
