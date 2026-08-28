from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from core.constants import ANNUAL_DUE, MONTHLY_FINE
from ledger.services import missed_months, sync_fine
from payments.models import Payment


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

        total_remaining = dues_remaining + fine

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
