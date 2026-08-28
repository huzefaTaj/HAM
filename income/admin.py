from django.contrib import admin

from income.models import Income
from income.services import generate_income_payments


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('income_id', 'income_name', 'income_type', 'amount', 'active', 'created_at')
    list_filter = ('income_type', 'active')
    search_fields = ('income_id', 'income_name')
    filter_horizontal = ('excluded_accounts',)
    readonly_fields = ('income_id', 'created_at', 'updated_at')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not change:
            generate_income_payments(form.instance)
