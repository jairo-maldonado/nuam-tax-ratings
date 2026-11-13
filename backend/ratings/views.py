from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBroker
from audit.services import log_upload_event

from .models import TaxRating
from .services import CsvValidationError, build_error, process_ratings_csv


def unprocessable_response(errors):
    return Response(
        {
            "detail": "CSV validation failed.",
            "error_count": len(errors),
            "errors": errors,
        },
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


class RatingsUploadView(APIView):
    permission_classes = [IsBroker]
    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            errors = [
                build_error(
                    None,
                    "file",
                    "file_required",
                    "A CSV file is required in the 'file' field.",
                )
            ]
            log_upload_event(
                user=request.user,
                filename=None,
                status_str="REJECTED",
                errors=errors,
            )
            return unprocessable_response(errors)

        try:
            created = process_ratings_csv(uploaded_file, request.user)
        except CsvValidationError as exc:
            log_upload_event(
                user=request.user,
                filename=uploaded_file.name,
                status_str="REJECTED",
                errors=exc.errors,
            )
            return unprocessable_response(exc.errors)

        log_upload_event(
            user=request.user,
            filename=uploaded_file.name,
            status_str="SUCCESS",
            created_count=created,
        )
        return Response(
            {"detail": "CSV processed successfully.", "created": created},
            status=status.HTTP_201_CREATED,
        )


class RatingsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = TaxRating.objects.select_related("uploaded_by").all()

        issuer_rut = request.query_params.get("issuer_rut")
        tax_year = request.query_params.get("tax_year")
        declaration_type = request.query_params.get("declaration_type")

        if issuer_rut:
            qs = qs.filter(issuer_rut__icontains=issuer_rut.strip())
        if tax_year and tax_year.isdigit():
            qs = qs.filter(tax_year=int(tax_year))
        if declaration_type:
            qs = qs.filter(declaration_type=declaration_type)

        data = [
            {
                "id": r.id,
                "issuer_rut": r.issuer_rut,
                "tax_year": r.tax_year,
                "declaration_type": r.declaration_type,
                "risk_factor": str(r.risk_factor),
                "uploaded_by": r.uploaded_by.username,
                "created_at": r.created_at.isoformat(),
            }
            for r in qs[:200]
        ]
        return Response({"results": data})