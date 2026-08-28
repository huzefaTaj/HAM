from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

EXEMPT_PATH_PREFIXES = ('/login', '/logout', '/admin', '/static')
CHANGE_PASSWORD_PATH = '/change-password/'


class JWTCookieAuthenticationMiddleware:
    """Gates every non-exempt page behind a valid JWT access/refresh token cookie."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        user, new_access_token = self._authenticate(request)
        if user is None:
            login_url = reverse('login')
            return redirect(f'{login_url}?next={request.path}')

        if user.must_change_password and request.path != CHANGE_PASSWORD_PATH:
            return redirect(CHANGE_PASSWORD_PATH)

        request.user = user
        response = self.get_response(request)

        if new_access_token:
            response.set_cookie(
                settings.JWT_ACCESS_COOKIE,
                new_access_token,
                httponly=True,
                samesite='Lax',
                secure=not settings.DEBUG,
            )
        return response

    def _authenticate(self, request):
        User = get_user_model()

        access = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        if access:
            try:
                token = AccessToken(access)
                user = User.objects.get(pk=token['user_id'], active=True)
                return user, None
            except (TokenError, User.DoesNotExist, KeyError):
                pass

        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if refresh:
            try:
                token = RefreshToken(refresh)
                user = User.objects.get(pk=token['user_id'], active=True)
                return user, str(token.access_token)
            except (TokenError, User.DoesNotExist, KeyError):
                pass

        return None, None
