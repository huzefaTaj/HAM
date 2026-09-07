from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from core.constants import ANNUAL_DUE, FINE_ALLOWED
from core.decorators import role_required
from expenses.models import Expense
from income.models import Income
from income.services import generate_income_payments
from ledger.services import compute_fine_due, sync_fine
from payments.models import Payment
from savings.models import SavingsAccount


def hello_payments(request):
    tab = request.GET.get('tab', 'mine')
    q = (request.GET.get('q') or '').strip()
    payment_type_filter = (request.GET.get('payment_type') or '').strip()
    entry_filter = (request.GET.get('entry') or '').strip()  # cr / dr
    date_from = (request.GET.get('from') or '').strip()  # YYYY-MM-DD
    date_to = (request.GET.get('to') or '').strip()      # YYYY-MM-DD
    status_filter = (request.GET.get('status') or '').strip()  # approved / pending
    limit_raw = (request.GET.get('limit') or '').strip()
    try:
        limit = int(limit_raw) if limit_raw else 10
    except ValueError:
        limit = 10
    if limit not in (10, 50, 100):
        limit = 10

    if tab == 'all':
        tab = 'all'

        grouped_income_qs = Income.objects.all()
        grouped_expense_qs = Expense.objects.all()

        if q:
            grouped_income_qs = grouped_income_qs.filter(income_name__icontains=q)
            grouped_expense_qs = grouped_expense_qs.filter(expense_name__icontains=q)

        if date_from:
            grouped_income_qs = grouped_income_qs.filter(created_at__date__gte=date_from)
            grouped_expense_qs = grouped_expense_qs.filter(created_at__date__gte=date_from)
        if date_to:
            grouped_income_qs = grouped_income_qs.filter(created_at__date__lte=date_to)
            grouped_expense_qs = grouped_expense_qs.filter(created_at__date__lte=date_to)

        if entry_filter == Payment.EntryType.DEBIT:
            grouped_income_qs = grouped_income_qs.none()
        elif entry_filter == Payment.EntryType.CREDIT:
            grouped_expense_qs = grouped_expense_qs.none()

        if payment_type_filter:
            if payment_type_filter == Payment.Type.EXPENSE:
                grouped_income_qs = grouped_income_qs.none()
            elif payment_type_filter == Payment.Type.INCOME:
                grouped_expense_qs = grouped_expense_qs.none()
                grouped_income_qs = grouped_income_qs.filter(income_type=Income.Type.INCOME)
            elif payment_type_filter == Payment.Type.INTEREST:
                grouped_expense_qs = grouped_expense_qs.none()
                grouped_income_qs = grouped_income_qs.filter(income_type=Income.Type.INTEREST)
            elif payment_type_filter == Payment.Type.FINE_REDISTRIBUTION:
                grouped_expense_qs = grouped_expense_qs.none()
                grouped_income_qs = grouped_income_qs.filter(income_type=Income.Type.FINE_REDISTRIBUTION)
            else:
                # direct payment type (contribution/fine/loans/etc)
                grouped_income_qs = grouped_income_qs.none()
                grouped_expense_qs = grouped_expense_qs.none()

        grouped_income = grouped_income_qs.values('income_id', 'income_name', 'income_type', 'amount', 'created_at')
        grouped_expense = grouped_expense_qs.values('expense_id', 'expense_name', 'amount', 'created_at')

        grouped_rows = []
        for row in grouped_income:
            grouped_rows.append({
                'is_group': True,
                'group_kind': 'income',
                'group_id': row['income_id'],
                'title': row['income_name'],
                'payment_type': row['income_type'],  # used for display only in template
                'entry_type': Payment.EntryType.CREDIT,
                'amount': row['amount'],
                'active': True,
                'created_at': row['created_at'],
            })
        for row in grouped_expense:
            grouped_rows.append({
                'is_group': True,
                'group_kind': 'expense',
                'group_id': row['expense_id'],
                'title': row['expense_name'],
                'payment_type': Payment.Type.EXPENSE,
                'entry_type': Payment.EntryType.DEBIT,
                'amount': row['amount'],
                'active': True,
                'created_at': row['created_at'],
            })

        # Keep direct payments (contribution, fine, loans, etc.) as individual rows.
        direct_qs = Payment.objects.select_related('savings_account__user').filter(income__isnull=True, expense__isnull=True)
        if q:
            direct_qs = direct_qs.filter(
                Q(savings_account__user__first_name__icontains=q)
                | Q(savings_account__user__last_name__icontains=q)
                | Q(savings_account__user__email__icontains=q)
            )
        if date_from:
            direct_qs = direct_qs.filter(created_at__date__gte=date_from)
        if date_to:
            direct_qs = direct_qs.filter(created_at__date__lte=date_to)
        if entry_filter in (Payment.EntryType.CREDIT, Payment.EntryType.DEBIT):
            direct_qs = direct_qs.filter(entry_type=entry_filter)
        if payment_type_filter and payment_type_filter not in (
            Payment.Type.EXPENSE,
            Payment.Type.INCOME,
            Payment.Type.INTEREST,
            Payment.Type.FINE_REDISTRIBUTION,
        ):
            direct_qs = direct_qs.filter(payment_type=payment_type_filter)

        payments = list(direct_qs.order_by('-created_at'))

        # Merge: dict rows + model instances, sorted by created_at
        payments = sorted(
            list(grouped_rows) + payments,
            key=lambda item: item['created_at'] if isinstance(item, dict) else item.created_at,
            reverse=True,
        )

        paginator = Paginator(payments, limit)
        page_obj = paginator.get_page(request.GET.get('page'))
        payments = page_obj
    else:
        tab = 'mine'
        qs = (
            Payment.objects.filter(savings_account__user=request.user)
            .select_related('savings_account__user')
            .order_by('-created_at')
        )
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if entry_filter in (Payment.EntryType.CREDIT, Payment.EntryType.DEBIT):
            qs = qs.filter(entry_type=entry_filter)
        if status_filter == 'approved':
            qs = qs.filter(active=True)
        elif status_filter == 'pending':
            qs = qs.filter(active=False)
        if payment_type_filter:
            qs = qs.filter(payment_type=payment_type_filter)

        paginator = Paginator(qs, limit)
        page_obj = paginator.get_page(request.GET.get('page'))
        payments = page_obj

    params = request.GET.copy()
    params.pop('page', None)
    base_qs = params.urlencode()

    return render(request, 'payments/hello.html', {
        'tab': tab,
        'payments': payments,
        'page_obj': page_obj,
        'base_qs': base_qs,
        'filters': {
            'q': q,
            'payment_type': payment_type_filter,
            'entry': entry_filter,
            'from': date_from,
            'to': date_to,
            'status': status_filter,
            'limit': str(limit),
        },
    })


def group_detail(request, kind, group_id):
    if kind == 'income':
        group = Income.objects.filter(income_id=group_id).first()
        if not group:
            return redirect('hello_payments')
        payments = (
            Payment.objects.filter(income=group, active=True)
            .select_related('savings_account__user')
            .order_by('savings_account__account_id')
        )
        title = group.income_name
        entry_type = Payment.EntryType.CREDIT
        amount = group.amount
        created_at = group.created_at
        payment_type = group.get_income_type_display()
    elif kind == 'expense':
        group = Expense.objects.filter(expense_id=group_id).first()
        if not group:
            return redirect('hello_payments')
        payments = (
            Payment.objects.filter(expense=group, active=True)
            .select_related('savings_account__user')
            .order_by('savings_account__account_id')
        )
        title = group.expense_name
        entry_type = Payment.EntryType.DEBIT
        amount = group.amount
        created_at = group.created_at
        payment_type = 'Expense'
    else:
        return redirect('hello_payments')

    return render(request, 'payments/group_detail.html', {
        'kind': kind,
        'group_id': group_id,
        'title': title,
        'payment_type': payment_type,
        'entry_type': entry_type,
        'amount': amount,
        'created_at': created_at,
        'payments': payments,
    })


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
                        applies_to_year=year,
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
                        applies_to_year=year,
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


@role_required(User.Role.SUPER_ADMIN)
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
                        source_payment=payment,
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


@role_required(User.Role.SUPER_ADMIN)
def edit_payment(request, txn_id):
    payment = Payment.objects.select_related('savings_account__user').filter(transaction_id=txn_id).first()
    if not payment or not payment.active:
        return redirect('hello_payments')

    if payment.payment_type not in (Payment.Type.CONTRIBUTION, Payment.Type.FINE):
        return redirect('hello_payments')

    error = None

    if request.method == 'POST':
        amount_raw = (request.POST.get('amount') or '').strip()
        amount = None
        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = 'Enter a valid amount.'

        if not error:
            old_amount = payment.amount
            if amount == old_amount:
                return redirect('hello_payments')

            if payment.payment_type == Payment.Type.CONTRIBUTION:
                delta = amount - old_amount
                Payment.objects.filter(pk=payment.pk).update(amount=amount)
                SavingsAccount.objects.filter(pk=payment.savings_account_id).update(balance=F('balance') + delta)
                return redirect('hello_payments')

            # Fine: adjust the payer's fine due and the redistribution income + payments.
            redistribution = Income.objects.filter(source_payment=payment).first()
            if redistribution is None:
                error = 'Cannot edit this fine payment because its redistribution record is missing.'
            else:
                from django.db import transaction

                with transaction.atomic():
                    # reverse existing redistribution payments from balances, then delete them
                    rows = list(
                        Payment.objects.filter(income=redistribution)
                        .values('savings_account_id')
                        .annotate(total=Sum('amount'))
                    )
                    for row in rows:
                        SavingsAccount.objects.filter(pk=row['savings_account_id']).update(balance=F('balance') - row['total'])
                    Payment.objects.filter(income=redistribution).delete()

                    Income.objects.filter(pk=redistribution.pk).update(amount=amount)
                    Payment.objects.filter(pk=payment.pk).update(amount=amount)

                    redistribution.refresh_from_db(fields=['amount', 'income_type'])
                    generate_income_payments(redistribution, created_at=redistribution.created_at)

                    sync_fine(payment.savings_account, compute_fine_due(payment.savings_account))
                    return redirect('hello_payments')

    return render(request, 'payments/edit_payment.html', {
        'payment': payment,
        'error': error,
    })


@role_required(User.Role.SUPER_ADMIN)
def delete_payment(request, txn_id):
    if request.method != 'POST':
        return redirect('hello_payments')

    payment = Payment.objects.select_related('savings_account__user').filter(transaction_id=txn_id).first()
    if not payment or not payment.active:
        return redirect('hello_payments')

    if payment.payment_type not in (Payment.Type.CONTRIBUTION, Payment.Type.FINE):
        return redirect('hello_payments')

    from django.db import transaction

    with transaction.atomic():
        if payment.payment_type == Payment.Type.CONTRIBUTION:
            SavingsAccount.objects.filter(pk=payment.savings_account_id).update(balance=F('balance') - payment.amount)
            payment.delete()
            return redirect('hello_payments')

        redistribution = Income.objects.filter(source_payment=payment).first()
        if redistribution is not None:
            rows = list(
                Payment.objects.filter(income=redistribution)
                .values('savings_account_id')
                .annotate(total=Sum('amount'))
            )
            for row in rows:
                SavingsAccount.objects.filter(pk=row['savings_account_id']).update(balance=F('balance') - row['total'])
            Payment.objects.filter(income=redistribution).delete()
            redistribution.delete()

        payer_account = payment.savings_account
        payment.delete()
        sync_fine(payer_account, compute_fine_due(payer_account))

    return redirect('hello_payments')
