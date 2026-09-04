from datetime import datetime, time
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db import transaction
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
            'txn_type': 'expense',
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
            'txn_type': 'income',
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


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def edit_transaction(request, txn_type, txn_id):
    accounts = SavingsAccount.objects.filter(active=True).select_related('user').order_by('account_id')
    error = None

    if txn_type == 'expense':
        txn = Expense.objects.filter(expense_id=txn_id).first()
        if not txn:
            return redirect('hello_expenses')
        initial_type = 'expense'
        initial_title = txn.expense_name
        initial_amount = txn.amount
        initial_excluded = set(txn.excluded_accounts.values_list('pk', flat=True))
        initial_date = txn.created_at.date()
        initial_income_type = None
    elif txn_type == 'income':
        txn = Income.objects.filter(income_id=txn_id).exclude(income_type=Income.Type.FINE_REDISTRIBUTION).first()
        if not txn:
            return redirect('hello_expenses')
        initial_type = 'interest' if txn.income_type == Income.Type.INTEREST else 'income'
        initial_title = txn.income_name
        initial_amount = txn.amount
        initial_excluded = set(txn.excluded_accounts.values_list('pk', flat=True))
        initial_date = txn.created_at.date()
        initial_income_type = initial_type
    else:
        return redirect('hello_expenses')

    if request.method == 'POST':
        form_type = request.POST.get('type')
        title = request.POST.get('name', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        excluded_ids = request.POST.getlist('excluded_accounts')
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

        if not title and not error:
            error = 'Title is required.'

        if form_type not in ('expense', 'income', 'interest') and not error:
            error = 'Choose a valid type.'

        if not error:
            with transaction.atomic():
                if txn_type == 'expense':
                    if form_type != 'expense':
                        error = 'You can only edit this as an expense.'
                    else:
                        # reverse old expense payments
                        old_payments = list(
                            Payment.objects.select_related('savings_account')
                            .filter(expense=txn, active=True)
                        )
                        for payment in old_payments:
                            SavingsAccount.objects.filter(pk=payment.savings_account_id).update(
                                balance=F('balance') + payment.amount
                            )
                        Payment.objects.filter(expense=txn).delete()

                        Expense.objects.filter(pk=txn.pk).update(expense_name=title, amount=amount)
                        txn.refresh_from_db(fields=['expense_name', 'amount', 'created_at'])
                        txn.excluded_accounts.set(excluded_ids)
                        if created_at:
                            Expense.objects.filter(pk=txn.pk).update(created_at=created_at)
                            txn.created_at = created_at

                        generate_expense_payments(txn, created_at=txn.created_at)
                        return redirect('hello_expenses')
                else:
                    # income / interest edit
                    if form_type == 'expense':
                        error = 'You can only edit this as income/interest.'
                    else:
                        old_payments = list(
                            Payment.objects.select_related('savings_account')
                            .filter(income=txn, active=True)
                        )
                        for payment in old_payments:
                            SavingsAccount.objects.filter(pk=payment.savings_account_id).update(
                                balance=F('balance') - payment.amount
                            )
                        Payment.objects.filter(income=txn).delete()

                        new_income_type = Income.Type.INTEREST if form_type == 'interest' else Income.Type.INCOME
                        Income.objects.filter(pk=txn.pk).update(income_name=title, amount=amount, income_type=new_income_type)
                        txn.refresh_from_db(fields=['income_name', 'amount', 'income_type', 'created_at'])
                        txn.excluded_accounts.set(excluded_ids)
                        if created_at:
                            Income.objects.filter(pk=txn.pk).update(created_at=created_at)
                            txn.created_at = created_at

                        generate_income_payments(txn, created_at=txn.created_at)
                        return redirect('hello_expenses')

    return render(request, 'expenses/edit_transaction.html', {
        'txn_type': txn_type,
        'txn_id': txn_id,
        'accounts': accounts,
        'error': error,
        'initial': {
            'type': initial_type,
            'name': initial_title,
            'amount': initial_amount,
            'excluded': list(initial_excluded),
            'created_date': initial_date.isoformat(),
            'income_type': initial_income_type,
        },
    })


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def delete_transaction(request, txn_type, txn_id):
    if request.method != 'POST':
        return redirect('hello_expenses')

    with transaction.atomic():
        if txn_type == 'expense':
            txn = Expense.objects.filter(expense_id=txn_id).first()
            if not txn:
                return redirect('hello_expenses')
            old_payments = list(Payment.objects.filter(expense=txn).values('savings_account_id', 'amount'))
            for row in old_payments:
                SavingsAccount.objects.filter(pk=row['savings_account_id']).update(balance=F('balance') + row['amount'])
            Payment.objects.filter(expense=txn).delete()
            txn.delete()
        elif txn_type == 'income':
            txn = Income.objects.filter(income_id=txn_id).exclude(income_type=Income.Type.FINE_REDISTRIBUTION).first()
            if not txn:
                return redirect('hello_expenses')
            old_payments = list(Payment.objects.filter(income=txn).values('savings_account_id', 'amount'))
            for row in old_payments:
                SavingsAccount.objects.filter(pk=row['savings_account_id']).update(balance=F('balance') - row['amount'])
            Payment.objects.filter(income=txn).delete()
            txn.delete()

    return redirect('hello_expenses')
