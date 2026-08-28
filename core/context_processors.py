from core.constants import CURRENCY_SYMBOL


def currency(request):
    return {'CURRENCY_SYMBOL': CURRENCY_SYMBOL}
