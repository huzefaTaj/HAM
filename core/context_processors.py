from core.constants import BANK_ACCOUNT_NO, BANK_IFSC, CURRENCY_SYMBOL, FINE_ALLOWED


def currency(request):
    return {
        'CURRENCY_SYMBOL': CURRENCY_SYMBOL,
        'FINE_ALLOWED': FINE_ALLOWED,
        'BANK_ACCOUNT_NO': BANK_ACCOUNT_NO,
        'BANK_IFSC': BANK_IFSC,
    }
