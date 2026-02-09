from rest_framework import serializers
from books.models import Book, Transaction

class TransactionSerializer(serializers.ModelSerializer):
    created_at = serializers.ReadOnlyField()
    class Meta:
        model = Transaction
        fields = ['id', 'book', 'amount', 'type', 'note', 'created_at', 'sign_amount']
        read_only_fields = ['id', 'book']

class BookSerializer(serializers.ModelSerializer):
    transactions_count = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Book
        fields = ['id', 'user', 'name', 'description', 'created_at', 'transactions_count', 'balance']
        read_only_fields = ['id', 'user', 'created_at']

    def get_transactions_count(self, obj):
        return obj.transactions.count()

    def get_balance(self, obj):
        return sum(t.sign_amount for t in obj.transactions.all())
