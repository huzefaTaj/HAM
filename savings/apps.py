from django.apps import AppConfig


class SavingsConfig(AppConfig):
    name = 'savings'

    def ready(self):
        import savings.signals  # noqa: F401
