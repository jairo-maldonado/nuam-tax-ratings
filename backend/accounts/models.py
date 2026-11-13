from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        BROKER = "BROKER", "Broker"
        ANALYST = "ANALYST", "Analyst"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.BROKER,
    )

    def __str__(self):
        return f"{self.username} ({self.role})"