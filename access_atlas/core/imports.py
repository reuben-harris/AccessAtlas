from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Sequence
from io import StringIO
from typing import Protocol

from django.core.paginator import Paginator
from django.http import HttpRequest

from access_atlas.core.search import normalize_per_page, page_size_options_for

DEFAULT_IMPORT_SORT_PARAM = "sort"


class ImportRow(Protocol):
    """Contract shared by CSV review rows that can be stored in the session."""

    @property
    def is_valid(self) -> bool: ...

    def as_session_data(self) -> dict[str, object]: ...


def read_uploaded_csv_rows(
    uploaded_file,
    *,
    required_headers: Sequence[str],
    optional_headers: Sequence[str],
) -> tuple[list[dict[str, str]] | None, str]:
    """Decode an uploaded CSV and validate the header contract."""

    content = uploaded_file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "CSV file must be UTF-8 encoded."

    reader = csv.DictReader(StringIO(text))
    headers = reader.fieldnames or []
    supported_headers = [*required_headers, *optional_headers]
    if any(header not in supported_headers for header in headers) or any(
        header not in headers for header in required_headers
    ):
        return None, csv_header_error(required_headers, optional_headers)
    return list(reader), ""


def csv_header_error(
    required_headers: Sequence[str],
    optional_headers: Sequence[str],
) -> str:
    required = ",".join(required_headers)
    if not optional_headers:
        return f"CSV headers must include {required}."
    optional = ",".join(optional_headers)
    return f"CSV headers must include {required} and may also include {optional}."


def has_import_row_errors(rows: Iterable[ImportRow]) -> bool:
    return any(not row.is_valid for row in rows)


def store_import_rows(
    request: HttpRequest,
    *,
    session_key: str,
    rows: Iterable[ImportRow],
) -> None:
    request.session[session_key] = [row.as_session_data() for row in rows]
    request.session.modified = True


def load_import_rows[RowT: ImportRow](
    request: HttpRequest,
    *,
    session_key: str,
    row_loader: Callable[[list[dict[str, object]]], list[RowT]],
) -> list[RowT] | None:
    session_rows = request.session.get(session_key)
    if not session_rows:
        return None
    return row_loader(session_rows)


def clear_import_rows(request: HttpRequest, *, session_key: str) -> None:
    request.session.pop(session_key, None)
    request.session.modified = True


def normalize_import_sort_value(
    value: str | None,
    sort_field_map: dict[str, Callable[[ImportRow], object]],
) -> str:
    if not value:
        return ""
    direction = "-" if value.startswith("-") else ""
    sort_key = value.removeprefix("-")
    if sort_key not in sort_field_map:
        return ""
    return f"{direction}{sort_key}"


def sort_import_rows[RowT: ImportRow](
    rows: list[RowT],
    *,
    sort_value: str,
    sort_field_map: dict[str, Callable[[RowT], object]],
) -> list[RowT]:
    """Sort in-session CSV review rows using stable, view-provided row keys."""

    if not sort_value:
        return rows
    descending = sort_value.startswith("-")
    sort_key = sort_value.removeprefix("-")
    key_function = sort_field_map.get(sort_key)
    if key_function is None:
        return rows
    return sorted(rows, key=key_function, reverse=descending)


def preserved_query_items(
    request: HttpRequest,
    *,
    exclude: set[str],
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key in request.GET:
        if key in exclude:
            continue
        for value in request.GET.getlist(key):
            items.append((key, value))
    return items


def import_review_context[RowT: ImportRow](
    request: HttpRequest,
    *,
    rows: list[RowT] | None,
    sort_field_map: dict[str, Callable[[RowT], object]] | None = None,
) -> dict:
    sort_field_map = sort_field_map or {}
    sort_value = normalize_import_sort_value(
        request.GET.get(DEFAULT_IMPORT_SORT_PARAM),
        sort_field_map,
    )
    sorted_rows = (
        sort_import_rows(rows, sort_value=sort_value, sort_field_map=sort_field_map)
        if rows is not None
        else []
    )
    per_page = normalize_per_page(request.GET.get("per_page"))
    page_size_options = page_size_options_for(per_page)
    paginator = Paginator(sorted_rows, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return {
        "rows": page_obj.object_list,
        "has_errors": has_import_row_errors(rows) if rows is not None else False,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": paginator.get_elided_page_range(number=page_obj.number),
        "per_page": per_page,
        "page_size_param": "per_page",
        "page_size_options": page_size_options,
        "per_page_preserved_query_items": preserved_query_items(
            request,
            exclude={"per_page", "page"},
        ),
        "current_sort": sort_value,
        "current_sort_field": sort_value.removeprefix("-"),
        "current_sort_descending": sort_value.startswith("-"),
        "sort_param": DEFAULT_IMPORT_SORT_PARAM,
    }
