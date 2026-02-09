from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('api/v1/auth/', include('accounts.api.urls')),
    path('api/v1/', include('books.api.urls')),
    path('', include('books.urls')),
]
