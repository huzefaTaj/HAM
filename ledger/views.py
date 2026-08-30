from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from core.constants import ANNUAL_DUE, FINE_ALLOWED, MONTHLY_FINE
from ledger.services import missed_months, sync_fine
from payments.models import Payment
from savings.models import SavingsAccount


def hello_ledger(request):
    now = timezone.now()
    year = now.year
    elapsed_months = now.month - 1  # fully-completed months so far this year

    contributions = (
        Payment.objects.filter(payment_type=Payment.Type.CONTRIBUTION, created_at__year=year, active=True)
        .annotate(month=ExtractMonth('created_at'))
        .values('savings_account__user_id', 'month')
        .annotate(total=Sum('amount'))
    )
    paid_by_user_month = defaultdict(dict)
    for row in contributions:
        paid_by_user_month[row['savings_account__user_id']][row['month']] = row['total']

    fine_paid_by_user = {}
    if FINE_ALLOWED:
        fine_payments = (
            Payment.objects.filter(payment_type=Payment.Type.FINE, created_at__year=year, active=True)
            .values('savings_account__user_id')
            .annotate(total=Sum('amount'))
        )
        fine_paid_by_user = {row['savings_account__user_id']: row['total'] for row in fine_payments}

    rows = []
    members = User.objects.exclude(role=User.Role.SUPER_ADMIN).order_by('first_name', 'last_name')
    for user in members:
        account = user.savings_accounts.order_by('created_at').first()
        month_totals = paid_by_user_month.get(user.id, {})
        paid_this_year = sum(month_totals.values(), Decimal('0'))

        fine = Decimal('0')
        if FINE_ALLOWED:
            gross_fine = missed_months(month_totals, elapsed_months) * MONTHLY_FINE
            fine_paid = fine_paid_by_user.get(user.id) or Decimal('0')
            fine = gross_fine - fine_paid
            if fine < 0:
                fine = Decimal('0')

        if account:
            sync_fine(account, fine)

        dues_remaining = ANNUAL_DUE - paid_this_year
        if dues_remaining < 0:
            dues_remaining = Decimal('0')

        total_remaining = dues_remaining + (fine if FINE_ALLOWED else Decimal('0'))

        rows.append({
            'user': user,
            'account': account,
            'paid': paid_this_year,
            'fine': fine,
            'remaining': total_remaining,
            'fully_paid': total_remaining <= 0,
        })

    return render(request, 'ledger/hello.html', {
        'rows': rows,
        'annual_due': ANNUAL_DUE,
        'year': year,
    })


def balance_sheet(request):
    now = timezone.now()
    year = now.year

    members = User.objects.exclude(role=User.Role.SUPER_ADMIN).order_by('first_name', 'last_name')
    member_ids = list(members.values_list('id', flat=True))

    accounts = SavingsAccount.objects.filter(user_id__in=member_ids)

    balance_by_user = {
        row['user_id']: row['total']
        for row in accounts.values('user_id').annotate(total=Sum('balance'))
    }

    sums = (
        Payment.objects.filter(
            savings_account__user_id__in=member_ids,
            created_at__year=year,
            active=True,
        )
        .values('savings_account__user_id', 'payment_type')
        .annotate(total=Sum('amount'))
    )

    totals_by_user_type = defaultdict(lambda: defaultdict(Decimal))
    for row in sums:
        user_id = row['savings_account__user_id']
        totals_by_user_type[user_id][row['payment_type']] = row['total'] or Decimal('0')

    rows = []
    total_contribution = Decimal('0')
    total_interest = Decimal('0')
    total_income = Decimal('0')
    total_expenses = Decimal('0')
    total_remaining = Decimal('0')
    for member in members:
        contribution = totals_by_user_type[member.id].get(Payment.Type.CONTRIBUTION, Decimal('0'))
        interest = totals_by_user_type[member.id].get(Payment.Type.INTEREST, Decimal('0'))
        income = totals_by_user_type[member.id].get(Payment.Type.INCOME, Decimal('0'))
        expenses = totals_by_user_type[member.id].get(Payment.Type.EXPENSE, Decimal('0'))
        remaining = balance_by_user.get(member.id) or Decimal('0')

        total_contribution += contribution
        total_interest += interest
        total_income += income
        total_expenses += expenses
        total_remaining += remaining

        rows.append({
            'user': member,
            'contribution': contribution,
            'interest': interest,
            'income': income,
            'expenses': expenses,
            'remaining': remaining,
        })

    return render(request, 'ledger/balance_sheet.html', {
        'rows': rows,
        'year': year,
        'totals': {
            'contribution': total_contribution,
            'interest': total_interest,
            'income': total_income,
            'expenses': total_expenses,
            'remaining': total_remaining,
        },
    })
