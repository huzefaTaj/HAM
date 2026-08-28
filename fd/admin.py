from django.contrib import admin

from fd.models import FD


@admin.register(FD)
class FDAdmin(admin.ModelAdmin):
    list_display = ('fd_id', 'fd_number', 'amount', 'interest_rate', 'duration_years', 'start_date', 'status')
    list_filter = ('status',)
    search_fields = ('fd_id', 'fd_number')
    filter_horizontal = ('excluded_accounts', 'participant_accounts')
    readonly_fields = ('fd_id', 'status', 'participant_accounts', 'created_at', 'updated_at')
