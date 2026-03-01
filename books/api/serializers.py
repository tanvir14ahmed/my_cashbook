from rest_framework import serializers
from books.models import Book, Transaction


# ─────────────────────────────────────────────
# TRANSACTION Serializer
# ─────────────────────────────────────────────

class TransactionSerializer(serializers.ModelSerializer):
    # FIX: sign_amount is a model @property, must use SerializerMethodField
    sign_amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        # FIX: removed 'book' from fields — it's set server-side, not by the client
        fields = ['id', 'amount', 'type', 'note', 'created_at', 'sign_amount']
        read_only_fields = ['id', 'sign_amount']

    def get_sign_amount(self, obj):
        return float(obj.sign_amount)


# ─────────────────────────────────────────────
# BOOK Serializer
# ─────────────────────────────────────────────

class BookSerializer(serializers.ModelSerializer):
    transactions_count = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Book
        # FIX: Added 'bid' — required for Flutter P2P transfer feature
        fields = ['id', 'name', 'description', 'bid', 'created_at', 'transactions_count', 'balance']
        read_only_fields = ['id', 'bid', 'created_at']

    def get_transactions_count(self, obj):
        return obj.transactions.count()

    def get_balance(self, obj):
        return float(sum(t.sign_amount for t in obj.transactions.all()))


# ─────────────────────────────────────────────
# BID VALIDATION Serializer
# ─────────────────────────────────────────────

class ValidateBIDSerializer(serializers.Serializer):
    """
    Used for GET /api/v1/validate-bid/?bid=XXXXXX
    Returns recipient book owner name and book name.
    """
    bid = serializers.CharField(max_length=6, min_length=6)

    def validate_bid(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("BID must be a 6-digit number.")
        try:
            book = Book.objects.get(bid=value)
        except Book.DoesNotExist:
            raise serializers.ValidationError("Invalid BID. Book not found.")
        return value


# ─────────────────────────────────────────────
# P2P TRANSFER Serializer
# ─────────────────────────────────────────────

class TransferSerializer(serializers.Serializer):
    """
    Used for POST /api/v1/transfer/
    Initiates a P2P money transfer from sender's book to recipient's book via BID.
    """
    sender_book_id = serializers.IntegerField()
    recipient_bid = serializers.CharField(max_length=6, min_length=6)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')

    def validate_recipient_bid(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("BID must be a 6-digit number.")
        try:
            Book.objects.get(bid=value)
        except Book.DoesNotExist:
            raise serializers.ValidationError("Recipient BID not found.")
        return value

    def validate(self, data):
        request = self.context['request']

        # Validate sender book ownership
        try:
            sender_book = Book.objects.get(id=data['sender_book_id'], user=request.user)
        except Book.DoesNotExist:
            raise serializers.ValidationError({"sender_book_id": "Sender book not found or not owned by you."})

        # Validate not same book
        if sender_book.bid == data['recipient_bid']:
            raise serializers.ValidationError({"recipient_bid": "Cannot transfer to the same book."})

        # Attach objects for use in view
        data['sender_book'] = sender_book
        data['recipient_book'] = Book.objects.get(bid=data['recipient_bid'])
        return data
