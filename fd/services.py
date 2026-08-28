from decimal import ROUND_HALF_UP, Decimal


def compute_shares(amount, accounts):
    """Split `amount` evenly across `accounts` (already ordered), returning
    {account_id: share}. The last account absorbs the rounding remainder so
    shares always sum to the exact amount."""
    count = len(accounts)
    if count == 0:
        return {}

    base_share = (amount / count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    shares = {account.pk: base_share for account in accounts}
    shares[accounts[-1].pk] += amount - (base_share * count)
    return shares


def compute_locked_amount(account):
    """Sum of this account's share across every FD it's still an ACTIVE participant in."""
    from fd.models import FD

    total = Decimal('0')
    active_fds = FD.objects.filter(status=FD.Status.ACTIVE, participant_accounts=account)
    for fd in active_fds:
        participants = list(fd.participant_accounts.order_by('created_at'))
        shares = compute_shares(fd.amount, participants)
        total += shares.get(account.pk, Decimal('0'))
    return total


def available_balance(account):
    return account.balance - compute_locked_amount(account)
