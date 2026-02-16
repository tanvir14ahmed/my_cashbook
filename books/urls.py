from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Book management
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='dashboard'),
    path('add/', views.add_book_view, name='add_book'),
    path('delete/<int:book_id>/', views.delete_book_view, name='delete_book'),
    path('book/<int:book_id>/', views.book_detail_view, name='book_detail'),
    path('book/<int:book_id>/add-transaction/', views.add_transaction_view, name='add_transaction'),

    # ✏ Edit & 🗑 Delete Transaction
    path('book/<int:book_id>/edit-transaction/<int:transaction_id>/', views.edit_transaction_view, name='edit_transaction'),
    path('book/<int:book_id>/delete-transaction/<int:transaction_id>/', views.delete_transaction_view, name='delete_transaction'),
    path('book/<int:book_id>/report/', views.transaction_report_pdf, name='transaction_report_pdf'),
    path('validate-bid/', views.validate_bid, name='validate_bid'),
    path('transfer-funds/', views.transfer_funds, name='transfer_funds'),
    
]
