from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Book, Transaction
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from datetime import datetime, date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph, SimpleDocTemplate, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date
from django.utils import timezone
import pytz
from django.db import transaction as db_transaction
from django.db.models import Sum, Case, When, DecimalField, F, Value
from django.db.models.functions import Coalesce


@login_required
def dashboard_view(request):
    # Get search query from request
    search_query = request.GET.get('search', '').strip()
    
    # Filter books by user and apply search if provided
    books = Book.objects.filter(user=request.user)
    
    if search_query:
        books = books.filter(name__icontains=search_query)
    
    # Sort books alphabetically by name (case-insensitive)
    books = books.annotate(
        total_balance=Coalesce(
            Sum(
                Case(
                    When(transactions__type='deposit', then=F('transactions__amount')),
                    When(transactions__type='withdraw', then=-F('transactions__amount')),
                    output_field=DecimalField(),
                )
            ),
            Value(0, output_field=DecimalField()),
        )
    ).order_by('name')
    
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
                'bid': book.bid,
                'description': book.description or 'No description provided.',
                'total_balance': str(book.total_balance),
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

    # Set Dhaka timezone for current time references
    dhaka_tz = pytz.timezone('Asia/Dhaka')
    now_dhaka = timezone.now().astimezone(dhaka_tz)

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
        end_date_display = now_dhaka.strftime('%Y-%m-%d')
        
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
    total_deposit_count = 0
    total_withdrawal_count = 0

    for t in transactions_list:
        if t.type.lower() == "deposit":
            running_balance += t.amount
            total_deposit += t.amount
            total_deposit_count += 1
        else:
            running_balance -= t.amount
            total_withdrawal += t.amount
            total_withdrawal_count += 1
        running_balances.append(running_balance)

    total_transaction_count = total_deposit_count + total_withdrawal_count

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
    report_timestamp = now_dhaka.strftime('%d-%m-%Y_%H%M%S')
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

    # --- Custom Styles (Professional Bank Statement Style) ---
    
    # Professional colors
    ACCENT_COLOR = colors.HexColor("#003366") # Navy Blue
    TEXT_COLOR = colors.HexColor("#333333")
    LINE_COLOR = colors.HexColor("#cccccc")
    
    # Logo Title Style
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=20, fontName='Helvetica-Bold', alignment=0, textColor=ACCENT_COLOR)
    
    # Tagline Style
    tagline_style = ParagraphStyle('Tagline', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Oblique', textColor=colors.grey, alignment=0)
    
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=TEXT_COLOR)
    
    # Note Color
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
    
    timestamp_style = ParagraphStyle('Timestamp', parent=styles['Normal'], fontSize=8, alignment=0, textColor=colors.grey)
    
    # Report Title Style
    report_header_style = ParagraphStyle('ReportHeader', parent=styles['Heading2'], fontSize=14, fontName='Helvetica-Bold', alignment=0, spaceBefore=20, spaceAfter=10, textColor=ACCENT_COLOR)

    # --- 1. Logo/Title Section ---
    
    # Main Logo Writing in Deep Purple (Requirement 2)
    elements.append(Paragraph("MyCashbook", title_style))
    elements.append(Paragraph("Track Your Expense Wisely", tagline_style))
    elements.append(Paragraph(f"<font size=8 color='#0000FF'>Website: mycashbook.codelab-by-tnv.top</font>", tagline_style))
    elements.append(Spacer(1, 15))

    # --- Report Information Section (Left: book/dates, Right: Final Balance) ---
    
    # Format the final balance text with the determined color
    final_balance_para = Paragraph(
        f"<font size=12 color='{TEXT_COLOR}'><b>Statement Balance:</b></font><br/><font size=16 color='{balance_color}'><b>{total_balance_report:.2f} TK</b></font>", 
        ParagraphStyle('Balance', parent=styles['Normal'], alignment=2, leading=22)
    )
    
    # Data for the header info table 
    header_data = [
        [
            Paragraph(f"<b>Account Holder:</b> {request.user.get_full_name() or request.user.username}<br/>"
                      f"<b>Book Name:</b> {book.name}<br/>"
                      f"<b>Period:</b> {start_date_display} to {end_date_display}", info_style),
            final_balance_para
        ]
    ]

    page_width = A4[0] - 50
    header_table = Table(header_data, colWidths=[page_width * 0.65, page_width * 0.35])
    header_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, ACCENT_COLOR),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    
    # Statement Header
    elements.append(Paragraph("Account Statement - Activity Detail", report_header_style))

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
    
    # Professional Bank Table Style
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT_COLOR), # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('LINEBELOW', (0, 0), (-1, 0), 2, ACCENT_COLOR),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE_COLOR),
    ])

    for i in range(1, len(data)):
        # Zebra stripping for rows
        bg = colors.HexColor("#f4f4f8") if i % 2 == 0 else colors.white 
        table_style.add('BACKGROUND', (0, i), (-1, i), bg)
        table_style.add('ALIGN', (0, i), (-1, i), 'CENTER')
        table_style.add('FONTSIZE', (0, i), (-1, i), 9)

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 15))
    
    # --- Total Deposit and Total Withdrawal Section ---
    
    summary_data = [
        [
            Paragraph(f"<b>Total Deposits ({total_deposit_count}):</b>", info_style),
            Paragraph(f"<font color='#27ae60'><b>{total_deposit:.2f} TK</b></font>", info_style)
        ],
        [
            Paragraph(f"<b>Total Withdrawals ({total_withdrawal_count}):</b>", info_style),
            Paragraph(f"<font color='#e74c3c'><b>{total_withdrawal:.2f} TK</b></font>", info_style)
        ],
        [
            Paragraph(f"<font size=9 color='#808080'>Total Transaction Count: {total_transaction_count}</font>", info_style),
            Paragraph("", info_style) # Empty cell for alignment
        ]
    ]
    
    summary_table = Table(summary_data, colWidths=[page_width * 0.7, page_width * 0.3])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, 1), 1, ACCENT_COLOR),
        ('TOPPADDING', (0, 0), (-1, 1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 1), 8),
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
        f"Statement generated on: {now_dhaka.strftime('%d %B, %Y at %I:%M %p')} (Dhaka Time)",
        timestamp_style
    ))

    elements.append(footer_note_para)

    # --- Page Footer Function (Meet the Developer & Page Numbers) ---
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(doc.leftMargin, 20, f"Page {doc.page}")

        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle
        link_style = ParagraphStyle('FooterLink', fontSize=8, alignment=2)
        link_text = '<font color="blue"><u><a href="https://tanvir.codelab-by-tnv.top/">Meet The Developer</a></u></font>'
        link_para = Paragraph(link_text, link_style)
        w, h = link_para.wrap(doc.width, doc.bottomMargin)
        link_para.drawOn(canvas, doc.leftMargin, 20)
        canvas.restoreState()

    pdf.build(elements, onFirstPage=add_footer, onLaterPages=add_footer)

    return response

@login_required
def validate_bid(request):
    bid = request.GET.get('bid')
    if not bid:
        return JsonResponse({'success': False, 'message': 'BID is required.'})
    
    try:
        recipient_book = Book.objects.get(bid=bid)
        return JsonResponse({
            'success': True,
            'owner_name': recipient_book.user.profile.display_name or recipient_book.user.username,
            'book_name': recipient_book.name
        })
    except Book.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid BID. Book not found.'})

@login_required
def transfer_funds(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'})
    
    sender_book_id = request.POST.get('sender_book_id')
    recipient_bid = request.POST.get('recipient_bid')
    amount_str = request.POST.get('amount')
    user_note = request.POST.get('note', '').strip()
    
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            return JsonResponse({'success': False, 'message': 'Amount must be greater than zero.'})
    except (ValueError, TypeError, InvalidOperation):
        return JsonResponse({'success': False, 'message': 'Invalid amount format.'})
    
    sender_book = get_object_or_404(Book, id=sender_book_id, user=request.user)
    
    try:
        recipient_book = Book.objects.get(bid=recipient_bid)
    except Book.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Recipient Book not found.'})
    
    if sender_book == recipient_book:
        return JsonResponse({'success': False, 'message': 'Cannot transfer to the same book.'})
    
    # Calculate current balance of sender book
    sender_balance = sender_book.transactions.all().aggregate(
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
        return JsonResponse({'success': False, 'message': 'Insufficient balance in sender book.'})
    
    try:
        with db_transaction.atomic():
            # 1. Create Withdrawal for Sender
            sender_note = f"Transfer to BID-{recipient_bid}"
            if user_note:
                sender_note += f": {user_note}"
            
            Transaction.objects.create(
                book=sender_book,
                amount=amount,
                type='withdraw',
                note=sender_note
            )
            
            # 2. Create Deposit for Recipient
            recipient_note = f"Transfer from BID-{sender_book.bid}"
            if user_note:
                recipient_note += f": {user_note}"
                
            Transaction.objects.create(
                book=recipient_book,
                amount=amount,
                type='deposit',
                note=recipient_note
            )
            
        return JsonResponse({'success': True, 'message': 'Transfer successful!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Transfer failed: {str(e)}'})