from django.contrib import admin

from savings.models import SavingsAccount


@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ('account_id', 'user', 'balance', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('account_id', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('account_id', 'created_at', 'updated_at')
