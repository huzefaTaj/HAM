from decimal import Decimal, InvalidOperation

from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from core.constants import ANNUAL_DUE, FINE_ALLOWED
from core.decorators import role_required
from income.models import Income
from income.services import generate_income_payments
from ledger.services import compute_fine_due, sync_fine
from payments.models import Payment
from savings.models import SavingsAccount


def hello_payments(request):
    tab = request.GET.get('tab', 'mine')

    if tab == 'all':
        payments = Payment.objects.select_related('savings_account__user').order_by('-created_at')
    else:
        tab = 'mine'
        payments = (
            Payment.objects.filter(savings_account__user=request.user)
            .select_related('savings_account__user')
            .order_by('-created_at')
        )

    return render(request, 'payments/hello.html', {'tab': tab, 'payments': payments})


def send_payment(request):
    account = request.user.savings_accounts.order_by('created_at').first()
    year = timezone.now().year

    paid_this_year = (
        Payment.objects.filter(
            savings_account=account,
            payment_type=Payment.Type.CONTRIBUTION,
            created_at__year=year,
            active=True,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    remaining_allowed = ANNUAL_DUE - paid_this_year
    if remaining_allowed < 0:
        remaining_allowed = Decimal('0')

    fine_due = compute_fine_due(account, year=year)

    error = None
    success = None

    if request.method == 'POST':
        payment_type = request.POST.get('payment_type')
        amount_raw = request.POST.get('amount', '').strip()

        amount = None
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount.'

        if amount is not None and not error:
            if payment_type == Payment.Type.CONTRIBUTION:
                if paid_this_year + amount > ANNUAL_DUE:
                    error = (
                        f'This would exceed your annual contribution limit of '
                        f'{ANNUAL_DUE}. You can deposit up to {remaining_allowed} more this year.'
                    )
                else:
                    Payment.objects.create(
                        savings_account=account,
                        amount=amount,
                        payment_type=Payment.Type.CONTRIBUTION,
                        entry_type=Payment.EntryType.CREDIT,
                        active=False,
                    )
                    success = 'Payment submitted — pending accountant approval.'
            elif payment_type == Payment.Type.FINE:
                if not FINE_ALLOWED:
                    error = 'Fine payments are currently disabled.'
                elif amount > fine_due:
                    error = f'This exceeds your outstanding fine of {fine_due}.'
                else:
                    Payment.objects.create(
                        savings_account=account,
                        amount=amount,
                        payment_type=Payment.Type.FINE,
                        entry_type=Payment.EntryType.DEBIT,
                        active=False,
                    )
                    success = 'Fine payment submitted — pending accountant approval.'
            else:
                error = 'Choose a valid payment type.'

    return render(request, 'payments/send_payment.html', {
        'error': error,
        'success': success,
        'paid_this_year': paid_this_year,
        'remaining_allowed': remaining_allowed,
        'fine_due': fine_due,
    })


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def approve_payments(request):
    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')
        action = request.POST.get('action')
        payment = Payment.objects.filter(pk=transaction_id, active=False).first()

        if payment:
            if payment.payment_type == Payment.Type.FINE and not FINE_ALLOWED:
                payment.delete()
                return redirect('approve_payments')
            if action == 'approve':
                payment.active = True
                payment.save(update_fields=['active'])

                if payment.payment_type == Payment.Type.FINE:
                    # Fine payments settle the fine record only — the payer's own
                    # savings balance is untouched. The amount is instead
                    # redistributed as income to every other account.
                    sync_fine(payment.savings_account, compute_fine_due(payment.savings_account))

                    redistribution = Income.objects.create(
                        income_name=f'Fine redistribution — {payment.savings_account.account_id}',
                        income_type=Income.Type.FINE_REDISTRIBUTION,
                        amount=payment.amount,
                    )
                    redistribution.excluded_accounts.set([payment.savings_account])
                    generate_income_payments(redistribution)
                elif payment.entry_type == Payment.EntryType.CREDIT:
                    SavingsAccount.objects.filter(pk=payment.savings_account_id).update(
                        balance=F('balance') + payment.amount
                    )
                else:
                    SavingsAccount.objects.filter(pk=payment.savings_account_id).update(
                        balance=F('balance') - payment.amount
                    )
            elif action == 'reject':
                payment.delete()

        return redirect('approve_payments')

    pending_payments = (
        Payment.objects.filter(active=False)
        .select_related('savings_account__user')
        .order_by('-created_at')
    )

    return render(request, 'payments/approve_payments.html', {'pending_payments': pending_payments})
