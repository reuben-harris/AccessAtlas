from collections.abc import Callable, Iterable, Sequence
from copy import copy
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import QueryDict

from access_atlas.core.imports import preserved_query_items
from access_atlas.core.pagination import normalize_per_page, page_size_options_for


@dataclass
class BulkEditResult:
    updated: int = 0


@dataclass(frozen=True)
class BulkEditIssue:
    object_id: int
    reason: str


@dataclass
class BulkEditValidation:
    issues: list[BulkEditIssue]

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def by_object_id(self) -> dict[int, str]:
        return {issue.object_id: issue.reason for issue in self.issues}

    def by_job_id(self) -> dict[int, str]:
        """Compatibility alias while Jobs is the only bulk-edit object."""
        return self.by_object_id()


class NullableBulkEditFormMixin:
    """Shared nullify-checkbox contract for nullable bulk-edit fields."""

    nullable_fields: Sequence[str] = ()
    nullable_field_labels: dict[str, str] = {}
    nullify_field_name = "_nullify"

    def nullified_fields(self) -> set[str]:
        raw_value = (
            self.data.getlist(self.nullify_field_name)
            if hasattr(self.data, "getlist")
            else self.data.get(self.nullify_field_name, [])
        )
        if isinstance(raw_value, str):
            raw_value = [raw_value]
        return set(raw_value) & set(self.nullable_fields)

    def nullify_label_for(self, field_name: str) -> str:
        return self.nullable_field_labels.get(
            field_name,
            f"Set {field_name.replace('_', ' ')} to null",
        )

    def nullable_field_label_map(self) -> dict[str, str]:
        return {
            field_name: self.nullify_label_for(field_name)
            for field_name in self.nullable_fields
        }


def integer_values_from_request(request, field_name: str) -> set[int]:
    return integer_values_from_data_sources(
        field_name,
        request.POST,
        request.GET,
    )


def integer_values_from_data_sources(field_name: str, *data_sources) -> set[int]:
    values: set[int] = set()
    for data_source in data_sources:
        for raw_value in data_source.getlist(field_name):
            try:
                values.add(int(raw_value))
            except TypeError, ValueError:
                continue
    return values


def selected_object_ids_from_request(request) -> set[int]:
    return integer_values_from_request(request, "pk")


def excluded_object_ids_from_request(request) -> set[int]:
    return integer_values_from_request(request, "_exclude")


def bulk_queryset_from_request(
    request,
    *,
    base_queryset,
    filterset_class,
    select_all_queryset: Callable | None = None,
):
    excluded_ids = excluded_object_ids_from_request(request)
    if "_all" in request.POST or "_all" in request.GET:
        filterset = filterset_class(
            data=request.GET.copy(),
            queryset=base_queryset,
            request=request,
        )
        queryset = filterset.qs
        if select_all_queryset is not None:
            queryset = select_all_queryset(queryset)
    else:
        selected_ids = selected_object_ids_from_request(request)
        queryset = base_queryset.filter(pk__in=selected_ids)
    if excluded_ids:
        queryset = queryset.exclude(pk__in=excluded_ids)
    return queryset


def bulk_preview_url(request, *, route_name: str) -> str:
    query = request.GET.copy()
    if "_all" in request.POST:
        query["_all"] = "1"
        query.pop("pk", None)
        query.pop("_exclude", None)
    else:
        selected_ids = (
            integer_values_from_data_sources("pk", request.POST)
            if request.method == "POST" and request.POST.getlist("pk")
            else selected_object_ids_from_request(request)
        )
        query.setlist(
            "pk",
            [str(object_id) for object_id in sorted(selected_ids)],
        )
        query.pop("_all", None)
        query.pop("_exclude", None)
    query.pop("page", None)
    query_string = query.urlencode()

    from django.urls import reverse

    url = reverse(route_name)
    return f"{url}?{query_string}" if query_string else url


def bulk_selection_signature(queryset) -> list[int]:
    return list(queryset.order_by("pk").values_list("pk", flat=True))


def bulk_edit_session_data(
    post_data,
    editable_fields: Sequence[str],
) -> dict[str, list[str]]:
    data: dict[str, list[str]] = {}
    for field_name in editable_fields:
        values = post_data.getlist(field_name)
        if values:
            data[field_name] = values
    return data


def querydict_from_session(data: dict[str, list[str]]) -> QueryDict:
    query = QueryDict(mutable=True)
    for field_name, values in data.items():
        query.setlist(field_name, values)
    return query


def store_bulk_edit_validation_attempt(
    request,
    *,
    session_key: str,
    queryset,
    post_data,
    editable_fields: Sequence[str],
) -> None:
    request.session[session_key] = {
        "selection": bulk_selection_signature(queryset),
        "data": bulk_edit_session_data(post_data, editable_fields),
    }


def clear_bulk_edit_validation_attempt(request, *, session_key: str) -> None:
    request.session.pop(session_key, None)


def bulk_edit_validation_attempt(request, *, session_key: str, queryset) -> dict | None:
    attempt = request.session.get(session_key)
    if not attempt:
        return None

    original_selection = set(attempt.get("selection") or [])
    current_selection = set(bulk_selection_signature(queryset))
    if not current_selection.issubset(original_selection):
        clear_bulk_edit_validation_attempt(request, session_key=session_key)
        return None
    return attempt


def normalize_bulk_preview_sort(
    value: str | None,
    sort_field_map: dict[str, str],
) -> str:
    if not value:
        return ""
    direction = "-" if value.startswith("-") else ""
    sort_key = value.removeprefix("-")
    if sort_key not in sort_field_map:
        return ""
    return f"{direction}{sort_key}"


def bulk_preview_context(
    request,
    selected_objects,
    *,
    bulk_edit_issues: dict[int, str],
    sort_field_map: dict[str, str],
    object_context_name: str,
):
    sort_value = normalize_bulk_preview_sort(request.GET.get("sort"), sort_field_map)
    errors_only = request.GET.get("errors_only") == "1" and bool(bulk_edit_issues)
    if errors_only:
        selected_objects = selected_objects.filter(pk__in=bulk_edit_issues)
    if sort_value:
        descending = sort_value.startswith("-")
        sort_key = sort_value.removeprefix("-")
        selected_objects = list(
            selected_objects.order_by(
                f"{'-' if descending else ''}{sort_field_map[sort_key]}",
                "pk",
            )
        )
    else:
        selected_objects = list(selected_objects)

    per_page = normalize_per_page(request.GET.get("per_page"))
    page_size_options = page_size_options_for(per_page)
    paginator = Paginator(selected_objects, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return {
        object_context_name: page_obj.object_list,
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
        "preview_control_query_items": preserved_query_items(
            request,
            exclude={"errors_only", "page", "per_page"},
        ),
        "preview_query_items": preserved_query_items(request, exclude={"page"}),
        "preview_total_count": paginator.count,
        "errors_only": errors_only,
        "current_sort": sort_value,
        "current_sort_field": sort_value.removeprefix("-"),
        "current_sort_descending": sort_value.startswith("-"),
        "sort_param": "sort",
    }


def validation_error_message(error: ValidationError) -> str:
    if hasattr(error, "message_dict"):
        messages: list[str] = []
        for field_name, field_messages in error.message_dict.items():
            label = field_name.replace("_", " ").capitalize()
            messages.extend(f"{label}: {message}" for message in field_messages)
        return "; ".join(messages)
    return "; ".join(error.messages)


def validate_bulk_edit_objects[ModelObject](
    objects: Iterable[ModelObject],
    *,
    apply_changes: Callable[[ModelObject], bool],
    blocker_reason: Callable[[ModelObject], str] | None = None,
) -> BulkEditValidation:
    """Validate every selected object against a draft before anything is saved."""
    issues: list[BulkEditIssue] = []

    for obj in objects:
        reason = blocker_reason(obj) if blocker_reason is not None else ""
        if reason:
            issues.append(BulkEditIssue(object_id=obj.pk, reason=reason))
            continue

        draft_object = copy(obj)
        apply_changes(draft_object)
        try:
            draft_object.full_clean()
        except ValidationError as error:
            issues.append(
                BulkEditIssue(
                    object_id=obj.pk,
                    reason=validation_error_message(error),
                )
            )

    return BulkEditValidation(issues=issues)


@transaction.atomic
def bulk_edit_objects[ModelObject](
    objects: Iterable[ModelObject],
    *,
    apply_changes: Callable[[ModelObject], bool],
    validate: Callable[[Iterable[ModelObject]], BulkEditValidation],
    change_reason: str,
) -> BulkEditResult:
    selected_objects = list(objects)
    validation = validate(selected_objects)
    if not validation.is_valid:
        raise ValidationError([issue.reason for issue in validation.issues])

    result = BulkEditResult()
    for obj in selected_objects:
        if not apply_changes(obj):
            continue
        obj._change_reason = change_reason
        obj.save()
        result.updated += 1
    return result
