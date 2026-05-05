from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from access_atlas.accounts.preferences import (
    get_user_preference,
    list_sort_preference_key,
    set_user_preference,
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
        preserved_query_items: list[tuple[str, str]] = []
        for key in self.request.GET:
            if key in {self.page_size_param, "page"}:
                continue
            for value in self.request.GET.getlist(key):
                preserved_query_items.append((key, value))

        return {
            "history_records": page_obj.object_list,
            "is_paginated": page_obj.has_other_pages(),
            "page_obj": page_obj,
            "paginator": paginator,
            "page_range": paginator.get_elided_page_range(number=page_obj.number),
            "per_page": per_page,
            "page_size_param": self.page_size_param,
            "page_size_options": page_size_options,
            "per_page_preserved_query_items": preserved_query_items,
        }
