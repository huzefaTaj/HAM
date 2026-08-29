from core.constants import CURRENCY_SYMBOL, FINE_ALLOWED


def currency(request):
    return {
        'CURRENCY_SYMBOL': CURRENCY_SYMBOL,
        'FINE_ALLOWED': FINE_ALLOWED,
    }
