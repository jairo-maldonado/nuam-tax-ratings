from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .validators import normalize_rut, validate_rut


class TaxRating(models.Model):
    class DeclarationType(models.TextChoices):
        DJ_1949 = "DJ_1949", "DJ 1949"
        DJ_1922 = "DJ_1922", "DJ 1922"

    issuer_rut = models.CharField(max_length=10, validators=[validate_rut])
    tax_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)]
    )
    declaration_type = models.CharField(
        max_length=7, choices=DeclarationType.choices
    )
    risk_factor = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal("0.0000")),
            MaxValueValidator(Decimal("1.0000")),
        ],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tax_ratings",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["issuer_rut", "tax_year", "declaration_type", "risk_factor"],
                name="unique_rating_per_rut_year_type_factor",
            ),
            models.CheckConstraint(
                condition=models.Q(risk_factor__gte=0) & models.Q(risk_factor__lte=1),
                name="risk_factor_between_0_and_1",
            ),
        ]
        indexes = [
            models.Index(
                fields=["issuer_rut", "tax_year", "declaration_type"],
                name="idx_rating_rut_year_type",
            ),
        ]

    def save(self, *args, **kwargs):
        self.issuer_rut = normalize_rut(self.issuer_rut)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.issuer_rut} | {self.tax_year} | "
            f"{self.declaration_type} | {self.risk_factor}"
        )