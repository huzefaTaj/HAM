from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework_simplejwt.tokens import RefreshToken

from savings.models import SavingsAccount
from accounts.models import User


def login_view(request):
    error = None
    next_url = request.POST.get('next') or request.GET.get('next') or ''

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is not None and user.active:
            refresh = RefreshToken.for_user(user)

            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                target = next_url
            else:
                target = reverse('hello_dashboard')

            response = redirect(target)
            response.set_cookie(
                settings.JWT_ACCESS_COOKIE,
                str(refresh.access_token),
                httponly=True,
                samesite='Lax',
                secure=not settings.DEBUG,
            )
            response.set_cookie(
                settings.JWT_REFRESH_COOKIE,
                str(refresh),
                httponly=True,
                samesite='Lax',
                secure=not settings.DEBUG,
            )
            return response

        error = 'Invalid email or password.'

    return render(request, 'accounts/login.html', {'error': error, 'next': next_url})


def logout_view(request):
    response = redirect('login')
    response.delete_cookie(settings.JWT_ACCESS_COOKIE)
    response.delete_cookie(settings.JWT_REFRESH_COOKIE)
    return response


def change_password_view(request):
    error = None

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not new_password or new_password != confirm_password:
            error = 'Passwords do not match.'
        else:
            try:
                validate_password(new_password, user=request.user)
            except ValidationError as exc:
                error = ' '.join(exc.messages)

        if not error:
            request.user.set_password(new_password)
            request.user.must_change_password = False
            request.user.save(update_fields=['password', 'must_change_password'])
            return redirect('hello_dashboard')

    return render(request, 'accounts/change_password.html', {'error': error})


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    account = (
        SavingsAccount.objects.filter(user=request.user, active=True)
        .order_by('created_at')
        .first()
    )

    return render(request, 'accounts/profile.html', {
        'account': account,
    })


def change_email_view(request):
    if not request.user.is_authenticated:
        return redirect('login')

    error = None
    success = None

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()

        if not email:
            error = 'Email is required.'
        elif User.objects.exclude(pk=request.user.pk).filter(email=email).exists():
            error = 'This email is already in use.'

        if not error:
            request.user.email = email
            request.user.save(update_fields=['email'])
            success = 'Email updated.'

    return render(request, 'accounts/change_email.html', {
        'error': error,
        'success': success,
    })
