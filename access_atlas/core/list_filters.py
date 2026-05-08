from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

import django_filters
from django.db.models import Q, QuerySet
from django.http import QueryDict

ChoiceSource = Iterable[tuple[str, str]] | Callable[[], Iterable[tuple[str, str]]]
ChoiceAttributeSource = Callable[[str], Mapping[str, str]]
FILTER_STATE_PARAM = "_filters"
FILTER_STATE_UPDATE = "update"


@dataclass(frozen=True)
class FilterOperator:
    value: str
    label: str
    suffix: str = ""
    no_value: bool = False
    submitted_value: str = ""

    def parameter_name(self, field_name: str) -> str:
        return f"{field_name}{self.suffix}"


@dataclass(frozen=True)
class FilterFieldSpec:
    name: str
    label: str
    input_type: str
    operators: tuple[FilterOperator, ...]
    choices: ChoiceSource = ()
    placeholder: str = ""
    show_control: bool = True
    collapse_chip_when_all_choices: bool = False
    all_choices_chip_label: str = "all options"
    choice_attributes: ChoiceAttributeSource | None = None

    def resolved_choices(self) -> list[tuple[str, str]]:
        choices = self.choices() if callable(self.choices) else self.choices
        return [(str(value), str(label)) for value, label in choices]

    def resolved_choice_attributes(self, value: str) -> dict[str, str]:
        if self.choice_attributes is None:
            return {}
        return {
            str(key): str(attribute_value)
            for key, attribute_value in self.choice_attributes(value).items()
        }


TEXT_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
    FilterOperator("icontains", "contains", "__icontains"),
    FilterOperator("istartswith", "starts with", "__istartswith"),
    FilterOperator("iendswith", "ends with", "__iendswith"),
    FilterOperator("iexact", "equals (case-insensitive)", "__iexact"),
    FilterOperator("regex", "matches pattern", "__regex"),
    FilterOperator(
        "iregex",
        "matches pattern (case-insensitive)",
        "__iregex",
    ),
)
CHOICE_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
)
RELATION_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
    FilterOperator(
        "empty_true",
        "is empty",
        "__empty",
        no_value=True,
        submitted_value="true",
    ),
    FilterOperator(
        "empty_false",
        "is not empty",
        "__empty",
        no_value=True,
        submitted_value="false",
    ),
)
REQUIRED_RELATION_OPERATORS = CHOICE_OPERATORS
DATE_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
    FilterOperator("gt", "after", "__gt"),
    FilterOperator("gte", "on or after", "__gte"),
    FilterOperator("lt", "before", "__lt"),
    FilterOperator("lte", "on or before", "__lte"),
    FilterOperator(
        "empty_true",
        "is empty",
        "__empty",
        no_value=True,
        submitted_value="true",
    ),
    FilterOperator(
        "empty_false",
        "is not empty",
        "__empty",
        no_value=True,
        submitted_value="false",
    ),
)
NUMBER_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
    FilterOperator("gt", "greater than", "__gt"),
    FilterOperator("gte", "at least", "__gte"),
    FilterOperator("lt", "less than", "__lt"),
    FilterOperator("lte", "at most", "__lte"),
    FilterOperator(
        "empty_true",
        "is empty",
        "__empty",
        no_value=True,
        submitted_value="true",
    ),
    FilterOperator(
        "empty_false",
        "is not empty",
        "__empty",
        no_value=True,
        submitted_value="false",
    ),
)
TAG_OPERATORS = (
    FilterOperator("exact", "has these tags"),
    FilterOperator("not", "does not have these tags", "__not"),
)
SEARCH_OPERATOR = (FilterOperator("icontains", "contains"),)


class EmptyValueFilter(django_filters.BooleanFilter):
    """Filter nullable fields, optionally treating blank strings as empty."""

    def __init__(self, *args, include_blank: bool = False, **kwargs):
        self.include_blank = include_blank
        super().__init__(*args, **kwargs)

    def filter(self, qs: QuerySet, value: bool | None) -> QuerySet:
        if value is None:
            return qs
        predicate = Q(**{f"{self.field_name}__isnull": True})
        if self.include_blank:
            predicate |= Q(**{self.field_name: ""})
        if value:
            return qs.filter(predicate)
        return qs.exclude(predicate)


class AccessAtlasFilterSet(django_filters.FilterSet):
    """Shared filter metadata and query-string helpers for object list filters."""

    filter_specs: tuple[FilterFieldSpec, ...] = ()
    defaulted_filter_params: set[str]
    clear_all_overrides: dict[str, list[str]] = {}

    def __init__(self, *args, **kwargs):
        if args:
            args = (ensure_querydict(args[0]), *args[1:])
        if "data" in kwargs:
            kwargs["data"] = ensure_querydict(kwargs["data"])
        self.defaulted_filter_params = set()
        super().__init__(*args, **kwargs)

    @classmethod
    def filter_parameter_names(cls) -> set[str]:
        names = set()
        for spec in cls.filter_specs:
            for operator in spec.operators:
                names.add(operator.parameter_name(spec.name))
        return names

    def filter_controls(self) -> list[dict[str, object]]:
        controls = []
        for spec in self.filter_specs:
            if not spec.show_control:
                continue
            operator, values = selected_operator_and_values(spec, self.data)
            controls.append(
                {
                    "name": spec.name,
                    "label": spec.label,
                    "input_type": spec.input_type,
                    "operators": [
                        {
                            "value": item.value,
                            "label": item.label,
                            "suffix": item.suffix,
                            "no_value": item.no_value,
                            "submitted_value": item.submitted_value,
                            "selected": item.value == operator.value,
                        }
                        for item in spec.operators
                    ],
                    "uses_empty_operator": any(
                        item.no_value for item in spec.operators
                    ),
                    "current_operator": operator.value,
                    "values": values,
                    "value": values[0] if values else "",
                    "choices": [
                        {
                            "value": value,
                            "label": label,
                            "selected": value in values,
                            **spec.resolved_choice_attributes(value),
                        }
                        for value, label in spec.resolved_choices()
                    ],
                    "placeholder": spec.placeholder,
                }
            )
        return controls

    def active_chips(self, request) -> list[dict[str, str]]:
        chips = []
        for spec in self.filter_specs:
            choice_labels = dict(spec.resolved_choices())
            for operator in spec.operators:
                parameter_name = operator.parameter_name(spec.name)
                values = cleaned_values(self.data.getlist(parameter_name))
                if not values and not (
                    operator.no_value and parameter_name in self.data
                ):
                    continue
                if is_collapsed_all_choices_chip(spec, operator, values):
                    chips.append(
                        {
                            "label": (
                                f"{spec.label} {operator.label} "
                                f"{spec.all_choices_chip_label}"
                            ),
                            "clear_url": self.clear_filter_url(
                                request,
                                parameter_name,
                            ),
                        }
                    )
                    continue
                if operator.no_value:
                    submitted = self.data.get(parameter_name)
                    if submitted != operator.submitted_value:
                        continue
                    chips.append(
                        {
                            "label": f"{spec.label} {operator.label}",
                            "clear_url": self.clear_filter_url(
                                request,
                                parameter_name,
                            ),
                        }
                    )
                    continue

                for value in values:
                    label = choice_labels.get(value, value)
                    chips.append(
                        {
                            "label": f"{spec.label} {operator.label} {label}",
                            "clear_url": self.clear_filter_url(
                                request,
                                parameter_name,
                                value,
                            ),
                        }
                    )
        return chips

    def clear_filter_url(
        self,
        request,
        parameter_name: str,
        value: str | None = None,
    ) -> str:
        query = request.GET.copy()
        query.pop("page", None)
        query.setlist(FILTER_STATE_PARAM, [FILTER_STATE_UPDATE])

        if parameter_name in self.defaulted_filter_params:
            query.setlist(
                parameter_name,
                self.clear_all_overrides.get(parameter_name, []),
            )
            return querydict_url(request, query)

        if value is None:
            query.pop(parameter_name, None)
        else:
            remaining = [
                item for item in query.getlist(parameter_name) if item != value
            ]
            if remaining:
                query.setlist(parameter_name, remaining)
            else:
                query.pop(parameter_name, None)
        return querydict_url(request, query)

    def clear_all_url(self, request) -> str:
        query = request.GET.copy()
        query.pop("page", None)
        query.setlist(FILTER_STATE_PARAM, [FILTER_STATE_UPDATE])
        for parameter_name in self.filter_parameter_names():
            query.pop(parameter_name, None)
        for parameter_name, values in self.clear_all_overrides.items():
            query.setlist(parameter_name, values)
        return querydict_url(request, query)


def cleaned_values(values: Iterable[str]) -> list[str]:
    return [str(value) for value in values if str(value).strip()]


def is_collapsed_all_choices_chip(
    spec: FilterFieldSpec,
    operator: FilterOperator,
    values: list[str],
) -> bool:
    if not spec.collapse_chip_when_all_choices or operator.suffix:
        return False
    all_choice_values = {value for value, _label in spec.resolved_choices()}
    return bool(all_choice_values) and set(values) == all_choice_values


def ensure_querydict(data):
    if data is None or isinstance(data, QueryDict):
        return data
    query = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, list | tuple | set):
            query.setlist(key, [str(item) for item in value])
        else:
            query.setlist(key, [str(value)])
    return query


def selected_operator_and_values(
    spec: FilterFieldSpec,
    data: QueryDict,
) -> tuple[FilterOperator, list[str]]:
    for operator in spec.operators:
        parameter_name = operator.parameter_name(spec.name)
        if operator.no_value:
            if data.get(parameter_name) == operator.submitted_value:
                return operator, []
            continue
        values = cleaned_values(data.getlist(parameter_name))
        if values:
            return operator, values
    return spec.operators[0], []


def querydict_url(request, query: QueryDict) -> str:
    query_string = query.urlencode()
    return f"{request.path}?{query_string}" if query_string else request.path


def preserved_query_items(
    request,
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


def query_string_without_page(request) -> str:
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()
