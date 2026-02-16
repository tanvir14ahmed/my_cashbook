from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Book(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    bid = models.CharField(max_length=6, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.bid:
            self.bid = self.generate_new_bid()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_new_bid():
        import random
        import string
        while True:
            new_bid = ''.join(random.choices(string.digits, k=6))
            # Import Book inside the method if needed to avoid circular imports, 
            # though here it's fine as it's a static method of the class.
            if not Book.objects.filter(bid=new_bid).exists():
                return new_bid

    def __str__(self):
        return self.name


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateField(default=timezone.now)  # store only date

    def __str__(self):
        return f"{self.type.capitalize()} - {self.amount}"

    @property
    def sign_amount(self):
        return self.amount if self.type == 'deposit' else -self.amount
