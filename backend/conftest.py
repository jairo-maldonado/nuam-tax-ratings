import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User

PASSWORD = "StrongPass#2026"


def build_authenticated_client(user):
    client = APIClient()
    access_token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def broker(db):
    return User.objects.create_user(
        username="broker_fixture", password=PASSWORD, role=User.Role.BROKER
    )


@pytest.fixture
def analyst(db):
    return User.objects.create_user(
        username="analyst_fixture", password=PASSWORD, role=User.Role.ANALYST
    )


@pytest.fixture
def broker_client(broker):
    return build_authenticated_client(broker)


@pytest.fixture
def analyst_client(analyst):
    return build_authenticated_client(analyst)