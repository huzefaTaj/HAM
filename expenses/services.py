from decimal import ROUND_HALF_UP, Decimal

from django.db.models import F

from payments.models import Payment
from savings.models import SavingsAccount


def generate_expense_payments(expense, created_at=None):
    excluded_ids = set(expense.excluded_accounts.values_list('pk', flat=True))
    included_accounts = list(
        SavingsAccount.objects.filter(active=True)
        .exclude(pk__in=excluded_ids)
        .order_by('created_at')
    )

    if not included_accounts:
        return

    count = len(included_accounts)
    base_share = (expense.amount / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    shares = [base_share] * count

    # the last share absorbs the rounding remainder so shares always sum to the exact expense amount
    shares[-1] += expense.amount - (base_share * count)

    for account, share in zip(included_accounts, shares):
        payment = Payment.objects.create(
            savings_account=account,
            amount=share,
            payment_type=Payment.Type.EXPENSE,
            entry_type=Payment.EntryType.DEBIT,
        )
        if created_at:
            Payment.objects.filter(pk=payment.pk).update(created_at=created_at)
        SavingsAccount.objects.filter(pk=account.pk).update(balance=F('balance') - share)
