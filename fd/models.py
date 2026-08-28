import re
from decimal import Decimal

from django.db import models, transaction

from core.models import BaseModel
from savings.models import SavingsAccount

FD_ID_PREFIX = 'FD'
FD_ID_PATTERN = re.compile(rf'^{FD_ID_PREFIX}(\d+)$')


class FD(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'

    fd_id = models.CharField(max_length=20, unique=True, editable=False)
    fd_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    duration_years = models.PositiveIntegerField()
    start_date = models.DateField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    excluded_accounts = models.ManyToManyField(
        SavingsAccount,
        related_name='excluded_fds',
        blank=True,
    )
    participant_accounts = models.ManyToManyField(
        SavingsAccount,
        related_name='fds',
        blank=True,
    )

    def save(self, *args, **kwargs):
        if not self.fd_id:
            self.fd_id = self._generate_fd_id()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_fd_id(cls):
        with transaction.atomic():
            last = (
                cls.objects.select_for_update()
                .filter(fd_id__startswith=FD_ID_PREFIX)
                .order_by('-created_at')
                .first()
            )
            next_number = 1
            if last:
                match = FD_ID_PATTERN.match(last.fd_id)
                if match:
                    next_number = int(match.group(1)) + 1
            return f'{FD_ID_PREFIX}{next_number:03d}'

    @property
    def interest_amount(self):
        """Simple interest over the full term: principal * rate * years / 100."""
        return (self.amount * self.interest_rate * self.duration_years / Decimal('100')).quantize(Decimal('0.01'))

    def __str__(self):
        return f'{self.fd_id} - {self.fd_number}'
