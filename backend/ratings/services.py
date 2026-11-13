import csv
import io
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .models import TaxRating
from .validators import normalize_rut, validate_rut

REQUIRED_HEADERS = ("issuer_rut", "tax_year", "declaration_type", "risk_factor")
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MAX_FACTOR_SUM = Decimal("1.0000")
FACTOR_DECIMAL_PLACES = 4
MIN_TAX_YEAR = 2000
MAX_TAX_YEAR = 2100
UPLOAD_LOCK_KEY = 482901


class CsvValidationError(Exception):
    def __init__(self, errors):
        super().__init__("CSV validation failed.")
        self.errors = errors


def build_error(row, field, code, message):
    return {"row": row, "field": field, "code": code, "message": message}


def read_csv_rows(uploaded_file):
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        raise CsvValidationError(
            [
                build_error(
                    None,
                    None,
                    "file_too_large",
                    f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit.",
                )
            ]
        )

    try:
        content = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvValidationError(
            [build_error(None, None, "invalid_encoding", "File must be UTF-8 encoded.")]
        )

    try:
        reader = csv.DictReader(io.StringIO(content))
        headers = [
            (header or "").strip().lower() for header in (reader.fieldnames or [])
        ]
        reader.fieldnames = headers

        missing = [header for header in REQUIRED_HEADERS if header not in headers]
        if missing:
            raise CsvValidationError(
                [
                    build_error(
                        None,
                        None,
                        "missing_columns",
                        f"Missing required columns: {', '.join(missing)}.",
                    )
                ]
            )

        rows = list(enumerate(reader, start=2))
    except csv.Error as exc:
        raise CsvValidationError(
            [build_error(None, None, "malformed_csv", f"Malformed CSV: {exc}")]
        )

    if not rows:
        raise CsvValidationError(
            [build_error(None, None, "empty_file", "File has no data rows.")]
        )
    if len(rows) > MAX_ROWS:
        raise CsvValidationError(
            [
                build_error(
                    None,
                    None,
                    "too_many_rows",
                    f"File exceeds the {MAX_ROWS} rows limit.",
                )
            ]
        )
    return rows


def parse_risk_factor(raw_value):
    try:
        value = Decimal(raw_value)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    if value.as_tuple().exponent < -FACTOR_DECIMAL_PLACES:
        return None
    if value < 0 or value > 1:
        return None
    return value


def parse_row(row_number, raw_row):
    errors = []
    raw_rut = (raw_row.get("issuer_rut") or "").strip()
    raw_year = (raw_row.get("tax_year") or "").strip()
    raw_type = (raw_row.get("declaration_type") or "").strip().upper()
    raw_factor = (raw_row.get("risk_factor") or "").strip()

    rut = None
    try:
        validate_rut(raw_rut)
        rut = normalize_rut(raw_rut)
    except ValidationError as exc:
        errors.append(build_error(row_number, "issuer_rut", exc.code, exc.messages[0]))

    tax_year = None
    if (
        raw_year.isascii()
        and raw_year.isdigit()
        and MIN_TAX_YEAR <= int(raw_year) <= MAX_TAX_YEAR
    ):
        tax_year = int(raw_year)
    else:
        errors.append(
            build_error(
                row_number,
                "tax_year",
                "invalid_tax_year",
                f"Tax year must be an integer between {MIN_TAX_YEAR} and {MAX_TAX_YEAR}.",
            )
        )

    declaration_type = None
    if raw_type in TaxRating.DeclarationType.values:
        declaration_type = raw_type
    else:
        errors.append(
            build_error(
                row_number,
                "declaration_type",
                "invalid_declaration_type",
                f"Declaration type must be one of: {', '.join(TaxRating.DeclarationType.values)}.",
            )
        )

    risk_factor = parse_risk_factor(raw_factor)
    if risk_factor is None:
        errors.append(
            build_error(
                row_number,
                "risk_factor",
                "invalid_risk_factor",
                "Risk factor must be a decimal between 0.0000 and 1.0000 "
                f"with at most {FACTOR_DECIMAL_PLACES} decimal places.",
            )
        )

    if errors:
        return None, errors

    return (
        {
            "issuer_rut": rut,
            "tax_year": tax_year,
            "declaration_type": declaration_type,
            "risk_factor": risk_factor,
        },
        [],
    )


def validate_business_rules(parsed_rows):
    errors = []
    accepted = []
    if not parsed_rows:
        return errors, accepted

    ruts = {row["issuer_rut"] for _, row in parsed_rows}
    existing_keys = set()
    totals = defaultdict(Decimal)
    existing_rows = TaxRating.objects.filter(issuer_rut__in=ruts).values_list(
        "issuer_rut", "tax_year", "declaration_type", "risk_factor"
    )
    for rut, year, declaration_type, factor in existing_rows:
        existing_keys.add((rut, year, declaration_type, factor))
        totals[(rut, year, declaration_type)] += factor

    file_keys = set()
    for row_number, row in parsed_rows:
        group = (row["issuer_rut"], row["tax_year"], row["declaration_type"])
        key = group + (row["risk_factor"],)

        if key in existing_keys:
            errors.append(
                build_error(
                    row_number,
                    None,
                    "duplicate_in_database",
                    "Row duplicates an existing record.",
                )
            )
            continue

        if key in file_keys:
            errors.append(
                build_error(
                    row_number,
                    None,
                    "duplicate_in_file",
                    "Row duplicates a previous row in this file.",
                )
            )
            continue

        new_total = totals[group] + row["risk_factor"]
        if new_total > MAX_FACTOR_SUM:
            errors.append(
                build_error(
                    row_number,
                    "risk_factor",
                    "factor_sum_exceeded",
                    f"Factor sum for {group[0]} / {group[1]} / {group[2]} "
                    f"would be {new_total:.4f}, exceeding {MAX_FACTOR_SUM}.",
                )
            )
            continue

        file_keys.add(key)
        totals[group] = new_total
        accepted.append(row)

    return errors, accepted


def process_ratings_csv(uploaded_file, user):
    rows = read_csv_rows(uploaded_file)

    errors = []
    parsed_rows = []
    for row_number, raw_row in rows:
        parsed, row_errors = parse_row(row_number, raw_row)
        errors.extend(row_errors)
        if parsed is not None:
            parsed_rows.append((row_number, parsed))

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [UPLOAD_LOCK_KEY])

        business_errors, accepted = validate_business_rules(parsed_rows)
        errors.extend(business_errors)

        if errors:
            errors.sort(key=lambda error: error["row"] or 0)
            raise CsvValidationError(errors)

        TaxRating.objects.bulk_create(
            [TaxRating(uploaded_by=user, **row) for row in accepted]
        )

    return len(accepted)