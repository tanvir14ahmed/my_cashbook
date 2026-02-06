from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book, Transaction
from django.contrib import messages
from decimal import Decimal
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from .models import Transaction, Book
from accounts.models import Profile
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer, PageBreak
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.dateparse import parse_date
from django.http import HttpResponseBadRequest
from datetime import date # Import date
from django.utils import timezone
import pytz
from decimal import Decimal
from datetime import datetime


@login_required
def dashboard_view(request):
    # Get search query from request
    search_query = request.GET.get('search', '').strip()
    
    # Filter books by user and apply search if provided
    books = Book.objects.filter(user=request.user)
    
    if search_query:
        books = books.filter(name__icontains=search_query)
    
    # Sort books alphabetically by name (case-insensitive)
    books = books.order_by('name')
    
    # Pagination: 12 books per page
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax:
        # Return JSON response for AJAX requests
        from django.http import JsonResponse
        books_data = []
        for book in page_obj:
            books_data.append({
                'id': book.id,
                'name': book.name,
                'description': book.description or 'No description provided.',
            })
        
        return JsonResponse({
            'books': books_data,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
            'page_range': list(paginator.page_range),
        })
    
    # Regular request - render full page
    display_name = request.user.profile.display_name
    
    context = {
        'page_obj': page_obj,
        'display_name': display_name,
        'search_query': search_query,
    }
    return render(request, 'books/dashboard.html', context)

@login_required
def add_book_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')

        if name:
            Book.objects.create(user=request.user, name=name, description=description)
            messages.success(request, 'Book created successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Book name is required.')

    return render(request, 'books/add_book.html')

@login_required
def delete_book_view(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book.delete()
    messages.success(request, 'Book deleted successfully!')
    return redirect('dashboard')

from .models import Book, Transaction
from decimal import Decimal

@login_required
def book_detail_view(request, book_id):
    # Get the book for the logged-in user
    book = get_object_or_404(Book, id=book_id, user=request.user)

    # ---------------------------
    # 1) Handle Form Submission
    # ---------------------------
    if request.method == "POST":
        amount = request.POST.get("amount")
        t_type = request.POST.get("type")
        note = request.POST.get("note", "")
        created_at = request.POST.get("created_at")  # date only

        # Validate amount
        try:
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, "Amount must be positive.")
                return redirect("book_detail", book_id=book.id)
        except:
            messages.error(request, "Invalid amount.")
            return redirect("book_detail", book_id=book.id)

        # Create transaction
        Transaction.objects.create(
            book=book,
            amount=amount,
            type=t_type,
            note=note,
            created_at=created_at
        )
        return redirect("book_detail", book_id=book.id)

    # ----------------------------------------------------------
    # 2) Fetch all transactions (NEWEST first for display)
    #    MUST order using '-created_at' + '-id' for same-date rows!
    # ----------------------------------------------------------
    transactions = Transaction.objects.filter(book=book).order_by('-created_at', '-id')

    # For Total Balance (sum of all signed amounts)
    total_balance = sum(t.sign_amount for t in transactions)

    # ---------------------
    # 3) Pagination
    # ---------------------
    paginator = Paginator(transactions, 20)  # 20 per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ----------------------------------------------------------
    # 4) Running Balance Calculation
    #    MUST calculate in TRUE chronological order
    #    (oldest first, stable tie-break using id)
    # ----------------------------------------------------------
    ordered_oldest_first = list(
        transactions.order_by('created_at', 'id')
    )

    running_map = {}
    balance = Decimal('0.00')

    for t in ordered_oldest_first:
        balance += t.sign_amount
        running_map[t.id] = balance

    # Attach running balance to paginated results
    transactions_with_running = []
    for t in page_obj:
        t.running_balance = running_map.get(t.id, Decimal('0.00'))
        transactions_with_running.append(t)

    # ---------------------
    # 5) Render Template
    # ---------------------
    context = {
        'book': book,
        'page_obj': page_obj,
        'transactions_with_running': transactions_with_running,
        'total_balance': total_balance,
    }

    return render(request, 'books/book_detail.html', context)


@login_required
def add_transaction_view(request, book_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)

    if request.method == 'POST':
        amount_str = request.POST.get('amount')
        trans_type = request.POST.get('type')
        note = request.POST.get('note')
        
        # ⚠️ IMPORTANT: Use the field name that is actually in your HTML form
        transaction_date_str = request.POST.get('date') # Assuming 'date' is correct now
        
        # 1. Amount Validation
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            messages.error(request, "❌ Invalid amount! Please enter a positive number.")
            # ✅ ALL ERROR REDIRECTS MUST GO TO THE DISPLAY PAGE
            return redirect('book_detail', book_id=book.id) 

        # 2. Date Validation
        transaction_date = date.today()
        if transaction_date_str:
            try:
                transaction_date = date.fromisoformat(transaction_date_str)
            except ValueError:
                messages.error(request, "❌ Invalid date format.")
                # ✅ ALL ERROR REDIRECTS MUST GO TO THE DISPLAY PAGE
                return redirect('book_detail', book_id=book.id)

        # 3. Create Transaction
        Transaction.objects.create(
            book=book, 
            amount=amount, 
            type=trans_type, 
            note=note,
            date=transaction_date # Assuming 'date' is the correct model field name
        )
        
        # 4. Success Message and Final Redirect
        messages.success(request, '✅ Transaction added successfully!')
        return redirect('book_detail', book_id=book.id)
    
    # Handle GET requests if this view is accessed directly
    return redirect('book_detail', book_id=book.id)
    

@login_required
def edit_transaction_view(request, book_id, transaction_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=transaction_id, book=book)

    if request.method == 'POST':
        transaction.amount = request.POST['amount']
        transaction.type = request.POST['type']
        transaction.note = request.POST['note']
        transaction.save()
        messages.success(request, '✅ Transaction updated successfully!')
        return redirect('book_detail', book_id=book.id)

@login_required
def delete_transaction_view(request, book_id, transaction_id):
    book = get_object_or_404(Book, id=book_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=transaction_id, book=book)

    if request.method == 'POST':
        transaction.delete()
        messages.success(request, '✅ Transaction deleted successfully!')
        return redirect('book_detail', book_id=book.id)
    

@login_required
def transaction_report_pdf(request, book_id):
    # Authorize book access
    book = get_object_or_404(Book, id=book_id, user=request.user)

    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')

    # --- UPDATED DATE HANDLING LOGIC START ---
    
    is_date_range_report = start_date_str and end_date_str

    if is_date_range_report:
        # Case 1: Dates were provided (Date Range Report)
        start_date = parse_date(start_date_str)
        end_date = parse_date(end_date_str)
        
        if not start_date or not end_date:
            return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

        if start_date > end_date:
            return HttpResponseBadRequest("'start' date cannot be after 'end' date.")
        
        # Set display dates for PDF header
        start_date_display = start_date_str
        end_date_display = end_date_str
        
        # Filter: created_at__range
        transactions_filter = {'created_at__range': (start_date, end_date)}

    else:
        # Case 2: Dates were NOT provided (All Transactions Report)
        # Fetch all transactions, no date filtering needed.
        start_date_display = "Start of Book"
        end_date_display = datetime.now().strftime('%Y-%m-%d')
        
        # Filter: Empty dictionary means no date constraint, just book constraint
        transactions_filter = {}
    
    # --- UPDATED DATE HANDLING LOGIC END ---

    # Fetch transactions for this book and the determined criteria
    transactions_qs = Transaction.objects.filter(
        book=book,
        **transactions_filter # Apply date filter only if it exists
    ).order_by('created_at')

    # Calculate running balances (oldest first)
    running_balance = Decimal('0.00')
    running_balances = []
    transactions_list = list(transactions_qs)

    # Variables for Total Deposit and Withdrawal
    total_deposit = Decimal('0.00')
    total_withdrawal = Decimal('0.00')

    for t in transactions_list:
        if t.type.lower() == "deposit":
            running_balance += t.amount
            total_deposit += t.amount
        else:
            running_balance -= t.amount
            total_withdrawal += t.amount
        running_balances.append(running_balance)

    # Reverse lists for latest-first display in PDF
    transactions_display = transactions_list[::-1]
    running_balances_display = running_balances[::-1]

    # --- Determine Final Balance and Color (Requirement 1) ---
    total_balance_report = running_balances_display[0] if running_balances_display else Decimal('0.00')
    
    # Define color based on value
    if total_balance_report >= Decimal('0.00'):
        balance_color = "#27ae60"  # Green for positive/zero
    else:
        balance_color = "#e74c3c"  # Red for negative

    # PDF Setup
    response = HttpResponse(content_type='application/pdf')
    
    # --- Filename Logic (Using the requested format) ---
    report_timestamp = datetime.now().strftime('%d-%m-%Y_%H%M%S')
    # Clean the book name (e.g., "My Savings Book" -> "my_savings_book")
    safe_book_name = book.name.replace(' ', '_').lower().replace('.', '') 

    # Construct the new filename
    filename = f"{safe_book_name}_{report_timestamp}_MyCashbook_report.pdf"
    
    # Set the new Content-Disposition header
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    pdf = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=50,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    elements = []

    # --- Custom Styles (Standardized and Updated for Logo Color) ---
    
    # Deep Purple color for the main logo text (Requirement 2)
    DEEP_PURPLE = colors.HexColor("#4b0082") 
    
    # Logo Title Style (Requirement 2)
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, fontName='Helvetica-Bold', alignment=0, textColor=DEEP_PURPLE)
    
    # Tagline Style
    tagline_style = ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Oblique', textColor=colors.darkgrey, alignment=0)
    
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10.5, fontName='Helvetica-Bold')
    
    # --- CHANGE 1: Darker Note Color ---
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=9.5, textColor=colors.grey) # Changed from colors.darkgrey to colors.grey
    
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=9, alignment=0, textColor=colors.darkgrey)
    
    # --- New Title Style for Transaction Report ---
    report_header_style = ParagraphStyle('ReportHeader', parent=styles['Heading2'], fontSize=14, fontName='Helvetica-Bold', alignment=1, spaceBefore=15, spaceAfter=8)

    # --- 1. Logo/Title Section ---
    
    # Main Logo Writing in Deep Purple (Requirement 2)
    elements.append(Paragraph("MyCashbook", title_style))
    elements.append(Paragraph("Track Your Expense Wisely", tagline_style))
    elements.append(Paragraph(f"<font size=8 color='#0000FF'>Website: mycashbook.codelab-by-tnv.top</font>", tagline_style))
    elements.append(Spacer(1, 15))

    # --- Report Information Section (Left: book/dates, Right: Final Balance) ---
    
    # Format the final balance text with the determined color (Requirement 1)
    final_balance_para = Paragraph(
        f"<font size=14 color='{balance_color}'><b>Current Balance:</b> {total_balance_report:.2f} TK</font>", 
        ParagraphStyle('Balance', parent=styles['Normal'], fontSize=14, alignment=2)
    )
    
    # Data for the header info table 
    header_data = [
        [
            Paragraph(f"<b>Book:</b> {book.name}", info_style),
            final_balance_para
        ],
        [
            # Use the determined display dates
            Paragraph(f"<b>Date Range:</b> {start_date_display} to {end_date_display}", info_style),
            '' 
        ]
    ]

    page_width = A4[0] - 50
    header_table = Table(header_data, colWidths=[page_width * 0.6, page_width * 0.4])
    header_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 1), (0, 1), 0.5, colors.HexColor("#6c5ce7")),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 15))
    
    # --- CHANGE 2: Add Transaction Report Heading ---
    elements.append(Paragraph("Transaction Report", report_header_style))

    # --- Transaction Table Data ---
    data = [["Date", "Type", "Amount", "Running Balance", "Note"]]

    for idx, t in enumerate(transactions_display):
        amount_text = f"{t.amount:.2f}"
        
        # Color-coding for Amount
        if t.type.lower() == "deposit":
            amount_para = Paragraph(f'<font color="#27ae60"><b>+{amount_text}</b></font>', styles["Normal"])
        else:
            amount_para = Paragraph(f'<font color="#e74c3c"><b>-{amount_text}</b></font>', styles["Normal"])
        
        # Running Balance - Style for clear distinction
        current_running_balance = running_balances_display[idx]
        if current_running_balance >= Decimal('0.00'):
            rb_color = "#2c3e50" # Dark grey/black for regular positive running balance
        else:
            rb_color = "#e74c3c" # Red for negative running balance
            
        running_balance_para = Paragraph(f"<font color='{rb_color}'>{current_running_balance:.2f}</font>", styles["Normal"])

        data.append([
            Paragraph(t.created_at.strftime("%d %B, %Y"), styles["Normal"]),
            Paragraph(t.type.capitalize(), styles["Normal"]),
            amount_para,
            running_balance_para,
            Paragraph(t.note or "-", note_style), # note_style now uses darker color
        ])

    # Column widths
    col_widths = [
        page_width * 0.18,  # Date
        page_width * 0.15,  # Type
        page_width * 0.15,  # Amount
        page_width * 0.22,  # Running Balance
        page_width * 0.30  # Note
    ]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Enhanced Table Style
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6c5ce7")), # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (3, 0), 'RIGHT'), # Align Amount/Balance Headers right
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor("#e0e0e0")), # Lighter grid lines
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#6c5ce7")), # Full table border
    ])

    for i in range(1, len(data)):
        # Zebra stripping for rows
        bg = colors.HexColor("#f4f4f8") if i % 2 == 0 else colors.white 
        table_style.add('BACKGROUND', (0, i), (-1, i), bg)
        # Content alignment
        table_style.add('ALIGN', (2, i), (3, i), 'RIGHT') 
        table_style.add('ALIGN', (0, i), (1, i), 'CENTER')
        table_style.add('ALIGN', (4, i), (4, i), 'LEFT')
        table_style.add('FONTSIZE', (0, i), (-1, i), 9.5)

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # --- Total Deposit and Total Withdrawal Section ---
    
    summary_data = [
        [
            Paragraph("<b>Total Deposits:</b>", info_style),
            Paragraph(f"<font color='#27ae60'><b>{total_deposit:.2f} TK</b></font>", info_style)
        ],
        [
            Paragraph("<b>Total Withdrawals:</b>", info_style),
            Paragraph(f"<font color='#e74c3c'><b>{total_withdrawal:.2f} TK</b></font>", info_style)
        ],
    ]
    
    summary_table = Table(summary_data, colWidths=[page_width * 0.7, page_width * 0.3])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor("#6c5ce7")), # Separator line
        ('TOPPADDING', (0, 0), (-1, 1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(summary_table)

    elements.append(Spacer(1, 12))
    
    # --- Footer Note (Translucent appearance simulated with grey text) ---
    
    footer_note_para = Paragraph(
        "This Is A System Generated Report, No Signature is Required",
        ParagraphStyle('FooterNote', parent=styles['Normal'], fontSize=9, alignment=1, textColor=colors.HexColor("#808080")) # Using a dark grey for 'transparency'
    )
    
    
    elements.append(Paragraph(
    f"Report generated on (Time: Dhaka/Bangladesh): {datetime.now().strftime('%d %B, %Y (%I:%M %p)')}",
    timestamp_style
    ))

    elements.append(footer_note_para)

    pdf.build(elements)
    return response