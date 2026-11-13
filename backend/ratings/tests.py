from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from accounts.models import User
from ratings.models import TaxRating
from ratings.validators import normalize_rut, validate_rut


@pytest.fixture
def broker(db):
    return User.objects.create_user(
        username="broker_test", password="StrongPass#2026", role=User.Role.BROKER
    )


def make_rating(user, **overrides):
    data = {
        "issuer_rut": "12345678-5",
        "tax_year": 2025,
        "declaration_type": TaxRating.DeclarationType.DJ_1949,
        "risk_factor": Decimal("0.4000"),
        "uploaded_by": user,
    }
    data.update(overrides)
    return TaxRating.objects.create(**data)


class TestRutValidator:
    @pytest.mark.parametrize(
        "rut", ["12345678-5", "11111111-1", "1000005-K", "12.345.678-5", "1000005-k"]
    )
    def test_accepts_valid_ruts(self, rut):
        validate_rut(rut)

    def test_rejects_wrong_check_digit(self):
        with pytest.raises(ValidationError) as error:
            validate_rut("12345678-9")
        assert error.value.code == "invalid_rut_check_digit"

    @pytest.mark.parametrize("rut", ["abc", "12345678", "1234-5", "", "123456789-0"])
    def test_rejects_invalid_format(self, rut):
        with pytest.raises(ValidationError) as error:
            validate_rut(rut)
        assert error.value.code == "invalid_rut_format"

    def test_normalize_removes_dots_and_uppercases(self):
        assert normalize_rut("12.345.678-5") == "12345678-5"
        assert normalize_rut("1000005-k") == "1000005-K"


@pytest.mark.django_db
class TestTaxRatingModel:
    def test_save_normalizes_rut(self, broker):
        rating = make_rating(broker, issuer_rut="12.345.678-5")
        assert rating.issuer_rut == "12345678-5"

    def test_identical_row_raises_integrity_error(self, broker):
        make_rating(broker)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_rating(broker)

    def test_same_key_with_different_factor_is_allowed(self, broker):
        make_rating(broker, risk_factor=Decimal("0.4000"))
        make_rating(broker, risk_factor=Decimal("0.6000"))
        assert TaxRating.objects.count() == 2

    def test_factor_above_one_raises_integrity_error(self, broker):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_rating(broker, risk_factor=Decimal("1.5000"))

    def test_negative_factor_raises_integrity_error(self, broker):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                make_rating(broker, risk_factor=Decimal("-0.1000"))

    def test_factor_exactly_one_is_allowed(self, broker):
        rating = make_rating(broker, risk_factor=Decimal("1.0000"))
        assert rating.risk_factor == Decimal("1.0000")