from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from access_atlas.jobs.models import (
    Job,
    JobTemplate,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)
from access_atlas.sites.access_record_services import (
    create_access_record_from_upload,
    create_access_record_version_from_upload,
)
from access_atlas.sites.access_records import (
    AccessRecordGeoJSONError,
    parse_access_record_geojson,
)
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordVersion,
    Site,
    SitePhoto,
)
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip

User = get_user_model()


def django_validation_to_drf(error: DjangoValidationError):
    if hasattr(error, "message_dict"):
        return {
            field: [str(message) for message in messages]
            for field, messages in error.message_dict.items()
        }
    return [str(message) for message in error.messages]


class FullCleanModelSerializer(serializers.ModelSerializer):
    """Run model-level validation that DRF serializers do not call by default."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        model = self.Meta.model
        instance = self.instance or model()
        concrete_fields = {field.name for field in model._meta.fields}
        for field_name, value in attrs.items():
            if field_name in concrete_fields:
                setattr(instance, field_name, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(django_validation_to_drf(exc)) from exc
        return attrs


@extend_schema_field(OpenApiTypes.STR)
class DisplayField(serializers.Field):
    def get_attribute(self, instance):
        return instance

    def to_representation(self, value):
        return str(value)


class ConfirmationMixin(serializers.Serializer):
    confirm_approval_reset = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    def create(self, validated_data):
        validated_data.pop("confirm_approval_reset", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("confirm_approval_reset", None)
        return super().update(instance, validated_data)


class UserBriefSerializer(serializers.ModelSerializer):
    display = DisplayField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "display"]


class SiteSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="site-api-detail")
    display = DisplayField(read_only=True)

    class Meta:
        model = Site
        fields = [
            "id",
            "url",
            "display",
            "source_name",
            "external_id",
            "code",
            "name",
            "description",
            "tags",
            "latitude",
            "longitude",
            "sync_status",
            "last_seen_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class JobTemplateSerializer(FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="job-template-api-detail")
    display = DisplayField(read_only=True)

    class Meta:
        model = JobTemplate
        fields = [
            "id",
            "url",
            "display",
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "url", "display", "created_at", "updated_at"]


class TemplateRequirementSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="template-requirement-api-detail"
    )
    display = DisplayField(read_only=True)

    class Meta:
        model = TemplateRequirement
        fields = [
            "id",
            "url",
            "display",
            "job_template",
            "requirement_type",
            "name",
            "quantity",
            "notes",
            "is_required",
        ]
        read_only_fields = ["id", "url", "display"]


class WorkProgrammeSerializer(FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="work-programme-api-detail")
    display = DisplayField(read_only=True)
    date_range_label = serializers.CharField(read_only=True)

    class Meta:
        model = WorkProgramme
        fields = [
            "id",
            "url",
            "display",
            "name",
            "start_date",
            "end_date",
            "date_range_label",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "url",
            "display",
            "date_range_label",
            "created_at",
            "updated_at",
        ]


class JobSerializer(ConfirmationMixin, FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="job-api-detail")
    display = DisplayField(read_only=True)
    due_date = serializers.DateField(read_only=True)
    is_assigned = serializers.BooleanField(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "url",
            "display",
            "site",
            "template",
            "work_programme",
            "title",
            "description",
            "estimated_duration_minutes",
            "priority",
            "status",
            "closeout_note",
            "due_date",
            "is_assigned",
            "confirm_approval_reset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "url",
            "display",
            "due_date",
            "is_assigned",
            "created_at",
            "updated_at",
        ]


class RequirementSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="requirement-api-detail")
    display = DisplayField(read_only=True)

    class Meta:
        model = Requirement
        fields = [
            "id",
            "url",
            "display",
            "job",
            "requirement_type",
            "name",
            "quantity",
            "notes",
            "is_required",
            "is_checked",
        ]
        read_only_fields = ["id", "url", "display"]


class TripSerializer(ConfirmationMixin, FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="trip-api-detail")
    display = DisplayField(read_only=True)
    submitted_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "url",
            "display",
            "name",
            "start_date",
            "end_date",
            "trip_leader",
            "team_members",
            "submitted_by",
            "submitted_at",
            "approved_at",
            "approval_round",
            "status",
            "notes",
            "confirm_approval_reset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "url",
            "display",
            "submitted_by",
            "submitted_at",
            "approved_at",
            "approval_round",
            "status",
            "created_at",
            "updated_at",
        ]


class SiteVisitSerializer(ConfirmationMixin, FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="site-visit-api-detail")
    display = DisplayField(read_only=True)

    class Meta:
        model = SiteVisit
        fields = [
            "id",
            "url",
            "display",
            "trip",
            "site",
            "planned_day",
            "planned_start",
            "planned_end",
            "status",
            "notes",
            "confirm_approval_reset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "url", "display", "created_at", "updated_at"]


class SiteVisitJobSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="site-visit-job-api-detail")
    display = DisplayField(read_only=True)
    confirm_approval_reset = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    class Meta:
        model = SiteVisitJob
        fields = [
            "id",
            "url",
            "display",
            "site_visit",
            "job",
            "confirm_approval_reset",
            "assigned_at",
        ]
        read_only_fields = ["id", "url", "display", "assigned_at"]

    def create(self, validated_data):
        validated_data.pop("confirm_approval_reset", None)
        return super().create(validated_data)


class AccessRecordSerializer(FullCleanModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="access-record-api-detail")
    display = DisplayField(read_only=True)
    geojson = serializers.JSONField(write_only=True, required=False)
    change_note = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = AccessRecord
        fields = [
            "id",
            "url",
            "display",
            "site",
            "name",
            "arrival_method",
            "status",
            "geojson",
            "change_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "url", "display", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        site = attrs.get("site") or getattr(self.instance, "site", None)
        name = (attrs.get("name") or getattr(self.instance, "name", "")).strip()
        duplicate_records = AccessRecord.objects.filter(site=site, name=name)
        if self.instance:
            duplicate_records = duplicate_records.exclude(pk=self.instance.pk)
        if site and name and duplicate_records.exists():
            raise serializers.ValidationError(
                {
                    "name": (
                        "An access record with this name already exists for this site."
                    )
                }
            )

        if self.instance is None:
            if "geojson" not in attrs:
                raise serializers.ValidationError(
                    {"geojson": "This field is required."}
                )
            if not str(attrs.get("change_note") or "").strip():
                raise serializers.ValidationError(
                    {"change_note": "This field is required."}
                )
        if "geojson" in attrs:
            try:
                parse_access_record_geojson(attrs["geojson"])
            except AccessRecordGeoJSONError as exc:
                raise serializers.ValidationError({"geojson": str(exc)}) from exc
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        geojson = validated_data.pop("geojson")
        change_note = validated_data.pop("change_note")
        return create_access_record_from_upload(
            user=request.user,
            geojson=geojson,
            change_note=change_note.strip(),
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("geojson", None)
        validated_data.pop("change_note", None)
        return super().update(instance, validated_data)


class AccessRecordVersionSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="access-record-version-api-detail"
    )
    display = DisplayField(read_only=True)

    class Meta:
        model = AccessRecordVersion
        fields = [
            "id",
            "url",
            "display",
            "access_record",
            "version_number",
            "geojson",
            "change_note",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "url",
            "display",
            "version_number",
            "uploaded_by",
            "created_at",
        ]

    def validate_geojson(self, value):
        try:
            parse_access_record_geojson(value)
        except AccessRecordGeoJSONError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        request = self.context["request"]
        return create_access_record_version_from_upload(
            user=request.user,
            **validated_data,
        )


class SitePhotoSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="site-photo-api-detail")
    display = DisplayField(read_only=True)

    class Meta:
        model = SitePhoto
        fields = [
            "id",
            "url",
            "display",
            "site",
            "image",
            "thumbnail",
            "image_sha256",
            "image_width",
            "image_height",
            "taken_date",
            "uploaded_by",
            "uploaded_at",
            "hidden",
            "hidden_at",
            "hidden_by",
        ]
        read_only_fields = fields


class JobFromTemplateSerializer(serializers.Serializer):
    site = serializers.PrimaryKeyRelatedField(queryset=Site.objects.all())
    template = serializers.PrimaryKeyRelatedField(
        queryset=JobTemplate.objects.filter(is_active=True)
    )
    work_programme = serializers.PrimaryKeyRelatedField(
        queryset=WorkProgramme.objects.all(),
        required=False,
        allow_null=True,
    )


class JobAssignmentSerializer(serializers.Serializer):
    jobs = serializers.PrimaryKeyRelatedField(
        queryset=Job.objects.all(),
        many=True,
        allow_empty=False,
    )
    confirm_approval_reset = serializers.BooleanField(required=False, default=False)


class TripCloseoutSiteVisitSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=SiteVisit._meta.get_field("status").choices
    )


class TripCloseoutJobSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField()
    outcome = serializers.CharField()
    closeout_note = serializers.CharField(required=False, allow_blank=True)


class TripCloseoutSerializer(serializers.Serializer):
    site_visits = TripCloseoutSiteVisitSerializer(many=True)
    jobs = TripCloseoutJobSerializer(many=True)


class EmptySerializer(serializers.Serializer):
    pass
