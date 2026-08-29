from decimal import Decimal

CURRENCY_SYMBOL = '₹'

ANNUAL_DUE = Decimal('6000.00')
MONTHLY_DUE = Decimal('500.00')
MONTHLY_FINE = Decimal('50.00')

# Toggle fines across the app.
# - True: fine module works as before
# - False: fine is not calculated/shown and fine payments are disabled
FINE_ALLOWED = False
