from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from expenses.models import Expense
from fd.models import FD
from fd.services import compute_locked_amount
from income.models import Income
from ledger.services import compute_fine_due
from payments.models import Payment
from savings.models import SavingsAccount


def hello_dashboard(request):
    my_accounts = SavingsAccount.objects.filter(user=request.user)
    my_account = my_accounts.order_by('created_at').first()
    my_savings = my_accounts.aggregate(total=Sum('balance'))['total'] or 0
    total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or 0
    my_locked_in_fd = (
        sum((compute_locked_amount(account) for account in my_accounts), Decimal('0'))
        if my_account else Decimal('0')
    )
    total_locked_in_fd = FD.objects.filter(status=FD.Status.ACTIVE).aggregate(total=Sum('amount'))['total'] or 0

    year = timezone.now().year

    total_income = (
        Income.objects.filter(
            income_type__in=[Income.Type.INCOME, Income.Type.INTEREST],
            created_at__year=year,
        ).aggregate(total=Sum('amount'))['total']
        or 0
    )
    total_expenses = Expense.objects.filter(created_at__year=year).aggregate(total=Sum('amount'))['total'] or 0

    my_income = (
        Payment.objects.filter(
            savings_account__in=my_accounts,
            payment_type__in=[Payment.Type.INCOME, Payment.Type.INTEREST],
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or 0
    )
    my_expenses = (
        Payment.objects.filter(
            savings_account__in=my_accounts,
            payment_type=Payment.Type.EXPENSE,
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or 0
    )

    ham_fine_collected = (
        Payment.objects.filter(
            payment_type=Payment.Type.FINE,
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or 0
    )
    my_fine_paid = (
        Payment.objects.filter(
            savings_account__in=my_accounts,
            payment_type=Payment.Type.FINE,
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or 0
    )
    my_fine_remaining = compute_fine_due(my_account, year=year) if my_account else Decimal('0')

    return render(request, 'dashboard/hello.html', {
        'my_account': my_account,
        'my_savings': my_savings,
        'total_savings': total_savings,
        'total_locked_in_fd': total_locked_in_fd,
        'my_locked_in_fd': my_locked_in_fd,
        'total_income': total_income,
        'my_income': my_income,
        'total_expenses': total_expenses,
        'my_expenses': my_expenses,
        'ham_fine_collected': ham_fine_collected,
        'my_fine_paid': my_fine_paid,
        'my_fine_remaining': my_fine_remaining,
        'year': year,
    })
