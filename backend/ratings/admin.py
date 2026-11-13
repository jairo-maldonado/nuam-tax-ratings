from django.contrib import admin

from .models import TaxRating


@admin.register(TaxRating)
class TaxRatingAdmin(admin.ModelAdmin):
    list_display = (
        "issuer_rut",
        "tax_year",
        "declaration_type",
        "risk_factor",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("tax_year", "declaration_type")
    search_fields = ("issuer_rut",)