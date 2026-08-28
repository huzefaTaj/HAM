from django.db import models

from core.models import BaseModel
from savings.models import SavingsAccount


class Fine(BaseModel):
    savings_account = models.OneToOneField(
        SavingsAccount,
        on_delete=models.CASCADE,
        related_name='fine',
    )
    fine_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.savings_account.account_id} - {self.fine_due}'
