from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from accounts.models import User
from core.decorators import role_required
from expenses.models import Expense
from expenses.services import generate_expense_payments
from income.models import Income
from income.services import generate_income_payments
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

        amount = None
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount.'

        if not name and not error:
            error = 'Name is required.'

        if not error:
            if txn_type == 'expense':
                expense = Expense.objects.create(expense_name=name, amount=amount)
                expense.excluded_accounts.set(excluded_ids)
                generate_expense_payments(expense)
                return redirect('hello_expenses')
            elif txn_type in ('income', 'interest'):
                income_type = Income.Type.INTEREST if txn_type == 'interest' else Income.Type.INCOME
                income = Income.objects.create(income_name=name, income_type=income_type, amount=amount)
                income.excluded_accounts.set(excluded_ids)
                generate_income_payments(income)
                return redirect('hello_expenses')
            else:
                error = 'Choose a type.'

    return render(request, 'expenses/add_transaction.html', {
        'accounts': accounts,
        'error': error,
    })
