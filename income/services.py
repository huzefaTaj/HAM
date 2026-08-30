from decimal import ROUND_HALF_UP, Decimal

from django.db.models import F

from income.models import Income
from payments.models import Payment
from savings.models import SavingsAccount


def generate_income_payments(income, created_at=None):
    excluded_ids = set(income.excluded_accounts.values_list('pk', flat=True))
    included_accounts = list(
        SavingsAccount.objects.filter(active=True)
        .exclude(pk__in=excluded_ids)
        .order_by('created_at')
    )

    if not included_accounts:
        return

    count = len(included_accounts)
    base_share = (income.amount / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    shares = [base_share] * count

    # the last share absorbs the rounding remainder so shares always sum to the exact income amount
    shares[-1] += income.amount - (base_share * count)

    income_to_payment_type = {
        Income.Type.INTEREST: Payment.Type.INTEREST,
        Income.Type.FINE_REDISTRIBUTION: Payment.Type.FINE_REDISTRIBUTION,
    }
    payment_type = income_to_payment_type.get(income.income_type, Payment.Type.INCOME)

    for account, share in zip(included_accounts, shares):
        payment = Payment.objects.create(
            savings_account=account,
            amount=share,
            payment_type=payment_type,
            entry_type=Payment.EntryType.CREDIT,
        )
        if created_at:
            Payment.objects.filter(pk=payment.pk).update(created_at=created_at)
        SavingsAccount.objects.filter(pk=account.pk).update(balance=F('balance') + share)
