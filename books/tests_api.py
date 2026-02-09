from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from books.models import Book, Transaction
from accounts.models import Profile

class MyCashbookAPITests(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='password123', email='u1@example.com')
        Profile.objects.create(user=self.user1, display_name='User One')
        
        self.user2 = User.objects.create_user(username='user2', password='password123', email='u2@example.com')
        Profile.objects.create(user=self.user2, display_name='User Two')
        
        self.book1 = Book.objects.create(user=self.user1, name='User 1 Book')
        self.book2 = Book.objects.create(user=self.user2, name='User 2 Book')

    def test_login(self):
        response = self.client.post('/api/v1/auth/login/', {'username': 'user1', 'password': 'password123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        return response.data['access']

    def test_login_by_email(self):
        # user1 has email 'u1@example.com'
        response = self.client.post('/api/v1/auth/login/', {'username': 'u1@example.com', 'password': 'password123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_book_list_unauthorized(self):
        response = self.client.get('/api/v1/books/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_book_list_authorized(self):
        token = self.test_login()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        response = self.client.get('/api/v1/books/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see user1's book
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'User 1 Book')

    def test_book_permissions(self):
        token = self.test_login()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
        # Access own book
        response = self.client.get(f'/api/v1/books/{self.book1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Access other user's book
        response = self.client.get(f'/api/v1/books/{self.book2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_transaction_creation(self):
        token = self.test_login()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
        data = {
            'amount': '100.00',
            'type': 'deposit',
            'note': 'API Test'
        }
        response = self.client.post(f'/api/v1/books/{self.book1.id}/transactions/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transaction.objects.count(), 1)
        
        # Verify balance update in book list
        response = self.client.get('/api/v1/books/')
        self.assertEqual(float(response.data[0]['balance']), 100.0)
