import re

from django.db import models, transaction

from core.models import BaseModel
from savings.models import SavingsAccount

INCOME_ID_PREFIX = 'INC'
INCOME_ID_PATTERN = re.compile(rf'^{INCOME_ID_PREFIX}(\d+)$')


class Income(BaseModel):
    class Type(models.TextChoices):
        INCOME = 'income', 'Income'
        INTEREST = 'interest', 'Interest'
        FINE_REDISTRIBUTION = 'fine_redistribution', 'Fine Redistribution'

    income_id = models.CharField(max_length=20, unique=True, editable=False)
    income_type = models.CharField(max_length=20, choices=Type.choices, default=Type.INCOME)
    income_name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    excluded_accounts = models.ManyToManyField(
        SavingsAccount,
        related_name='excluded_incomes',
        blank=True,
    )
    source_payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fine_redistribution_income',
    )

    def save(self, *args, **kwargs):
        if not self.income_id:
            self.income_id = self._generate_income_id()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_income_id(cls):
        with transaction.atomic():
            last = (
                cls.objects.select_for_update()
                .filter(income_id__startswith=INCOME_ID_PREFIX)
                .order_by('-income_id')
                .first()
            )
            next_number = 1
            if last:
                match = INCOME_ID_PATTERN.match(last.income_id)
                if match:
                    next_number = int(match.group(1)) + 1
            return f'{INCOME_ID_PREFIX}{next_number:03d}'

    def __str__(self):
        return f'{self.income_id} - {self.income_name}'
