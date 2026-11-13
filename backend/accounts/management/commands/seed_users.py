from django.core.management.base import BaseCommand

from accounts.models import User

SEED_USERS = [
    {
        "username": "broker1",
        "email": "broker1@nuam.test",
        "password": "Broker#2026",
        "role": User.Role.BROKER,
    },
    {
        "username": "analyst1",
        "email": "analyst1@nuam.test",
        "password": "Analyst#2026",
        "role": User.Role.ANALYST,
    },
]


class Command(BaseCommand):
    help = "Create demo Broker and Analyst users."

    def handle(self, *args, **options):
        for data in SEED_USERS:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"email": data["email"], "role": data["role"]},
            )
            if created:
                user.set_password(data["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created {user}"))
            else:
                self.stdout.write(f"Already exists: {user}")