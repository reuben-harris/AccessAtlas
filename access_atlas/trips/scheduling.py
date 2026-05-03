from django.utils import timezone


def planned_date(value):
    if timezone.is_aware(value):
        return timezone.localtime(value).date()
    return value.date()


def infer_planned_day(planned_day, planned_start, planned_end):
    if planned_day:
        return planned_day
    if planned_start:
        return planned_date(planned_start)
    if planned_end:
        return planned_date(planned_end)
    return None


def validate_site_visit_schedule(
    *,
    trip,
    planned_day,
    planned_start,
    planned_end,
    message_overrides: dict[str, str] | None = None,
) -> tuple[object, dict[str, str]]:
    # Centralize the scheduling policy so the model and the form stay aligned.
    # The model uses the default wording, while the form can override messages
    # to keep browser-facing field errors phrased in UI language.
    errors: dict[str, str] = {}
    message_overrides = message_overrides or {}
    normalized_day = infer_planned_day(planned_day, planned_start, planned_end)

    if not normalized_day:
        errors["planned_day"] = message_overrides.get(
            "planned_day_required",
            "Choose a trip day.",
        )
    if planned_end and not planned_start:
        errors["planned_start"] = message_overrides.get(
            "planned_start_required_for_end",
            "A planned end requires a planned start.",
        )
    if planned_start and planned_end and planned_end <= planned_start:
        errors["planned_end"] = message_overrides.get(
            "planned_end_after_start",
            "Planned end must be after planned start.",
        )
    if errors or trip is None:
        return normalized_day, errors

    trip_start = trip.start_date
    trip_end = trip.end_date
    trip_date_message = f"Must be between {trip_start} and {trip_end}."
    if normalized_day < trip_start or normalized_day > trip_end:
        errors["planned_day"] = trip_date_message
    if planned_start:
        planned_start_date = planned_date(planned_start)
        if planned_start_date != normalized_day:
            errors["planned_start"] = "Start time must be on the selected trip day."
        elif planned_start_date < trip_start or planned_start_date > trip_end:
            errors["planned_start"] = trip_date_message
    if planned_end:
        planned_end_date = planned_date(planned_end)
        if planned_end_date != normalized_day:
            errors["planned_end"] = "End time must be on the selected trip day."
        elif planned_end_date < trip_start or planned_end_date > trip_end:
            errors["planned_end"] = trip_date_message
    return normalized_day, errors
