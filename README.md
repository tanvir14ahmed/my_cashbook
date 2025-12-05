# MyCashBook

**MyCashBook** is a Django-based web application designed to help users manage their personal finances efficiently. The app allows users to track daily income and expenses, categorize transactions, view detailed reports, and download statements in PDF format. It provides a simple and clear interface for maintaining financial clarity.

---

## Features

* **User Authentication**: Sign up, login, and secure access to personal financial data.
* **Multiple Books**: Organize transactions into different books for various purposes.
* **Income & Expense Tracking**: Record daily income and expenses easily.
* **Detailed Reports**: View summaries and detailed reports of all transactions.
* **PDF Export**: Download transaction reports in PDF format for record-keeping.
* **Responsive UI**: Works on desktop and mobile devices.

---

## Project Structure

```
my_cashbook/
│
├── accounts/         # User authentication and profile management
├── books/            # Transaction and book management
├── core/             # Core configurations and utilities
├── static/           # CSS, JS, images, and other static files
├── templates/        # HTML templates for the frontend
├── manage.py         # Django management script
├── requirements.txt  # Python dependencies
├── db.sqlite3        # SQLite database (for development)
└── .gitignore        # Files and folders to ignore in Git
```

---

## Installation & Setup

### Prerequisites

* Python 3.x
* pip
* Virtual environment (`venv` recommended)
* Git

### Steps

1. **Clone the repository**

```bash
git clone https://github.com/tanvir14ahmed/my_cashbook.git
cd my_cashbook
```

2. **Create a virtual environment**

```bash
python -m venv venv
```

3. **Activate the virtual environment**

* Windows:

```bash
venv\Scripts\activate
```

* macOS/Linux:

```bash
source venv/bin/activate
```

4. **Install dependencies**

```bash
pip install -r requirements.txt
```

5. **Apply migrations**

```bash
python manage.py migrate
```

6. **Create a superuser (for admin access)**

```bash
python manage.py createsuperuser
```

7. **Run the development server**

```bash
python manage.py runserver
```

Open your browser at `http://127.0.0.1:8000/` to access MyCashBook.

---

## Usage

1. Sign up for a new account or login if you already have one.
2. Create a “Book” to categorize your transactions.
3. Add income and expense entries under the book.
4. View summaries and generate PDF reports for your records.

---

## Dependencies

* Django 4.x
* ReportLab (for PDF generation)
* Other dependencies listed in `requirements.txt`

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a new branch (`git checkout -b feature-name`)
3. Make your changes and commit (`git commit -m 'Add feature'`)
4. Push to the branch (`git push origin feature-name`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Contact

**Tanvir Ahmed Joy**

* Phone: +8801823555505 (@Whatsapp)
* Email: [tanvir14ahmed@gmail.com](mailto:tanvir14ahmed@gmail.com)
* GitHub: [https://github.com/tanvir14ahmed](https://github.com/tanvir14ahmed)

---

**MyCashBook** helps you manage your daily finances with clarity and ease. Start tracking your expenses today!
