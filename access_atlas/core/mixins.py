from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from access_atlas.accounts.preferences import (
    get_user_preference,
    list_filter_preference_key,
    list_sort_preference_key,
    set_user_preference,
)
from access_atlas.core.global_history import (
    append_query_string,
    history_detail_url,
    history_object_filter_query,
)
from access_atlas.core.history_diff import build_history_diff
from access_atlas.core.list_filters import (
    FILTER_STATE_PARAM,
    FILTER_STATE_UPDATE,
    AccessAtlasFilterSet,
    preserved_query_items,
    query_string_without_page,
    querydict_url,
)


class ObjectFormMixin:
    """Provide consistent form chrome for object create/edit pages."""

    def get_cancel_url(self) -> str:
        obj = getattr(self, "object", None)
        if obj and obj.pk and hasattr(obj, "get_absolute_url"):
            return obj.get_absolute_url()
        return reverse("dashboard")

    def get_form_title(self) -> str:
        obj = getattr(self, "object", None)
        action = "Edit" if obj and obj.pk else "Create"
        return f"{action} {self.model._meta.verbose_name.title()}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = self.get_cancel_url()
        context["form_title"] = self.get_form_title()
        return context


class SearchablePaginatedListMixin:
    """Apply URL-driven search and page-size state to queryset-backed lists."""

    default_paginate_by = 25
    page_size_options = (25, 50, 100)
    search_param = "q"
    page_size_param = "per_page"
    search_fields: tuple[str, ...] = ()
    search_placeholder = "Search"

    def get_search_query(self) -> str:
        return self.request.GET.get(self.search_param, "").strip()

    def get_per_page(self) -> int:
        try:
            per_page = int(self.request.GET.get(self.page_size_param, ""))
        except TypeError, ValueError:
            return self.default_paginate_by
        return per_page if per_page > 0 else self.default_paginate_by

    def get_paginate_by(self, queryset):
        return self.get_per_page()

    def apply_search(self, queryset):
        query = self.get_search_query()
        if not query or not self.search_fields:
            return queryset
        predicate = Q()
        for field_name in self.search_fields:
            predicate |= Q(**{f"{field_name}__icontains": query})
        return queryset.filter(predicate)

    def build_query_items(self, *, exclude: set[str]) -> list[tuple[str, str]]:
        """Preserve non-target query params across search/pagination form posts."""
        items: list[tuple[str, str]] = []
        for key in self.request.GET:
            if key in exclude:
                continue
            for value in self.request.GET.getlist(key):
                items.append((key, value))
        return items

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_size_options = list(self.page_size_options)
        current_per_page = self.get_per_page()
        if current_per_page not in page_size_options:
            page_size_options.append(current_per_page)
            page_size_options.sort()
        context["search_query"] = self.get_search_query()
        context["search_param"] = self.search_param
        context["search_placeholder"] = self.search_placeholder
        context["search_result_count"] = (
            context["paginator"].count if context.get("paginator") is not None else 0
        )
        context["per_page"] = current_per_page
        context["page_size_param"] = self.page_size_param
        context["page_size_options"] = page_size_options
        context["search_preserved_query_items"] = self.build_query_items(
            exclude={self.search_param, "page"}
        )
        context["per_page_preserved_query_items"] = self.build_query_items(
            exclude={self.page_size_param, "page"}
        )
        page_obj = context.get("page_obj")
        if page_obj is not None:
            context["page_range"] = page_obj.paginator.get_elided_page_range(
                number=page_obj.number
            )
        return context


class FilterPreferenceMixin:
    """Persist URL-backed filter state as the user's default for a list page."""

    filterset_class: type[AccessAtlasFilterSet] | None = None
    filter_preference_page_key = ""

    def get_filter_parameter_names(self) -> set[str]:
        if self.filterset_class is None:
            return set()
        return self.filterset_class.filter_parameter_names() - {"q"}

    def get_filter_preference_key(self) -> str:
        return list_filter_preference_key(self.filter_preference_page_key)

    def filter_preferences_enabled(self) -> bool:
        return bool(
            self.filter_preference_page_key and self.request.user.is_authenticated
        )

    def filter_query_params(self, query) -> dict[str, list[str]]:
        params: dict[str, list[str]] = {}
        for parameter_name in self.get_filter_parameter_names():
            values = [
                str(value).strip()
                for value in query.getlist(parameter_name)
                if str(value).strip()
            ]
            if values:
                params[parameter_name] = values
        return params

    def request_has_filter_state(self, query) -> bool:
        return any(
            parameter_name in query
            for parameter_name in self.get_filter_parameter_names()
        )

    def saved_filter_params(self) -> dict[str, list[str]]:
        preference = get_user_preference(
            self.request.user,
            self.get_filter_preference_key(),
        )
        params = preference.get("params")
        if not isinstance(params, dict):
            return {}
        allowed_parameters = self.get_filter_parameter_names()
        return {
            key: [str(value) for value in values]
            for key, values in params.items()
            if key in allowed_parameters and isinstance(values, list)
        }

    def filter_state_redirect(self, query) -> HttpResponseRedirect:
        query.pop(FILTER_STATE_PARAM, None)
        query.pop("page", None)
        return HttpResponseRedirect(querydict_url(self.request, query))

    def dispatch(self, request, *args, **kwargs):
        if not self.filter_preferences_enabled():
            return super().dispatch(request, *args, **kwargs)

        query = request.GET.copy()
        marker = query.get(FILTER_STATE_PARAM)
        current_params = self.filter_query_params(query)
        has_filter_state = self.request_has_filter_state(query)

        if marker == FILTER_STATE_UPDATE:
            set_user_preference(
                request.user,
                self.get_filter_preference_key(),
                {"params": current_params},
            )
            return self.filter_state_redirect(query)

        if has_filter_state:
            set_user_preference(
                request.user,
                self.get_filter_preference_key(),
                {"params": current_params},
            )
            return super().dispatch(request, *args, **kwargs)

        saved_params = self.saved_filter_params()
        if saved_params:
            query.pop("page", None)
            for parameter_name, values in saved_params.items():
                query.setlist(parameter_name, values)
            return HttpResponseRedirect(querydict_url(request, query))

        return super().dispatch(request, *args, **kwargs)


class FilteredListMixin(FilterPreferenceMixin):
    """Apply a shared django-filter FilterSet and expose filter UI context."""

    def get_filter_data(self):
        return self.request.GET.copy()

    def get_filterset(self, queryset):
        if self.filterset_class is None:
            msg = "FilteredListMixin requires filterset_class."
            raise AttributeError(msg)
        return self.filterset_class(
            data=self.get_filter_data(),
            queryset=queryset,
            request=self.request,
        )

    def apply_filters(self, queryset):
        self._filterset = self.get_filterset(queryset)
        return self._filterset.qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filterset = getattr(self, "_filterset", None)
        if filterset is None:
            object_list = context.get("object_list")
            if object_list is None:
                object_list = self.model.objects.none()
            filterset = self.get_filterset(object_list)
            self._filterset = filterset

        filter_parameter_names = filterset.filter_parameter_names()
        controls = filterset.filter_controls()
        chips = filterset.active_chips(self.request)
        context["filterset"] = filterset
        context["filter_controls"] = controls
        context["active_filter_chips"] = chips
        context["filter_clear_all_url"] = filterset.clear_all_url(self.request)
        context["filter_state_param"] = FILTER_STATE_PARAM
        context["filter_state_update"] = FILTER_STATE_UPDATE
        context["list_filter_preference_key"] = (
            self.get_filter_preference_key() if self.filter_preference_page_key else ""
        )
        context["filter_preserved_query_items"] = preserved_query_items(
            self.request,
            exclude=(filter_parameter_names - {"q"}) | {"page", FILTER_STATE_PARAM},
        )
        context["search_preserved_query_items"] = preserved_query_items(
            self.request,
            exclude={"q", "page", FILTER_STATE_PARAM},
        )
        context["list_view_query_string"] = query_string_without_page(self.request)
        context.setdefault("search_query", self.request.GET.get("q", "").strip())
        context.setdefault("search_param", "q")
        context.setdefault("search_placeholder", "Search")
        if context.get("paginator") is not None:
            context.setdefault("search_result_count", context["paginator"].count)
        else:
            object_list = context.get("object_list", [])
            try:
                result_count = object_list.count()
            except TypeError:
                result_count = len(object_list)
            context.setdefault("search_result_count", result_count)
        return context


class SortableListMixin:
    """Apply single-column sorting with URL state and saved user fallback."""

    sort_param = "sort"
    default_sort = ""
    sort_preference_page_key = ""
    sort_field_map: dict[str, str] = {}

    def normalize_sort_value(self, value: str | None) -> str | None:
        if not value:
            return None
        direction = "-" if value.startswith("-") else ""
        sort_key = value.removeprefix("-")
        if sort_key not in self.sort_field_map:
            return None
        return f"{direction}{sort_key}"

    def get_sort_preference_key(self) -> str:
        return list_sort_preference_key(self.sort_preference_page_key)

    def get_saved_sort_value(self) -> str | None:
        preference = get_user_preference(
            self.request.user,
            self.get_sort_preference_key(),
        )
        return self.normalize_sort_value(preference.get("value"))

    def get_sort_value(self) -> str:
        if hasattr(self, "_cached_sort_value"):
            return self._cached_sort_value

        # Explicit URL state always wins so links remain shareable and
        # debuggable. When a user intentionally sorts a page, we also persist
        # that choice as the next default for visits without a sort param.
        explicit_sort = self.normalize_sort_value(self.request.GET.get(self.sort_param))
        if explicit_sort is not None:
            if self.request.user.is_authenticated:
                saved_sort = self.get_saved_sort_value()
                if saved_sort != explicit_sort:
                    set_user_preference(
                        self.request.user,
                        self.get_sort_preference_key(),
                        {"value": explicit_sort},
                    )
            self._cached_sort_value = explicit_sort
            return explicit_sort

        saved_sort = self.get_saved_sort_value()
        self._cached_sort_value = saved_sort or self.default_sort
        return self._cached_sort_value

    def apply_sort(self, queryset):
        sort_value = self.get_sort_value()
        descending = sort_value.startswith("-")
        sort_key = sort_value.removeprefix("-")
        sort_field = self.sort_field_map.get(sort_key)
        if not sort_field:
            return queryset
        prefix = "-" if descending else ""
        return queryset.order_by(f"{prefix}{sort_field}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort_value = self.get_sort_value()
        context["current_sort"] = sort_value
        context["current_sort_field"] = sort_value.removeprefix("-")
        context["current_sort_descending"] = sort_value.startswith("-")
        context["sort_param"] = self.sort_param
        return context


class PaginatedObjectHistoryMixin:
    """Paginate object history pages with the same per-page contract as lists."""

    default_paginate_by = 25
    page_size_options = (25, 50, 100)
    page_size_param = "per_page"

    def get_history_per_page(self) -> int:
        try:
            per_page = int(self.request.GET.get(self.page_size_param, ""))
        except TypeError, ValueError:
            return self.default_paginate_by
        return per_page if per_page > 0 else self.default_paginate_by

    def get_history_queryset(self):
        return self.object.history.all()

    def get_history_detail_url(self, record) -> str:
        return append_query_string(
            history_detail_url(record),
            history_object_filter_query(record.instance),
        )

    def get_history_context(self) -> dict:
        # History pages are DetailViews, not ListViews, so pagination state is
        # assembled manually here and then reused by the shared history partial.
        per_page = self.get_history_per_page()
        page_size_options = list(self.page_size_options)
        if per_page not in page_size_options:
            page_size_options.append(per_page)
            page_size_options.sort()

        paginator = Paginator(self.get_history_queryset(), per_page)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        for record in page_obj.object_list:
            record.history_detail_url = self.get_history_detail_url(record)
        preserved_query_items: list[tuple[str, str]] = []
        for key in self.request.GET:
            if key in {self.page_size_param, "page"}:
                continue
            for value in self.request.GET.getlist(key):
                preserved_query_items.append((key, value))

        return {
            "history_records": page_obj.object_list,
            "history_object_type": self.object._meta.verbose_name.title(),
            "object_global_history_url": append_query_string(
                reverse("global_history"),
                history_object_filter_query(self.object),
            ),
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
            "paginator": paginator,
            "page_range": paginator.get_elided_page_range(number=page_obj.number),
            "per_page": per_page,
            "page_size_param": self.page_size_param,
            "page_size_options": page_size_options,
            "per_page_preserved_query_items": preserved_query_items,
        }


class ObjectHistoryDetailMixin:
    """Render a single simple-history record with previous/current diff data."""

    template_name = "object_history_detail.html"

    def get_history_record(self):
        if hasattr(self, "_history_record"):
            return self._history_record
        self._history_record = get_object_or_404(
            self.get_history_queryset(),
            history_id=self.kwargs["history_id"],
        )
        return self._history_record

    def get_adjacent_history_records(self, history_record):
        records = list(
            self.get_history_queryset().order_by("history_date", "history_id")
        )
        record_ids = [record.history_id for record in records]
        index = record_ids.index(history_record.history_id)
        previous_record = records[index - 1] if index > 0 else None
        next_record = records[index + 1] if index < len(records) - 1 else None
        return previous_record, next_record

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        history_record = self.get_history_record()
        previous_record, next_record = self.get_adjacent_history_records(history_record)
        context.update(
            {
                "history_record": history_record,
                "history_diff": build_history_diff(history_record, previous_record),
                "previous_history_url": self.get_history_detail_url(previous_record)
                if previous_record
                else "",
                "next_history_url": self.get_history_detail_url(next_record)
                if next_record
                else "",
                "object_history_url": self.object.get_history_url(),
            }
        )
        return context
