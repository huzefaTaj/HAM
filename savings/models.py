import re

from django.conf import settings
from django.db import models, transaction

from core.models import BaseModel

ACCOUNT_ID_PREFIX = 'HAM'
ACCOUNT_ID_PATTERN = re.compile(rf'^{ACCOUNT_ID_PREFIX}(\d+)$')


class SavingsAccount(BaseModel):
    account_id = models.CharField(max_length=20, unique=True, editable=False)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='savings_accounts',
    )

    def save(self, *args, **kwargs):
        if not self.account_id:
            self.account_id = self._generate_account_id()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_account_id(cls):
        with transaction.atomic():
            last = (
                cls.objects.select_for_update()
                .filter(account_id__startswith=ACCOUNT_ID_PREFIX)
                .order_by('-created_at')
                .first()
            )
            next_number = 1
            if last:
                match = ACCOUNT_ID_PATTERN.match(last.account_id)
                if match:
                    next_number = int(match.group(1)) + 1
            return f'{ACCOUNT_ID_PREFIX}{next_number:03d}'

    def __str__(self):
        return self.account_id
