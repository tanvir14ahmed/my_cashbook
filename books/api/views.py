from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from books.models import Book, Transaction
from .serializers import BookSerializer, TransactionSerializer

class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class BookViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Book.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['get', 'post'])
    def transactions(self, request, pk=None):
        book = self.get_object()
        if request.method == 'GET':
            transactions = book.transactions.all().order_by('-created_at', '-id')
            serializer = TransactionSerializer(transactions, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = TransactionSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save(book=book)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow accessing transactions of books owned by the user
        return Transaction.objects.filter(book__user=self.request.user)

    def has_object_permission(self, request, view, obj):
        return obj.book.user == request.user
