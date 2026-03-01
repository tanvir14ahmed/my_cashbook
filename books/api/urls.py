from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookViewSet, TransactionViewSet, ValidateBIDView, TransferFundsView

router = DefaultRouter()
router.register(r'books',        BookViewSet,       basename='book')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),

    # ── P2P Transfer ─────────────────────────────────
    path('validate-bid/', ValidateBIDView.as_view(),    name='api_validate_bid'),
    path('transfer/',     TransferFundsView.as_view(),  name='api_transfer_funds'),
]
