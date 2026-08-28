from django.conf import settings
from django.contrib.auth import authenticate
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from rest_framework_simplejwt.tokens import RefreshToken


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
