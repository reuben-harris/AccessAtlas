from __future__ import annotations

from django import forms
from django.db import transaction

from .models import TripStatus
from .services import invalidate_trip_approval

APPROVAL_RESET_MESSAGE = (
    "Making changes to this approved trip will send it back to waiting for approval."
)
APPROVAL_CONFIRM_FIELD = "confirm_trip_approval_reset"


class ApprovedTripChangeMixin:
    approval_reset_reason = "Returned trip to submitted after changes"

    def get_approval_trip(self):
        return None

    def trip_requires_approval_reset(self) -> bool:
        trip = self.get_approval_trip()
        return trip is not None and trip.status == TripStatus.APPROVED

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.trip_requires_approval_reset():
            form.fields[APPROVAL_CONFIRM_FIELD] = forms.BooleanField(
                label="I understand this change will send the trip back for approval.",
                required=True,
            )
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.trip_requires_approval_reset():
            context["form_notice"] = APPROVAL_RESET_MESSAGE
        return context

    def form_valid(self, form):
        trip = self.get_approval_trip()
        with transaction.atomic():
            response = super().form_valid(form)
            if trip is not None and trip.status == TripStatus.APPROVED:
                invalidate_trip_approval(
                    trip,
                    self.request.user,
                    self.approval_reset_reason,
                )
        return response
