from django.db.models import Q
from django.urls import reverse


class ObjectFormMixin:
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
