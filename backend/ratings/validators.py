import re

from django.core.exceptions import ValidationError

RUT_PATTERN = re.compile(r"^\d{7,8}-[\dK]$")


def normalize_rut(raw_rut: str) -> str:
    return raw_rut.replace(".", "").replace(" ", "").upper()


def compute_check_digit(body: str) -> str:
    total = 0
    factor = 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)


def validate_rut(value: str) -> None:
    rut = normalize_rut(value)
    if not RUT_PATTERN.match(rut):
        raise ValidationError(
            "Invalid RUT format. Expected 12345678-5.",
            code="invalid_rut_format",
        )
    body, check_digit = rut.split("-")
    if compute_check_digit(body) != check_digit:
        raise ValidationError(
            "Invalid RUT check digit.",
            code="invalid_rut_check_digit",
        )