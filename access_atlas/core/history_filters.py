from __future__ import annotations

import django_filters

from access_atlas.accounts.models import User
from access_atlas.core.global_history import (
    HISTORY_ACTION_CHOICES,
    history_object_type_choices,
    history_user_choices,
)
from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    SEARCH_OPERATOR,
    AccessAtlasFilterSet,
    FilterFieldSpec,
    FilterOperator,
)

OBJECT_ID_OPERATORS = (
    FilterOperator("exact", "is"),
    FilterOperator("not", "is not", "__not"),
)


class GlobalHistoryFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter()
    object_type = django_filters.MultipleChoiceFilter(
        choices=history_object_type_choices,
    )
    object_type__not = django_filters.MultipleChoiceFilter(
        choices=history_object_type_choices,
        exclude=True,
    )
    object_id = django_filters.CharFilter()
    object_id__not = django_filters.CharFilter()
    action = django_filters.MultipleChoiceFilter(choices=HISTORY_ACTION_CHOICES)
    action__not = django_filters.MultipleChoiceFilter(
        choices=HISTORY_ACTION_CHOICES,
        exclude=True,
    )
    user = django_filters.MultipleChoiceFilter(choices=history_user_choices)
    user__not = django_filters.MultipleChoiceFilter(
        choices=history_user_choices,
        exclude=True,
    )

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec(
            "object_type",
            "Object type",
            "multiselect",
            CHOICE_OPERATORS,
            choices=history_object_type_choices,
        ),
        FilterFieldSpec(
            "object_id",
            "Object ID",
            "text",
            OBJECT_ID_OPERATORS,
            placeholder="Object ID",
        ),
        FilterFieldSpec(
            "action",
            "Action",
            "multiselect",
            CHOICE_OPERATORS,
            choices=HISTORY_ACTION_CHOICES,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all actions",
        ),
        FilterFieldSpec(
            "user",
            "User",
            "multiselect",
            CHOICE_OPERATORS,
            choices=history_user_choices,
        ),
    )

    class Meta:
        model = User
        fields: list[str] = []
