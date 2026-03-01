<div align="center">

# 💰 MyCashBook

**A full-stack personal finance management application**
<br/>
Built with **Django 5** · **Django REST Framework** · **JWT Auth** · **ReportLab PDF**

[![Live Demo](https://img.shields.io/badge/Live-Demo-orange?style=for-the-badge&logo=google-chrome)](https://mycashbook.codelab-by-tnv.top)
[![GitHub](https://img.shields.io/badge/GitHub-tanvir14ahmed-black?style=for-the-badge&logo=github)](https://github.com/tanvir14ahmed)
[![Django](https://img.shields.io/badge/Django-5.2.8-green?style=for-the-badge&logo=django)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.16-red?style=for-the-badge)](https://www.django-rest-framework.org)

</div>

---

## 📖 Overview

**MyCashBook** is a feature-rich, production-ready personal finance management app. It supports a full web UI and a **REST API** (designed for Flutter and other mobile clients), featuring P2P money transfers via unique Book IDs (BIDs), OTP-based email verification, JWT authentication, running balance calculation, and professional PDF statement generation.

---

## ✨ Features

### 🔐 Authentication & Accounts
- **OTP Email Verification** during signup (10-minute expiry)
- **Login with Email or Username**
- **JWT Access + Refresh Tokens** (SimpleJWT)
- **Forgot Password** with OTP reset flow (3-step)
- **Change Password** while logged in
- **User Profile** — custom display name and timezone
- **Session-based auth** for the web UI (24-hour session)

### 📚 Books
- Create multiple **cashbooks** for different purposes (e.g., Personal, Business, Savings)
- Each book has a unique **6-digit BID (Book ID)** for P2P transfers
- View **total balance**, transaction count, and full history per book
- Search books by name on the dashboard
- Paginated book listing (12 per page)

### 💸 Transactions
- Add **Deposit** or **Withdraw** transactions with a date and optional note
- **Edit** or **Delete** any transaction
- **Running balance** calculated accurately per transaction (chronological order)
- Pagination: 20 transactions per page

### 💳 P2P Money Transfer (Send Money)
- Send money to **any book** using its BID
- **Real-time BID validation** — see recipient name and book before confirming
- Atomic transfer: Withdrawal from sender + Deposit to recipient in one transaction
- **Insufficient balance** protection
- Auto-generated notes on both sides (e.g., `Transfer to BID-123456`)

### 📄 PDF Reports
- Download professional **bank-statement-style PDF** reports
- Filter by **custom date range** or download all transactions
- Shows: Date, Type, Amount, Running Balance, Note
- Summary section: Total Deposits, Total Withdrawals, Transaction Count
- Auto-generated filename with timestamp

### 🎨 UI/UX
- **Premium Orange Theme** — subtle metallic tones in both light and dark mode
- **Dark Mode toggle** with localStorage persistence
- **Glowing BID badges** with pulse animation on the dashboard
- **Soothing transfer animation** (bouncing coin + rotating halo) during P2P transfers
- Fully **responsive** — desktop, tablet, and mobile
- Inline modals for Add, Edit, Delete, Report, and Send Money actions

### 📱 REST API (Flutter / Mobile Ready)
- Full DRF API at `/api/v1/`
- JWT bearer token authentication
- All web app features exposed as JSON endpoints
- See the [API Reference](#-api-reference) section below

---

## 🏗️ Project Structure

```
my_cashbook/
│
├── accounts/                   # User auth, profile, OTP
│   ├── api/
│   │   ├── serializers.py      # RegisterSerializer, ProfileSerializer, etc.
│   │   ├── views.py            # API views for auth & profile
│   │   └── urls.py             # /api/v1/auth/ routes
│   ├── migrations/
│   ├── models.py               # PendingUser, UserProfile, Profile
│   ├── views.py                # Web views (signup, login, OTP, etc.)
│   └── urls.py                 # /accounts/ web routes
│
├── books/                      # Books, transactions, transfers
│   ├── api/
│   │   ├── serializers.py      # BookSerializer, TransactionSerializer, TransferSerializer, etc.
│   │   ├── views.py            # BookViewSet, TransactionViewSet, ValidateBIDView, TransferFundsView
│   │   └── urls.py             # /api/v1/ routes
│   ├── migrations/
│   ├── models.py               # Book, Transaction
│   ├── views.py                # Web views (dashboard, book_detail, PDF, transfer, etc.)
│   └── urls.py                 # Web routes
│
├── core/
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Root URL configuration
│   └── wsgi.py
│
├── static/                     # Static files (CSS, JS, images)
├── templates/                  # HTML templates
│   ├── accounts/               # login, signup, OTP, forgot password pages
│   └── books/                  # dashboard, book_detail, add_transaction, report
│
├── .cpanel.yml                 # cPanel auto-deployment configuration
├── .env                        # Environment variables (not committed)
├── manage.py
├── requirements.txt
└── Procfile                    # For platform deployments (e.g., Heroku)
```

---

## 💾 Data Models

### `Book`
| Field | Type | Notes |
|-------|------|-------|
| `user` | ForeignKey(User) | Owner of the book |
| `name` | CharField | Book name |
| `description` | TextField | Optional |
| `bid` | CharField(6) | Auto-generated unique 6-digit ID |
| `created_at` | DateTimeField | Auto |

### `Transaction`
| Field | Type | Notes |
|-------|------|-------|
| `book` | ForeignKey(Book) | Linked book |
| `amount` | DecimalField | Positive value |
| `type` | CharField | `deposit` or `withdraw` |
| `note` | CharField | Optional |
| `created_at` | DateField | Transaction date |

### `Profile`
| Field | Type | Notes |
|-------|------|-------|
| `user` | OneToOneField(User) | |
| `display_name` | CharField | User-chosen name |
| `timezone` | CharField | e.g., `Asia/Dhaka` |

---

## 🌐 API Reference

> **Base URL:** `https://mycashbook.codelab-by-tnv.top/api/v1/`
> **Auth:** All 🔐 endpoints require `Authorization: Bearer <access_token>` header.

### Auth Endpoints — `/api/v1/auth/`

| Endpoint | Method | Auth | Request Body | Response |
|---|---|---|---|---|
| `register/` | POST | Public | `username, email, password, display_name, timezone` | OTP sent to email |
| `verify-otp/` | POST | Public | `email, otp` | `access, refresh, user` |
| `resend-otp/` | POST | Public | `email` | OTP resent |
| `login/` | POST | Public | `username` (or email), `password` | `access, refresh` |
| `refresh/` | POST | Public | `refresh` | new `access` token |
| `profile/` | GET | 🔐 | — | User + Profile data |
| `profile/` | PATCH | 🔐 | `display_name?, timezone?` | Updated user data |
| `change-password/` | POST | 🔐 | `old_password, new_password` | Success message |
| `forgot-password/` | POST | Public | `email` | OTP sent |
| `reset-password/` | POST | Public | `email, otp, new_password` | Success message |

### Books & Transactions — `/api/v1/`

| Endpoint | Method | Auth | Notes |
|---|---|---|---|
| `books/` | GET | 🔐 | List all books with `bid`, `balance`, `transactions_count` |
| `books/` | POST | 🔐 | `name, description` |
| `books/{id}/` | GET | 🔐 | Single book detail |
| `books/{id}/` | PUT / PATCH | 🔐 | Update book name/description |
| `books/{id}/` | DELETE | 🔐 | Delete a book and all its transactions |
| `books/{id}/transactions/` | GET | 🔐 | List all transactions (newest first) |
| `books/{id}/transactions/` | POST | 🔐 | `amount, type, note, created_at` |
| `transactions/{id}/` | PUT / PATCH | 🔐 | Edit a transaction |
| `transactions/{id}/` | DELETE | 🔐 | Delete a transaction |
| `validate-bid/` | GET | 🔐 | `?bid=XXXXXX` → `owner_name, book_name` |
| `transfer/` | POST | 🔐 | `sender_book_id, recipient_bid, amount, note?` |

### Example: Login + Get Books (Postman / Flutter HTTP)

```json
// POST /api/v1/auth/login/
{
  "username": "your_email@example.com",
  "password": "yourpassword"
}

// Response
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}

// GET /api/v1/books/
// Header: Authorization: Bearer eyJ...

// Response
[
  {
    "id": 1,
    "name": "Personal Savings",
    "description": "My main book",
    "bid": "482901",
    "created_at": "2026-01-15",
    "transactions_count": 24,
    "balance": 15000.00
  }
]
```

---

## ⚙️ Installation & Local Setup

### Prerequisites
- Python **3.12+**
- pip
- Git

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/tanvir14ahmed/my_cashbook.git
cd my_cashbook

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your email credentials

# 5. Apply database migrations
python manage.py migrate

# 6. Create an admin superuser
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser.

### Environment Variables (`.env`)

```env
EMAIL_HOST_USER=your-email@yourdomain.com
EMAIL_HOST_PASSWORD=your-email-password
```

> **Note:** The app uses Django's SMTP email backend for OTP delivery. Configure your email host in `settings.py` accordingly.

---

## 🚀 Deployment (cPanel)

The project includes a `.cpanel.yml` for automated Git-based deployment to cPanel.

```yaml
# .cpanel.yml
post_deploy:
  - python3.12 manage.py migrate
  - python3.12 manage.py collectstatic --noinput
```

### Steps
1. Push code to GitHub.
2. In cPanel → **Git Version Control**, pull the latest changes.
3. cPanel automatically runs `migrate` and `collectstatic`.
4. Restart the Python app from **Setup Python App**.

> ⚠️ **Data Safety:** `migrate` only applies new schema changes — it **never** deletes existing data.

---

## 🗃️ Database

- **Development:** SQLite (`db.sqlite3`)
- **Production:** MySQL (`mysqlclient` driver included)

Switch in `settings.py` by uncommenting the MySQL block and commenting out the SQLite block:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

---

## 📦 Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| Django | 5.2.8 | Web framework |
| djangorestframework | 3.16.1 | REST API |
| djangorestframework-simplejwt | 5.5.1 | JWT authentication |
| mysqlclient | 2.2.7 | MySQL database driver |
| reportlab | 4.4.4 | PDF generation |
| python-decouple | 3.8 | Environment variable management |
| gunicorn | 23.0.0 | WSGI server for production |
| whitenoise | 6.11.0 | Static file serving |
| pytz | 2025.2 | Timezone support |
| pillow | 12.0.0 | Image processing |

> Full list in [`requirements.txt`](requirements.txt)

---

## 🧪 Running Tests

```bash
source .venv/bin/activate
python manage.py test books.tests_api --verbosity=2
```

The test suite covers:
- Login by username and email
- Unauthorized access blocked (401)
- Book list filtered by owner
- Cross-user book access blocked (404)
- Transaction creation and balance update

---

## 📱 Flutter / Mobile App Integration

This backend is designed to support a **Flutter Android/iOS app**. Key integration points:

1. **Authentication**: Use `/api/v1/auth/login/` to get JWT tokens. Store them with `flutter_secure_storage`.
2. **Token Refresh**: Call `/api/v1/auth/refresh/` when the access token expires.
3. **Books**: `GET /api/v1/books/` returns all books with balances and BIDs.
4. **Transactions**: `GET /api/v1/books/{id}/transactions/` for a full list.
5. **P2P Transfer**: First validate with `GET /api/v1/validate-bid/`, then `POST /api/v1/transfer/`.
6. **Local API (during dev)**: Use `http://10.0.2.2:8000/` from Android Emulator (maps to your PC's localhost).

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a new branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add: your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a **Pull Request**

---

## 📃 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Tanvir Ahmed Joy**

| | |
|---|---|
| 📧 Email | [tanvir14ahmed@gmail.com](mailto:tanvir14ahmed@gmail.com) |
| 📱 WhatsApp | +8801823555505 |
| 🌐 Portfolio | [tanvir.codelab-by-tnv.top](https://tanvir.codelab-by-tnv.top) |
| 🐙 GitHub | [github.com/tanvir14ahmed](https://github.com/tanvir14ahmed) |
| 🌍 Live App | [mycashbook.codelab-by-tnv.top](https://mycashbook.codelab-by-tnv.top) |

---

<div align="center">

**MyCashBook** — Track your expenses wisely. 💰

</div>
