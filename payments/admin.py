from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'savings_account', 'user_full_name', 'payment_type', 'entry_type', 'amount', 'active', 'created_at')
    list_filter = ('payment_type', 'entry_type', 'active')
    search_fields = (
        'transaction_id',
        'savings_account__account_id',
        'savings_account__user__email',
        'savings_account__user__first_name',
        'savings_account__user__last_name',
    )
    readonly_fields = ('transaction_id', 'user_full_name', 'created_at', 'updated_at')
