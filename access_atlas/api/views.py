from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from simple_history.utils import update_change_reason

from access_atlas.jobs.models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)
from access_atlas.jobs.services import (
    assign_jobs_to_work_programme,
    create_job_from_template,
)
from access_atlas.sites.feed import SiteFeedError, sync_configured_site_feed
from access_atlas.sites.forms import SitePhotoUploadForm
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordVersion,
    Site,
    SitePhoto,
)
from access_atlas.sites.photo_services import (
    calculate_image_sha256,
    create_site_photo,
    hide_site_photo,
    site_photo_hashes,
)
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip, TripStatus
from access_atlas.trips.services import (
    JOB_OUTCOME_CANCELLED,
    JOB_OUTCOME_COMPLETED,
    approve_trip,
    assign_job_to_site_visit,
    assign_jobs_to_site_visit,
    cancel_trip,
    close_trip,
    get_trip_assignments,
    invalidate_trip_approval,
    return_trip_to_draft,
    submit_trip_for_approval,
    unassign_site_visit_job,
)

from .serializers import (
    AccessRecordSerializer,
    AccessRecordVersionSerializer,
    EmptySerializer,
    JobAssignmentSerializer,
    JobFromTemplateSerializer,
    JobSerializer,
    JobTemplateSerializer,
    RequirementSerializer,
    SitePhotoSerializer,
    SiteSerializer,
    SiteVisitJobSerializer,
    SiteVisitSerializer,
    TemplateRequirementSerializer,
    TripCloseoutSerializer,
    TripSerializer,
    WorkProgrammeSerializer,
    django_validation_to_drf,
)

APPROVAL_CONFIRMATION_ERROR = (
    "Set confirm_approval_reset to true to send this approved trip back for approval."
)


class NoDeleteModelViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    def perform_create(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Created via API")

    def perform_update(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Updated via API")


class ListRetrieveCreateViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    def perform_create(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Created via API")


def raise_drf_validation(error: DjangoValidationError) -> None:
    raise ValidationError(django_validation_to_drf(error)) from error


def require_approval_confirmation(trip: Trip | None, confirmed: bool) -> None:
    if trip is not None and trip.status == TripStatus.APPROVED and not confirmed:
        raise ValidationError({"confirm_approval_reset": APPROVAL_CONFIRMATION_ERROR})


def approved_trip_for_job(job: Job) -> Trip | None:
    assignment = getattr(job, "site_visit_assignment", None)
    if assignment is None:
        return None
    trip = assignment.site_visit.trip
    return trip if trip.status == TripStatus.APPROVED else None


class SiteViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["source_name", "external_id", "code", "sync_status"]
    search_fields = ["code", "name", "description", "source_name", "external_id"]
    ordering_fields = ["code", "name", "source_name", "sync_status", "last_seen_at"]
    ordering = ["code"]

    @action(detail=False, methods=["post"], serializer_class=EmptySerializer)
    def sync(self, request):
        try:
            result = sync_configured_site_feed()
        except SiteFeedError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(
            {
                "created": result.created,
                "updated": result.updated,
                "rejected": result.rejected,
            }
        )


class JobTemplateViewSet(NoDeleteModelViewSet):
    queryset = JobTemplate.objects.all()
    serializer_class = JobTemplateSerializer
    filterset_fields = ["priority", "is_active"]
    search_fields = ["title", "description"]
    ordering_fields = ["title", "priority", "is_active", "created_at", "updated_at"]
    ordering = ["title"]


class TemplateRequirementViewSet(NoDeleteModelViewSet):
    queryset = TemplateRequirement.objects.select_related("job_template")
    serializer_class = TemplateRequirementSerializer
    filterset_fields = ["job_template", "requirement_type", "is_required"]
    search_fields = ["name", "quantity", "notes", "job_template__title"]
    ordering_fields = ["name", "requirement_type", "job_template"]
    ordering = ["name"]


class WorkProgrammeViewSet(NoDeleteModelViewSet):
    queryset = WorkProgramme.objects.all()
    serializer_class = WorkProgrammeSerializer
    search_fields = ["name", "description"]
    ordering_fields = ["name", "start_date", "end_date", "created_at", "updated_at"]
    ordering = ["start_date", "name"]

    @action(
        detail=True,
        methods=["post"],
        serializer_class=JobAssignmentSerializer,
        url_path="assign-jobs",
    )
    def assign_jobs(self, request, pk=None):
        work_programme = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            count = assign_jobs_to_work_programme(
                serializer.validated_data["jobs"],
                work_programme,
            )
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        return Response({"assigned": count})


class JobViewSet(NoDeleteModelViewSet):
    queryset = Job.objects.select_related("site", "template", "work_programme")
    serializer_class = JobSerializer
    filterset_fields = ["site", "template", "work_programme", "priority", "status"]
    search_fields = [
        "title",
        "description",
        "closeout_note",
        "site__code",
        "site__name",
        "work_programme__name",
    ]
    ordering_fields = [
        "site",
        "title",
        "priority",
        "status",
        "created_at",
        "updated_at",
    ]
    ordering = ["site__code", "title"]

    def perform_update(self, serializer):
        trip = approved_trip_for_job(serializer.instance)
        confirmed = serializer.validated_data.get("confirm_approval_reset", False)
        require_approval_confirmation(trip, confirmed)
        with transaction.atomic():
            instance = serializer.save()
            update_change_reason(instance, "Updated via API")
            if trip is not None:
                invalidate_trip_approval(
                    trip,
                    self.request.user,
                    "Returned to submitted after job API update",
                )

    @action(
        detail=False,
        methods=["post"],
        serializer_class=JobFromTemplateSerializer,
        url_path="from-template",
    )
    def from_template(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = create_job_from_template(
            site=serializer.validated_data["site"],
            template=serializer.validated_data["template"],
            work_programme=serializer.validated_data.get("work_programme"),
            change_reason="Created job from template via API",
        )
        return Response(
            JobSerializer(job, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class RequirementViewSet(NoDeleteModelViewSet):
    queryset = Requirement.objects.select_related("job", "job__site")
    serializer_class = RequirementSerializer
    filterset_fields = ["job", "requirement_type", "is_required", "is_checked"]
    search_fields = ["name", "quantity", "notes", "job__title", "job__site__code"]
    ordering_fields = ["name", "requirement_type", "is_required", "is_checked"]
    ordering = ["name"]


class TripViewSet(NoDeleteModelViewSet):
    queryset = Trip.objects.select_related(
        "trip_leader",
        "submitted_by",
    ).prefetch_related("team_members")
    serializer_class = TripSerializer
    filterset_fields = ["trip_leader", "status", "start_date", "end_date"]
    search_fields = ["name", "notes", "trip_leader__email", "trip_leader__display_name"]
    ordering_fields = ["name", "start_date", "end_date", "status", "created_at"]
    ordering = ["-start_date", "name"]

    def perform_create(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Created trip via API")

    def perform_update(self, serializer):
        trip = serializer.instance
        confirmed = serializer.validated_data.get("confirm_approval_reset", False)
        require_approval_confirmation(trip, confirmed)
        with transaction.atomic():
            instance = serializer.save()
            update_change_reason(instance, "Updated trip via API")
            invalidate_trip_approval(
                trip,
                self.request.user,
                "Returned to submitted after trip API update",
            )

    @action(detail=True, methods=["post"], serializer_class=EmptySerializer)
    def submit(self, request, pk=None):
        trip = self.get_object()
        try:
            submit_trip_for_approval(trip, request.user)
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        return Response(
            TripSerializer(trip, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], serializer_class=EmptySerializer)
    def approve(self, request, pk=None):
        trip = self.get_object()
        try:
            approve_trip(trip, request.user)
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        trip.refresh_from_db()
        return Response(
            TripSerializer(trip, context=self.get_serializer_context()).data
        )

    @action(
        detail=True,
        methods=["post"],
        serializer_class=EmptySerializer,
        url_path="return-to-draft",
    )
    def return_to_draft(self, request, pk=None):
        trip = self.get_object()
        try:
            return_trip_to_draft(trip)
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        trip.refresh_from_db()
        return Response(
            TripSerializer(trip, context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"], serializer_class=EmptySerializer)
    def cancel(self, request, pk=None):
        trip = self.get_object()
        try:
            summary = cancel_trip(trip)
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        trip.refresh_from_db()
        return Response(
            {
                "trip": TripSerializer(
                    trip,
                    context=self.get_serializer_context(),
                ).data,
                "site_visits_to_skip": summary.site_visits_to_skip,
                "jobs_to_return": summary.jobs_to_return,
            }
        )

    @action(detail=True, methods=["post"], serializer_class=TripCloseoutSerializer)
    def close(self, request, pk=None):
        trip = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cleaned_data = self._closeout_cleaned_data(trip, serializer.validated_data)
        try:
            close_trip(trip, cleaned_data)
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        trip.refresh_from_db()
        return Response(
            TripSerializer(trip, context=self.get_serializer_context()).data
        )

    def _closeout_cleaned_data(self, trip: Trip, payload: dict) -> dict:
        site_visits = {
            site_visit.pk: site_visit for site_visit in trip.site_visits.all()
        }
        submitted_site_visits = {
            item["id"]: item["status"] for item in payload["site_visits"]
        }
        if set(submitted_site_visits) != set(site_visits):
            raise ValidationError(
                {"site_visits": "Submit one closeout status for every site visit."}
            )

        assignments = {
            assignment.pk: assignment
            for assignment in get_trip_assignments(trip).filter(
                job__status__in=[JobStatus.ASSIGNED, JobStatus.UNASSIGNED]
            )
        }
        submitted_jobs = {item["assignment_id"]: item for item in payload["jobs"]}
        if set(submitted_jobs) != set(assignments):
            raise ValidationError(
                {"jobs": "Submit one closeout outcome for every open job assignment."}
            )

        cleaned_data = {
            f"site_visit_{site_visit_id}": visit_status
            for site_visit_id, visit_status in submitted_site_visits.items()
        }
        allowed_outcomes = {
            JOB_OUTCOME_COMPLETED,
            "return",
            JOB_OUTCOME_CANCELLED,
        }
        for assignment_id, item in submitted_jobs.items():
            outcome = item["outcome"]
            closeout_note = item.get("closeout_note", "").strip()
            if outcome not in allowed_outcomes:
                raise ValidationError(
                    {"jobs": f"{outcome!r} is not a valid closeout outcome."}
                )
            if outcome in {JOB_OUTCOME_COMPLETED, JOB_OUTCOME_CANCELLED}:
                if not closeout_note:
                    raise ValidationError(
                        {"jobs": "Completed or cancelled jobs require a closeout note."}
                    )
            cleaned_data[f"job_{assignment_id}_outcome"] = outcome
            cleaned_data[f"job_{assignment_id}_closeout_note"] = closeout_note
        return cleaned_data


class SiteVisitViewSet(NoDeleteModelViewSet):
    queryset = SiteVisit.objects.select_related("trip", "site")
    serializer_class = SiteVisitSerializer
    filterset_fields = ["trip", "site", "status", "planned_day"]
    search_fields = ["notes", "site__code", "site__name", "trip__name"]
    ordering_fields = ["trip", "site", "planned_day", "planned_start", "status"]
    ordering = ["trip", "planned_day", "planned_start", "site__code", "id"]

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        if trip.is_terminal:
            raise ValidationError(
                {
                    "trip": (
                        "Site visits cannot be added to completed or cancelled trips."
                    )
                }
            )
        confirmed = serializer.validated_data.get("confirm_approval_reset", False)
        require_approval_confirmation(trip, confirmed)
        with transaction.atomic():
            instance = serializer.save()
            update_change_reason(instance, "Created site visit via API")
            invalidate_trip_approval(
                trip,
                self.request.user,
                "Returned to submitted after site visit API creation",
            )

    def perform_update(self, serializer):
        trip = serializer.instance.trip
        confirmed = serializer.validated_data.get("confirm_approval_reset", False)
        require_approval_confirmation(trip, confirmed)
        with transaction.atomic():
            instance = serializer.save()
            update_change_reason(instance, "Updated site visit via API")
            invalidate_trip_approval(
                trip,
                self.request.user,
                "Returned to submitted after site visit API update",
            )

    @action(
        detail=True,
        methods=["post"],
        serializer_class=JobAssignmentSerializer,
        url_path="assign-jobs",
    )
    def assign_jobs(self, request, pk=None):
        site_visit = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_approval_confirmation(
            site_visit.trip,
            serializer.validated_data.get("confirm_approval_reset", False),
        )
        try:
            count = assign_jobs_to_site_visit(
                site_visit,
                serializer.validated_data["jobs"],
                request.user,
            )
        except DjangoValidationError as exc:
            raise_drf_validation(exc)
        return Response({"assigned": count})


class SiteVisitJobViewSet(ListRetrieveCreateViewSet):
    queryset = SiteVisitJob.objects.select_related(
        "site_visit",
        "site_visit__trip",
        "job",
    )
    serializer_class = SiteVisitJobSerializer
    filterset_fields = ["site_visit", "job", "site_visit__trip"]
    search_fields = ["job__title", "site_visit__site__code", "site_visit__trip__name"]
    ordering_fields = ["assigned_at", "site_visit", "job"]
    ordering = ["assigned_at"]

    def perform_create(self, serializer):
        site_visit = serializer.validated_data["site_visit"]
        confirmed = serializer.validated_data.get("confirm_approval_reset", False)
        require_approval_confirmation(site_visit.trip, confirmed)
        try:
            if site_visit.trip.status == TripStatus.APPROVED:
                assign_jobs_to_site_visit(
                    site_visit,
                    [serializer.validated_data["job"]],
                    self.request.user,
                )
                assignment = SiteVisitJob.objects.get(
                    site_visit=site_visit,
                    job=serializer.validated_data["job"],
                )
            else:
                assignment = assign_job_to_site_visit(
                    site_visit,
                    serializer.validated_data["job"],
                )
            serializer.instance = assignment
            update_change_reason(assignment, "Assigned job to site visit via API")
        except DjangoValidationError as exc:
            raise_drf_validation(exc)

    @action(
        detail=True,
        methods=["post"],
        serializer_class=EmptySerializer,
        url_path="unassign",
    )
    def unassign(self, request, pk=None):
        assignment = self.get_object()
        site_visit = assignment.site_visit
        require_approval_confirmation(
            site_visit.trip,
            request.data.get("confirm_approval_reset") is True
            or str(request.data.get("confirm_approval_reset")).lower() in {"1", "true"},
        )
        with transaction.atomic():
            unassign_site_visit_job(assignment)
            invalidate_trip_approval(
                site_visit.trip,
                request.user,
                "Returned to submitted after job assignment API change",
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccessRecordViewSet(NoDeleteModelViewSet):
    queryset = AccessRecord.objects.select_related("site")
    serializer_class = AccessRecordSerializer
    filterset_fields = ["site", "arrival_method", "status"]
    search_fields = ["name", "site__code", "site__name"]
    ordering_fields = ["site", "name", "arrival_method", "status", "created_at"]
    ordering = ["site__code", "name"]

    def perform_create(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Created access record via API")
        current_version = instance.current_version
        if current_version is not None:
            update_change_reason(
                current_version,
                "Created access record revision via API",
            )


class AccessRecordVersionViewSet(ListRetrieveCreateViewSet):
    queryset = AccessRecordVersion.objects.select_related(
        "access_record",
        "uploaded_by",
    )
    serializer_class = AccessRecordVersionSerializer
    filterset_fields = ["access_record", "uploaded_by"]
    search_fields = ["change_note", "access_record__name", "access_record__site__code"]
    ordering_fields = ["access_record", "version_number", "created_at"]
    ordering = ["access_record", "-version_number"]

    def perform_create(self, serializer):
        instance = serializer.save()
        update_change_reason(instance, "Created access record revision via API")


class SitePhotoViewSet(ListRetrieveCreateViewSet):
    queryset = SitePhoto.objects.select_related("site", "uploaded_by", "hidden_by")
    serializer_class = SitePhotoSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    filterset_fields = ["site", "uploaded_by", "hidden", "taken_date"]
    search_fields = ["site__code", "site__name", "image"]
    ordering_fields = ["site", "taken_date", "uploaded_at", "hidden"]
    ordering = ["-taken_date", "-uploaded_at", "-id"]

    def create(self, request, *args, **kwargs):
        site = get_object_or_404(Site, pk=request.data.get("site"))
        form = SitePhotoUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            raise ValidationError(form.errors)

        existing_hashes = site_photo_hashes(site)
        upload_hashes = set()
        created_photos = []
        skipped_count = 0
        for photo_file in form.cleaned_data["photos"]:
            image_sha256 = calculate_image_sha256(photo_file)
            if image_sha256 in existing_hashes or image_sha256 in upload_hashes:
                skipped_count += 1
                continue
            created_photos.append(
                create_site_photo(
                    site=site,
                    user=request.user,
                    image_file=photo_file,
                    image_sha256=image_sha256,
                )
            )
            upload_hashes.add(image_sha256)

        response_status = (
            status.HTTP_201_CREATED if created_photos else status.HTTP_200_OK
        )
        return Response(
            {
                "created": SitePhotoSerializer(
                    created_photos,
                    many=True,
                    context=self.get_serializer_context(),
                ).data,
                "skipped_duplicates": skipped_count,
            },
            status=response_status,
        )

    @action(detail=True, methods=["post"], serializer_class=EmptySerializer)
    def hide(self, request, pk=None):
        photo = self.get_object()
        hide_site_photo(photo=photo, user=request.user)
        return Response(
            SitePhotoSerializer(photo, context=self.get_serializer_context()).data
        )
