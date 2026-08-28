from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User
from savings.models import SavingsAccount


@receiver(post_save, sender=User)
def create_savings_account(sender, instance, created, **kwargs):
    if created:
        SavingsAccount.objects.create(user=instance)
