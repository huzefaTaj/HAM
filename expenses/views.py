from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from core.decorators import role_required
from expenses.models import Expense
from expenses.services import generate_expense_payments
from income.models import Income
from income.services import generate_income_payments
from payments.models import Payment
from savings.models import SavingsAccount


def hello_expenses(request):
    expense_rows = [
        {
            'id': expense.expense_id,
            'name': expense.expense_name,
            'category': 'Expense',
            'amount': expense.amount,
            'created_at': expense.created_at,
        }
        for expense in Expense.objects.all()
    ]
    income_rows = [
        {
            'id': income.income_id,
            'name': income.income_name,
            'category': income.get_income_type_display(),
            'amount': income.amount,
            'created_at': income.created_at,
        }
        for income in Income.objects.exclude(income_type=Income.Type.FINE_REDISTRIBUTION)
    ]

    transactions = sorted(expense_rows + income_rows, key=lambda row: row['created_at'], reverse=True)

    paginator = Paginator(transactions, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'expenses/hello.html', {'page_obj': page_obj})


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def add_transaction(request):
    accounts = SavingsAccount.objects.filter(active=True).select_related('user').order_by('account_id')
    error = None

    if request.method == 'POST':
        txn_type = request.POST.get('type')
        name = request.POST.get('name', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        excluded_ids = request.POST.getlist('excluded_accounts')
        contribution_account_id = request.POST.get('contribution_account') or None
        created_date_raw = (request.POST.get('created_date') or '').strip()

        created_at = None
        if created_date_raw:
            try:
                created_date = datetime.strptime(created_date_raw, '%Y-%m-%d').date()
                created_at = timezone.make_aware(datetime.combine(created_date, time.min))
            except ValueError:
                error = 'Choose a valid date.'

        amount = None
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount.'

        if txn_type != 'contribution' and not name and not error:
            error = 'Title is required.'

        if not error:
            if txn_type == 'expense':
                expense = Expense.objects.create(expense_name=name, amount=amount)
                expense.excluded_accounts.set(excluded_ids)
                if created_at:
                    Expense.objects.filter(pk=expense.pk).update(created_at=created_at)
                generate_expense_payments(expense, created_at=created_at)
                return redirect('hello_expenses')
            elif txn_type in ('income', 'interest'):
                income_type = Income.Type.INTEREST if txn_type == 'interest' else Income.Type.INCOME
                income = Income.objects.create(income_name=name, income_type=income_type, amount=amount)
                income.excluded_accounts.set(excluded_ids)
                if created_at:
                    Income.objects.filter(pk=income.pk).update(created_at=created_at)
                generate_income_payments(income, created_at=created_at)
                return redirect('hello_expenses')
            elif txn_type == 'contribution':
                contribution_account = None
                if contribution_account_id:
                    contribution_account = accounts.filter(pk=contribution_account_id).first()
                if not contribution_account:
                    error = 'Choose a member account.'
                else:
                    payment = Payment.objects.create(
                        savings_account=contribution_account,
                        amount=amount,
                        payment_type=Payment.Type.CONTRIBUTION,
                        entry_type=Payment.EntryType.CREDIT,
                        active=True,
                    )
                    SavingsAccount.objects.filter(pk=contribution_account.pk).update(balance=F('balance') + amount)
                    if created_at:
                        Payment.objects.filter(pk=payment.pk).update(created_at=created_at)
                    return redirect('hello_payments')
            else:
                error = 'Choose a type.'

    return render(request, 'expenses/add_transaction.html', {
        'accounts': accounts,
        'error': error,
    })
