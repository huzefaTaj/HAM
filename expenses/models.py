import re

from django.db import models, transaction

from core.models import BaseModel
from savings.models import SavingsAccount

EXPENSE_ID_PREFIX = 'EXP'
EXPENSE_ID_PATTERN = re.compile(rf'^{EXPENSE_ID_PREFIX}(\d+)$')


class Expense(BaseModel):
    expense_id = models.CharField(max_length=20, unique=True, editable=False)
    expense_name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    excluded_accounts = models.ManyToManyField(
        SavingsAccount,
        related_name='excluded_expenses',
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.expense_id:
            self.expense_id = self._generate_expense_id()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_expense_id(cls):
        with transaction.atomic():
            last = (
                cls.objects.select_for_update()
                .filter(expense_id__startswith=EXPENSE_ID_PREFIX)
                .order_by('-created_at')
                .first()
            )
            next_number = 1
            if last:
                match = EXPENSE_ID_PATTERN.match(last.expense_id)
                if match:
                    next_number = int(match.group(1)) + 1
            return f'{EXPENSE_ID_PREFIX}{next_number:03d}'

    def __str__(self):
        return f'{self.expense_id} - {self.expense_name}'
