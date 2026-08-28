import uuid

from django.db import models

from core.models import BaseModel
from savings.models import SavingsAccount


class Payment(BaseModel):
    class Type(models.TextChoices):
        CONTRIBUTION = 'contribution', 'Contribution'
        EXPENSE = 'expense', 'Expense'
        LOAN_REPAYMENT = 'loan_repayment', 'Loan Repayment'
        LOAN_DISBURSEMENT = 'loan_disbursement', 'Loan Disbursement'
        FINE = 'fine', 'Fine'
        INCOME = 'income', 'Income'
        INTEREST = 'interest', 'Interest'
        FINE_REDISTRIBUTION = 'fine_redistribution', 'Fine Redistribution'

    class EntryType(models.TextChoices):
        DEBIT = 'dr', 'Debit'
        CREDIT = 'cr', 'Credit'

    transaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=Type.choices, default=Type.CONTRIBUTION)
    entry_type = models.CharField(max_length=2, choices=EntryType.choices, default=EntryType.CREDIT)
    savings_account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name='payments',
    )

    @property
    def user_full_name(self):
        return self.savings_account.user.get_full_name()

    def __str__(self):
        return f'{self.transaction_id} - {self.amount}'
