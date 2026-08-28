from datetime import date
from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from core.decorators import role_required
from fd.models import FD
from fd.services import available_balance, compute_locked_amount, compute_shares
from income.models import Income
from income.services import generate_income_payments
from savings.models import SavingsAccount


def hello_fd(request):
    fds = FD.objects.order_by('-created_at')
    return render(request, 'fd/hello.html', {'fds': fds})


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def create_fd(request):
    accounts = SavingsAccount.objects.filter(active=True).select_related('user').order_by('account_id')
    error = None

    if request.method == 'POST':
        fd_number = request.POST.get('fd_number', '').strip()
        amount_raw = request.POST.get('amount', '').strip()
        duration_raw = request.POST.get('duration_years', '').strip()
        start_date_raw = request.POST.get('start_date', '').strip()
        interest_rate_raw = request.POST.get('interest_rate', '').strip()
        excluded_ids = request.POST.getlist('excluded_accounts')

        amount = duration_years = start_date = interest_rate = None
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount.'

        if not error:
            try:
                duration_years = int(duration_raw)
                if duration_years <= 0:
                    raise ValueError
            except ValueError:
                error = 'Enter a valid duration in years.'

        if not error:
            try:
                start_date = date.fromisoformat(start_date_raw)
            except ValueError:
                error = 'Enter a valid start date.'

        if not error:
            try:
                interest_rate = Decimal(interest_rate_raw)
                if interest_rate <= 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                error = 'Enter a valid interest rate.'

        if not error and not fd_number:
            error = 'FD number is required.'

        if not error:
            included_accounts = list(
                SavingsAccount.objects.filter(active=True)
                .exclude(pk__in=excluded_ids)
                .order_by('created_at')
            )

            if not included_accounts:
                error = 'No accounts left to fund this FD after exclusions.'
            else:
                shares = compute_shares(amount, included_accounts)
                insufficient = [
                    account for account in included_accounts
                    if available_balance(account) < shares[account.pk]
                ]

                if insufficient:
                    names = ', '.join(
                        f'{account.user.get_full_name()} ({account.account_id})'
                        for account in insufficient
                    )
                    error = f'Cannot create FD — insufficient available balance for: {names}'
                else:
                    fd = FD.objects.create(
                        fd_number=fd_number,
                        amount=amount,
                        duration_years=duration_years,
                        start_date=start_date,
                        interest_rate=interest_rate,
                    )
                    fd.excluded_accounts.set(excluded_ids)
                    fd.participant_accounts.set(included_accounts)
                    return redirect('hello_fd')

    return render(request, 'fd/create_fd.html', {'accounts': accounts, 'error': error})


@role_required(User.Role.ACCOUNTANT, User.Role.SUPER_ADMIN)
def complete_fd(request, fd_id):
    fd = get_object_or_404(FD, pk=fd_id, status=FD.Status.ACTIVE)

    if request.method == 'POST':
        interest = fd.interest_amount

        fd.status = FD.Status.COMPLETED
        fd.save(update_fields=['status'])

        income = Income.objects.create(
            income_name=f'{fd.fd_id} interest on fd',
            income_type=Income.Type.INTEREST,
            amount=interest,
        )
        non_participants = SavingsAccount.objects.exclude(
            pk__in=fd.participant_accounts.values_list('pk', flat=True)
        )
        income.excluded_accounts.set(non_participants)
        generate_income_payments(income)

    return redirect('hello_fd')
