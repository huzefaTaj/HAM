from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone

from core.constants import FINE_ALLOWED, MONTHLY_DUE, MONTHLY_FINE
from ledger.models import Fine
from payments.models import Payment


def missed_months(month_totals, elapsed_months):
    """Walk each completed month in order: a month is only "covered" if the
    cumulative contribution paid by that point already met its cumulative
    due. A later lump-sum payment can't retroactively fix an earlier month
    that already missed its checkpoint."""
    missed = 0
    cumulative_paid = Decimal('0')
    for month in range(1, elapsed_months + 1):
        cumulative_paid += month_totals.get(month, Decimal('0'))
        if cumulative_paid < month * MONTHLY_DUE:
            missed += 1
    return missed


def compute_fine_due(account, year=None):
    """Fine still owed for one account: gross fine from missed months, minus
    any fine payments already made this year."""
    if not FINE_ALLOWED:
        return Decimal('0')
    if account is None:
        return Decimal('0')

    year = year or timezone.now().year
    elapsed_months = timezone.now().month - 1

    rows = (
        Payment.objects.filter(
            savings_account=account,
            payment_type=Payment.Type.CONTRIBUTION,
            created_at__year=year,
            active=True,
        )
        .annotate(month=ExtractMonth('created_at'))
        .values('month')
        .annotate(total=Sum('amount'))
    )
    month_totals = {row['month']: row['total'] for row in rows}

    gross_fine = missed_months(month_totals, elapsed_months) * MONTHLY_FINE

    fine_paid = (
        Payment.objects.filter(
            savings_account=account,
            payment_type=Payment.Type.FINE,
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )

    fine_due = gross_fine - fine_paid
    return fine_due if fine_due > 0 else Decimal('0')


def sync_fine(account, fine_due):
    if account is None:
        return
    if not FINE_ALLOWED:
        fine_due = Decimal('0')
    Fine.objects.update_or_create(savings_account=account, defaults={'fine_due': fine_due})
