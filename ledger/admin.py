from django.contrib import admin

from ledger.models import Fine


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ('savings_account', 'fine_due', 'active', 'updated_at')
    list_filter = ('active',)
    search_fields = (
        'savings_account__account_id',
        'savings_account__user__email',
        'savings_account__user__first_name',
        'savings_account__user__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')
