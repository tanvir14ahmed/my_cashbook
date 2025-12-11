from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta

from django.db import models
from django.utils import timezone
from datetime import timedelta


class PendingUser(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=200)  # Hashed password recommended
    display_name = models.CharField(max_length=150)
    timezone = models.CharField(max_length=100, default='UTC')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_otp')
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=150)  # Stores the name user entered
    timezone = models.CharField(max_length=64, default='UTC')  # store tz name

    def __str__(self):
        return self.display_name  # Shows user-friendly name
