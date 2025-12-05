from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
import random, datetime
from django.utils.crypto import get_random_string
from .models import Profile, UserProfile
import requests
from .models import Profile  # make sure Profile is imported

# Temporary in-memory storage for OTPs
otp_storage = {}
forgot_otp_storage = {}

def detect_timezone_from_ip(ip):
    try:
        resp = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2).json()
        return resp.get('timezone', 'UTC')
    except Exception:
        return 'UTC'

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

        # Send OTP via email
        subject = "MyCashBook - Password Reset OTP"
        message = f"Hello {user.username},\n\nYour OTP for resetting your password is: {otp}\n\nThis OTP will expire in 10 minutes.\n\nThank you!"
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

        # Store username in session
        request.session['forgot_username'] = user.username
        messages.success(request, "OTP has been sent to your registered email.")
        return redirect('verify_forgot_otp')

    return render(request, 'accounts/forgot_password.html')

# -----------------------------
# 🟠 Verify Forgot OTP View
# -----------------------------
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

        # OTP expiration check (10 minutes)
        if timezone.now() - user_data['created_at'] > datetime.timedelta(minutes=10):
            forgot_otp_storage.pop(username, None)
            messages.error(request, "OTP expired. Please resend a new one.")
            return redirect('forgot_password')

        if entered_otp == user_data['otp']:
            forgot_otp_storage.pop(username, None)
            messages.success(request, "OTP verified! Please set a new password.")
            return redirect('reset_password')
        else:
            messages.error(request, "Invalid OTP! Please try again.")
            return redirect('verify_forgot_otp')

    return render(request, 'accounts/verify_forgot_otp.html')

# -----------------------------
# 🟡 Reset Password View
# -----------------------------
def reset_password_view(request):
    username = request.session.get('forgot_username')
    if not username:
        messages.error(request, "Session expired. Please try again.")
        return redirect('forgot_password')

    user = User.objects.get(username=username)

    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, "Passwords do not match!")
            return redirect('reset_password')

        user.set_password(password1)
        user.save()
        messages.success(request, "Password reset successful! Please login with your new password.")
        # Clear session
        request.session.pop('forgot_username', None)
        return redirect('login')

    return render(request, 'accounts/reset_password.html')

# -----------------------------
# 🟢 Signup View - Generate OTP
# -----------------------------
def signup_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']

        # Password validation
        if password1 != password2:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')

        # Email uniqueness check
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered!")
            return redirect('signup')

        # Generate unique username for database (user sees display_name as entered)
        original_username = username
        while User.objects.filter(username=username).exists():
            random_suffix = get_random_string(4, allowed_chars='0123456789')
            username = f"{original_username}_{random_suffix}"

        # Create inactive user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_active = False
        user.save()

        # Detect timezone from user's IP
        user_ip = request.META.get('REMOTE_ADDR', '')
        detected_tz = detect_timezone_from_ip(user_ip)

        # Create Profile with display_name and detected timezone
        Profile.objects.create(
            user=user,
            display_name=request.POST['username'],
            timezone=detected_tz
        )

        # Generate OTP + timestamp
        otp = str(random.randint(1000, 9999))
        UserProfile.objects.create(user=user, otp=otp, otp_created_at=timezone.now())
        otp_storage[user.username] = {"otp": otp, "created_at": timezone.now()}

        # Send OTP email
        subject = "MyCashBook Email Verification OTP"
        message = f"Hello {request.POST['username']},\n\nYour 4-digit OTP for verifying your MyCashBook account is: <h2>{otp}</h2>\n\nThis OTP will expire in 10 minutes.\n\nThank you!"
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

        # Store username in session for OTP verification
        request.session['username_for_otp'] = user.username

        return redirect('verify_otp')

    return render(request, 'accounts/signup.html')


# --------------------------------
# 🟠 Verify OTP View - Check OTP
# --------------------------------
def verify_otp_view(request):
    username = request.session.get('username_for_otp')
    if not username:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    user = User.objects.get(username=username)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        user_data = otp_storage.get(username)

        if not user_data:
            messages.error(request, "OTP not found. Please resend a new one.")
            return redirect('verify_otp')

        if timezone.now() - user_data['created_at'] > datetime.timedelta(minutes=10):
            otp_storage.pop(username, None)
            messages.error(request, "OTP expired. Please resend a new one.")
            return redirect('verify_otp')

        if entered_otp == user_data['otp']:
            user.is_active = True
            user.save()
            otp_storage.pop(username, None)
            messages.success(request, f"Signup SUCCESSFUL! Please login with your credentials.")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP! Please try again.")
            return redirect('verify_otp')

    return render(request, 'accounts/verify_otp.html')



# --------------------------------
# 🔁 Resend OTP View
# --------------------------------
def resend_otp_view(request):
    username = request.session.get('username_for_otp')
    if not username:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('signup')

    # Generate new OTP
    otp = str(random.randint(1000, 9999))
    otp_storage[username] = {
        "otp": otp,
        "created_at": timezone.now()
    }

    # Send email
    subject = "MyCashBook - New OTP Code"
    message = f"Hello {user.username},\n\nYour new OTP code is: {otp}\n\nThis OTP will expire in 10 minutes.\n\nThank you!"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

    messages.success(request, "A new OTP has been sent to your email.")
    return redirect('verify_otp')


# --------------------------------
# 🟡 Login View
# --------------------------------
#def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Please verify your email via OTP before logging in.")
                return redirect('login')

            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password!")
            return redirect('login')

    return render(request, 'accounts/login.html')



def login_view(request):
    context = {}
    if request.method == 'POST':
        email = request.POST['username']  # login by email
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
                context['login_status'] = 'failed'
                context['error_message'] = "Please verify your email via OTP before logging in."
                return render(request, 'accounts/login.html', context)

            login(request, user)
            # Store display_name in session for showing in profile/header
            request.session['display_name'] = user.profile.display_name
            return redirect('dashboard')
        else:
            context['login_status'] = 'failed'
            context['error_message'] = "Invalid email or password!"
            return render(request, 'accounts/login.html', context)

    return render(request, 'accounts/login.html', context)


# --------------------------------
# 🔴 Logout View
# --------------------------------
def logout_view(request):
    logout(request)
    return redirect('login')
