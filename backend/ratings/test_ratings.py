import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from ratings.models import TaxRating
from ratings.services import MAX_FILE_SIZE_BYTES, MAX_ROWS

pytestmark = pytest.mark.django_db

HEADER = "issuer_rut,tax_year,declaration_type,risk_factor\n"
RUT_A = "12345678-5"
RUT_B = "11111111-1"
INVALID_CHECK_DIGIT_RUT = "12345678-9"


def row(rut=RUT_A, year=2025, declaration_type="DJ_1949", factor="0.5000"):
    return f"{rut},{year},{declaration_type},{factor}"


def build_csv(*rows, header=HEADER, name="ratings.csv"):
    content = header + "\n".join(rows)
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


def upload(client, csv_file):
    return client.post(
        reverse("ratings-upload"), {"file": csv_file}, format="multipart"
    )


def error_codes(response):
    return [error["code"] for error in response.data["errors"]]


class TestSuccessfulUpload:
    def test_valid_csv_creates_ratings(self, broker_client, broker):
        response = upload(
            broker_client,
            build_csv(row(RUT_A, factor="0.5000"), row(RUT_B, factor="1.0000")),
        )
        assert response.status_code == 201
        assert response.data["created"] == 2
        assert TaxRating.objects.filter(uploaded_by=broker).count() == 2

    def test_factors_summing_exactly_one_are_accepted(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(factor="0.4000"), row(factor="0.6000")),
        )
        assert response.status_code == 201
        assert TaxRating.objects.count() == 2

    def test_same_rut_in_different_years_is_independent(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(year=2024, factor="0.9000"), row(year=2025, factor="0.9000")),
        )
        assert response.status_code == 201

    def test_same_rut_in_different_declaration_types_is_independent(
        self, broker_client
    ):
        response = upload(
            broker_client,
            build_csv(
                row(declaration_type="DJ_1949", factor="0.9000"),
                row(declaration_type="DJ_1922", factor="0.9000"),
            ),
        )
        assert response.status_code == 201

    def test_rut_with_dots_is_normalized_on_save(self, broker_client):
        response = upload(broker_client, build_csv(row(rut="12.345.678-5")))
        assert response.status_code == 201
        assert TaxRating.objects.get().issuer_rut == RUT_A

    def test_utf8_bom_file_is_accepted(self, broker_client):
        content = (HEADER + row()).encode("utf-8-sig")
        csv_file = SimpleUploadedFile("bom.csv", content, content_type="text/csv")
        response = upload(broker_client, csv_file)
        assert response.status_code == 201

    def test_headers_are_case_and_space_insensitive(self, broker_client):
        header = " ISSUER_RUT , Tax_Year ,declaration_type,RISK_FACTOR\n"
        response = upload(broker_client, build_csv(row(), header=header))
        assert response.status_code == 201

    def test_second_upload_completing_exactly_one_is_accepted(self, broker_client):
        first = upload(broker_client, build_csv(row(factor="0.6000")))
        second = upload(broker_client, build_csv(row(factor="0.4000")))
        assert first.status_code == 201
        assert second.status_code == 201
        assert TaxRating.objects.count() == 2


class TestFactorSumRule:
    def test_sum_above_one_returns_structured_422(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(factor="0.7000"), row(factor="0.4000")),
        )
        assert response.status_code == 422
        assert response.data["error_count"] == 1
        error = response.data["errors"][0]
        assert error["row"] == 3
        assert error["field"] == "risk_factor"
        assert error["code"] == "factor_sum_exceeded"
        assert TaxRating.objects.count() == 0

    def test_sum_one_ten_thousandth_above_limit_is_rejected(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(factor="0.5000"), row(factor="0.5001")),
        )
        assert response.status_code == 422
        assert error_codes(response) == ["factor_sum_exceeded"]

    def test_sum_includes_existing_database_rows(self, broker_client):
        first = upload(broker_client, build_csv(row(factor="0.6000")))
        assert first.status_code == 201

        second = upload(broker_client, build_csv(row(factor="0.5000")))
        assert second.status_code == 422
        assert error_codes(second) == ["factor_sum_exceeded"]
        assert TaxRating.objects.count() == 1

    def test_single_factor_above_one_is_rejected(self, broker_client):
        response = upload(broker_client, build_csv(row(factor="1.0001")))
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_risk_factor"]


class TestDuplicates:
    def test_duplicate_row_in_same_file_is_rejected(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(factor="0.3000"), row(factor="0.3000")),
        )
        assert response.status_code == 422
        assert response.data["errors"][0]["row"] == 3
        assert error_codes(response) == ["duplicate_in_file"]
        assert TaxRating.objects.count() == 0

    def test_duplicate_detected_after_rut_normalization(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(rut=RUT_A), row(rut="12.345.678-5")),
        )
        assert response.status_code == 422
        assert error_codes(response) == ["duplicate_in_file"]

    def test_duplicate_of_existing_record_is_rejected(self, broker_client):
        first = upload(broker_client, build_csv(row(factor="0.3000")))
        assert first.status_code == 201

        second = upload(broker_client, build_csv(row(factor="0.3000")))
        assert second.status_code == 422
        assert error_codes(second) == ["duplicate_in_database"]
        assert TaxRating.objects.count() == 1


class TestRowValidation:
    def test_invalid_check_digit_is_rejected(self, broker_client):
        response = upload(broker_client, build_csv(row(rut=INVALID_CHECK_DIGIT_RUT)))
        assert response.status_code == 422
        error = response.data["errors"][0]
        assert error["row"] == 2
        assert error["field"] == "issuer_rut"
        assert error["code"] == "invalid_rut_check_digit"

    @pytest.mark.parametrize(
        "bad_rut", ["abc", "12345678", "1234-5", "", "123456789-0"]
    )
    def test_malformed_rut_is_rejected(self, broker_client, bad_rut):
        response = upload(broker_client, build_csv(row(rut=bad_rut)))
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_rut_format"]

    @pytest.mark.parametrize("bad_year", ["abc", "1999", "2101", "20.25", "", "-2025"])
    def test_invalid_tax_year_is_rejected(self, broker_client, bad_year):
        response = upload(broker_client, build_csv(row(year=bad_year)))
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_tax_year"]

    @pytest.mark.parametrize("bad_type", ["DJ_9999", "", "1949"])
    def test_invalid_declaration_type_is_rejected(self, broker_client, bad_type):
        response = upload(broker_client, build_csv(row(declaration_type=bad_type)))
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_declaration_type"]

    @pytest.mark.parametrize(
        "bad_factor",
        ["abc", "1.5000", "-0.1000", "0.12345", "", "NaN", "Infinity", '"0,5"'],
    )
    def test_invalid_risk_factor_is_rejected(self, broker_client, bad_factor):
        response = upload(broker_client, build_csv(row(factor=bad_factor)))
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_risk_factor"]

    def test_all_row_errors_are_reported_with_structure(self, broker_client):
        response = upload(
            broker_client,
            build_csv(
                row(rut=INVALID_CHECK_DIGIT_RUT),
                row(year="abc"),
                row(factor="2.0000"),
            ),
        )
        assert response.status_code == 422
        assert response.data["error_count"] == 3
        assert [error["row"] for error in response.data["errors"]] == [2, 3, 4]
        for error in response.data["errors"]:
            assert set(error.keys()) == {"row", "field", "code", "message"}


class TestAtomicity:
    def test_one_invalid_row_rejects_the_entire_file(self, broker_client):
        response = upload(
            broker_client,
            build_csv(row(rut=RUT_B), row(rut=INVALID_CHECK_DIGIT_RUT)),
        )
        assert response.status_code == 422
        assert TaxRating.objects.count() == 0

    def test_exceeding_group_rejects_the_entire_file(self, broker_client):
        response = upload(
            broker_client,
            build_csv(
                row(rut=RUT_B, factor="0.5000"),
                row(rut=RUT_A, factor="0.7000"),
                row(rut=RUT_A, factor="0.4000"),
            ),
        )
        assert response.status_code == 422
        assert TaxRating.objects.count() == 0


class TestFileLevelErrors:
    def test_missing_column_is_rejected(self, broker_client):
        header = "issuer_rut,tax_year,declaration_type\n"
        response = upload(
            broker_client, build_csv(f"{RUT_A},2025,DJ_1949", header=header)
        )
        assert response.status_code == 422
        error = response.data["errors"][0]
        assert error["code"] == "missing_columns"
        assert error["row"] is None
        assert "risk_factor" in error["message"]

    def test_header_only_file_is_rejected(self, broker_client):
        response = upload(broker_client, build_csv())
        assert response.status_code == 422
        assert error_codes(response) == ["empty_file"]

    def test_request_without_file_is_rejected(self, broker_client):
        response = broker_client.post(
            reverse("ratings-upload"), {}, format="multipart"
        )
        assert response.status_code == 422
        assert error_codes(response) == ["file_required"]

    def test_non_utf8_file_is_rejected(self, broker_client):
        csv_file = SimpleUploadedFile(
            "bad.csv", b"\x80\x81\x82", content_type="text/csv"
        )
        response = upload(broker_client, csv_file)
        assert response.status_code == 422
        assert error_codes(response) == ["invalid_encoding"]

    def test_file_over_size_limit_is_rejected(self, broker_client):
        csv_file = SimpleUploadedFile(
            "big.csv", b"x" * (MAX_FILE_SIZE_BYTES + 1), content_type="text/csv"
        )
        response = upload(broker_client, csv_file)
        assert response.status_code == 422
        assert error_codes(response) == ["file_too_large"]

    def test_file_over_row_limit_is_rejected(self, broker_client):
        rows = [row(factor="0.0001")] * (MAX_ROWS + 1)
        response = upload(broker_client, build_csv(*rows))
        assert response.status_code == 422
        assert error_codes(response) == ["too_many_rows"]


class TestRolePermissions:
    def test_analyst_cannot_upload(self, analyst_client):
        response = upload(analyst_client, build_csv(row()))
        assert response.status_code == 403
        assert TaxRating.objects.count() == 0

    def test_anonymous_cannot_upload(self, api_client):
        response = upload(api_client, build_csv(row()))
        assert response.status_code == 401
        assert TaxRating.objects.count() == 0

    def test_invalid_token_cannot_upload(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        response = upload(api_client, build_csv(row()))
        assert response.status_code == 401