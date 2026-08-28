from django.contrib import admin

from expenses.models import Expense
from expenses.services import generate_expense_payments


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_id', 'expense_name', 'amount', 'active', 'created_at')
    list_filter = ('active',)
    search_fields = ('expense_id', 'expense_name')
    filter_horizontal = ('excluded_accounts',)
    readonly_fields = ('expense_id', 'created_at', 'updated_at')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not change:
            generate_expense_payments(form.instance)
