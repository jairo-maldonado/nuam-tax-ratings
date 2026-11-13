from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBroker

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
            return unprocessable_response(
                [
                    build_error(
                        None,
                        "file",
                        "file_required",
                        "A CSV file is required in the 'file' field.",
                    )
                ]
            )

        try:
            created = process_ratings_csv(uploaded_file, request.user)
        except CsvValidationError as exc:
            return unprocessable_response(exc.errors)

        return Response(
            {"detail": "CSV processed successfully.", "created": created},
            status=status.HTTP_201_CREATED,
        )