from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from books.models import Book, Transaction
from decimal import Decimal, InvalidOperation
from django.db import transaction as db_transaction
from django.db.models import Sum, Case, When, DecimalField, F, Value
from django.db.models.functions import Coalesce
from .serializers import BookSerializer, TransactionSerializer, ValidateBIDSerializer, TransferSerializer


# ─────────────────────────────────────────────
# Permissions
# ─────────────────────────────────────────────

class IsBookOwner(permissions.BasePermission):
    """Object-level: book must belong to the requesting user."""
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


# ─────────────────────────────────────────────
# BOOK ViewSet
# ─────────────────────────────────────────────

class BookViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated, IsBookOwner]

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get', 'post'], url_path='transactions')
    def transactions(self, request, pk=None):
        """
        GET  /api/v1/books/{id}/transactions/  — list transactions for a book
        POST /api/v1/books/{id}/transactions/  — add a new transaction
        """
        book = self.get_object()

        if request.method == 'GET':
            qs = book.transactions.all().order_by('-created_at', '-id')
            serializer = TransactionSerializer(qs, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = TransactionSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(book=book)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """
        GET /api/v1/books/{id}/report/
        Returns the PDF report for the book.
        """
        from .views import transaction_report_pdf
        return transaction_report_pdf(request, pk)


# ─────────────────────────────────────────────
# TRANSACTION ViewSet (edit / delete individual transactions)
# ─────────────────────────────────────────────

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return transactions belonging to the authenticated user's books
        return Transaction.objects.filter(book__user=self.request.user)

    def get_object(self):
        obj = super().get_object()
        # Extra safety: ensure transaction belongs to requesting user
        if obj.book.user != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not own this transaction.")
        return obj


# ─────────────────────────────────────────────
# BID VALIDATION View
# ─────────────────────────────────────────────

class ValidateBIDView(APIView):
    """
    GET /api/v1/validate-bid/?bid=XXXXXX
    Returns recipient book's owner name and book name.
    Used in Step 1 of Flutter P2P transfer flow.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = ValidateBIDSerializer(data=request.query_params)
        if serializer.is_valid():
            bid = serializer.validated_data['bid']
            book = Book.objects.get(bid=bid)
            return Response({
                'success': True,
                'owner_name': book.user.profile.display_name or book.user.username,
                'book_name': book.name,
                'bid': bid,
            })
        return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# P2P TRANSFER View
# ─────────────────────────────────────────────

class TransferFundsView(APIView):
    """
    POST /api/v1/transfer/
    Body: { sender_book_id, recipient_bid, amount, note (optional) }
    Performs a P2P transfer atomically — creates a withdrawal + a deposit.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = TransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({'success': False, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        sender_book = data['sender_book']
        recipient_book = data['recipient_book']
        amount = data['amount']
        user_note = data['note']

        # Check sender has sufficient balance
        sender_balance = sender_book.transactions.aggregate(
            balance=Coalesce(
                Sum(Case(
                    When(type='deposit', then=F('amount')),
                    When(type='withdraw', then=-F('amount')),
                    output_field=DecimalField()
                )),
                Value(0, output_field=DecimalField())
            )
        )['balance']

        if sender_balance < amount:
            return Response(
                {'success': False, 'message': 'Insufficient balance in sender book.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomic transfer
        try:
            with db_transaction.atomic():
                sender_note = f"Transfer to BID-{recipient_book.bid}"
                if user_note:
                    sender_note += f": {user_note}"

                Transaction.objects.create(
                    book=sender_book,
                    amount=amount,
                    type='withdraw',
                    note=sender_note
                )

                recipient_note = f"Transfer from BID-{sender_book.bid}"
                if user_note:
                    recipient_note += f": {user_note}"

                Transaction.objects.create(
                    book=recipient_book,
                    amount=amount,
                    type='deposit',
                    note=recipient_note
                )

            return Response({'success': True, 'message': f'Successfully transferred {amount} TK.'})

        except Exception as e:
            return Response(
                {'success': False, 'message': f'Transfer failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
