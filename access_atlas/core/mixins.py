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
