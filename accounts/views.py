from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
import random, datetime
from django.utils.crypto import get_random_string
from .models import Profile, UserProfile, PendingUser   # ← NEW
import requests
from datetime import timedelta
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def cleanup_expired_pending_users():
    expiration_time = timezone.now() - timedelta(minutes=10)
    PendingUser.objects.filter(created_at__lt=expiration_time).delete()

# -----------------------------
# 🔵 DETECT TIMEZONE
# -----------------------------
def detect_timezone_from_ip(ip):
    try:
        resp = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2).json()
        return resp.get('timezone', 'UTC')
    except Exception:
        return 'UTC'

# -----------------------------
# 🔵 FORGOT PASSWORD (unchanged)
# -----------------------------
otp_storage = {}
forgot_otp_storage = {}

def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Email/User is not registered yet!")
            return redirect('forgot_password')

        # Generate OTP
        otp = str(random.randint(1000, 9999))
        forgot_otp_storage[user.username] = {
            "otp": otp,
            "created_at": timezone.now()
        }

        # 📧 Professional HTML email
        subject = "MyCashBook - Password Reset OTP"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>MyCashBook Password Reset OTP</title>
        </head>
        <body style="font-family: Arial, sans-serif; background-color: #f7f7f7; padding: 20px;">
            <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #333333; text-align: center;">Password Reset Request</h2>
                <p>Hi <strong>{user.username}</strong>,</p>
                <p>We received a request to reset your <strong>MyCashBook</strong> password. Use the OTP below to reset your password:</p>
                <p style="text-align: center; font-size: 28px; font-weight: bold; color: #E74C3C; letter-spacing: 2px; margin: 30px 0;">
                    {otp}
                </p>
                <p style="font-size: 14px; color: #555555;">This OTP is valid for <strong>10 minutes</strong>. Do not share it with anyone.</p>
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
            subject=subject,
            message=f"Your OTP for password reset is {otp}",  # plain-text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content
        )

        # Store username in session for OTP verification
        request.session['forgot_username'] = user.username
        messages.success(request, "OTP has been sent to your registered email.")
        return redirect('verify_forgot_otp')

    return render(request, 'accounts/forgot_password.html')


def verify_forgot_otp_view(request):
    username = request.session.get('forgot_username')
    if not username:
        messages.error(request, "Session expired. Please try again.")
        return redirect('forgot_password')

    user = User.objects.get(username=username)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        user_data = forgot_otp_storage.get(username)

        if not user_data:
            messages.error(request, "OTP not found. Please resend a new one.")
            return redirect('verify_forgot_otp')

        if timezone.now() - user_data['created_at'] > datetime.timedelta(minutes=10):
            forgot_otp_storage.pop(username, None)
            messages.error(request, "OTP expired. Please resend a new one.")
            return redirect('forgot_password')

        if entered_otp == user_data['otp']:
            forgot_otp_storage.pop(username, None)
            messages.success(request, "OTP verified! Please set a new password.")
            return redirect('reset_password')
        else:
            messages.error(request, "Invalid OTP!")
            return redirect('verify_forgot_otp')

    return render(request, 'accounts/verify_forgot_otp.html')


def reset_password_view(request):
    username = request.session.get('forgot_username')
    if not username:
        messages.error(request, "Session expired. Please try again.")
        return redirect('forgot_password')

    user = User.objects.get(username=username)

    if request.method == 'POST':
        p1 = request.POST.get('password1')
        p2 = request.POST.get('password2')

        if p1 != p2:
            messages.error(request, "Passwords do not match!")
            return redirect('reset_password')

        user.set_password(p1)
        user.save()
        request.session.pop('forgot_username', None)
        messages.success(request, "Password reset successful!")
        return redirect('login')

    return render(request, 'accounts/reset_password.html')


# ============================================================
# ============================================================
# 🟢 NEW SIGNUP FLOW USING PendingUser
# ============================================================
# ============================================================

# -----------------------------
# 🟢 SIGNUP → CREATE PendingUser
# -----------------------------
def signup_view(request):
    cleanup_expired_pending_users()
    
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        if password1 != password2:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address! Please enter a valid email.")
            return redirect('signup')
        
        # 🔥 Clear old pending entry for same email
        PendingUser.objects.filter(email=email).delete()

        # ❗ If email already used in real user table
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered!")
            return redirect('signup')

        # Detect client timezone
        user_ip = request.META.get('REMOTE_ADDR', '')
        detected_tz = detect_timezone_from_ip(user_ip)

        # Generate OTP
        otp = str(random.randint(1000, 9999))

        # 🔥 Save temporary user
        PendingUser.objects.create(
            username=username,
            email=email,
            password=password1,
            display_name=username,
            timezone=detected_tz,
            otp=otp
        )

        # 📧 Send professional HTML OTP email
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
                <p>Hi <strong>{username}</strong>,</p>
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
            subject=subject,
            message=f"Your OTP is {otp}",  # fallback for plain text email clients
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_content
        )

        # Save email for verification
        request.session['pending_email'] = email

        return redirect('verify_otp')

    return render(request, 'accounts/signup.html')


# -----------------------------
# 🟠 VERIFY OTP → CREATE REAL USER
# -----------------------------
from django.utils.crypto import get_random_string

def verify_otp_view(request):
    cleanup_expired_pending_users()
    email = request.session.get('pending_email')

    if not email:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    try:
        pending = PendingUser.objects.get(email=email)
    except PendingUser.DoesNotExist:
        messages.error(request, "No pending registration found!")
        return redirect('signup')

    if request.method == 'POST':
        entered = request.POST.get('otp')

        if entered != pending.otp:
            messages.error(request, "Invalid OTP!")
            return redirect('verify_otp')

        # 🔥 Generate a unique username for the real User
        username = pending.username
        original_username = username
        while User.objects.filter(username=username).exists():
            random_suffix = get_random_string(4, allowed_chars='0123456789')
            username = f"{original_username}_{random_suffix}"

        # 🔥 Create real Django user
        user = User.objects.create_user(
            username=username,
            email=pending.email,
            password=pending.password
        )

        # Create Profile (display_name keeps original name)
        Profile.objects.create(
            user=user,
            display_name=pending.display_name,
            timezone=pending.timezone
        )

        # Delete temporary PendingUser
        pending.delete()

        messages.success(request, "Signup successful! Please login.")
        return redirect('login')

    return render(request, 'accounts/verify_otp.html')



# -----------------------------
# 🔁 RESEND OTP
# -----------------------------
def resend_otp_view(request):
    email = request.session.get('pending_email')

    if not email:
        messages.error(request, "Session expired! Please start signup again.")
        return redirect('signup')

    try:
        pending = PendingUser.objects.get(email=email)
    except PendingUser.DoesNotExist:
        messages.error(request, "Pending user not found! Please sign up again.")
        return redirect('signup')

    # Generate new OTP
    new_otp = str(random.randint(1000, 9999))
    pending.otp = new_otp
    pending.save()

    # 📧 Send professional HTML OTP email
    subject = "MyCashBook - New OTP Code"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>MyCashBook OTP Verification</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f7f7f7; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color: #333333; text-align: center;">MyCashBook OTP Resend</h2>
            <p>Hi <strong>{pending.username}</strong>,</p>
            <p>You requested a new OTP to verify your <strong>MyCashBook</strong> account. Use the OTP below to complete your signup:</p>
            <p style="text-align: center; font-size: 28px; font-weight: bold; color: #E74C3C; letter-spacing: 2px; margin: 30px 0;">
                {new_otp}
            </p>
            <p style="font-size: 14px; color: #555555;">This OTP is valid for <strong>10 minutes</strong>. Do not share it with anyone.</p>
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
        subject=subject,
        message=f"Your new OTP is {new_otp}",  # fallback for plain text clients
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_content
    )

    messages.success(request, "A new OTP has been sent to your email!")
    return redirect('verify_otp')


# ============================================================
# ======================= LOGIN + LOGOUT ======================
# ============================================================

def login_view(request):
    context = {}
    if request.method == 'POST':
        email = request.POST['username']
        password = request.POST['password']

        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            context['login_status'] = 'failed'
            context['error_message'] = "Invalid email or password!"
            return render(request, 'accounts/login.html', context)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                context['error_message'] = "Please verify your email first."
                return render(request, 'accounts/login.html', context)

            login(request, user)
            request.session['display_name'] = user.profile.display_name
            return redirect('dashboard')

        context['error_message'] = "Invalid email or password!"
        return render(request, 'accounts/login.html', context)

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')
