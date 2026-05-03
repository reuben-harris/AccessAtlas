from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, FormView, UpdateView

from access_atlas.core.mixins import PaginatedObjectHistoryMixin

from .access_record_snapshots import build_access_record_snapshots
from .access_warnings import build_access_record_warnings
from .forms import (
    AccessRecordForm,
    AccessRecordUploadForm,
    AccessRecordVersionUploadForm,
)
from .models import AccessRecord, Site
from .presentation import (
    POINT_TYPE_BADGE_CLASS,
    POINT_TYPE_DISPLAY,
    TRACK_SUITABILITY_DISPLAY,
    point_details,
)
from .services import (
    create_access_record_from_upload,
    create_access_record_upload_draft,
    create_access_record_version_from_upload,
)
from .view_helpers import (
    access_record_detail_sections,
    build_site_access_map_data,
    map_tile_layer,
)


class AccessRecordCreateView(LoginRequiredMixin, FormView):
    form_class = AccessRecordUploadForm
    template_name = "sites/access_record_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        create_access_record_from_upload(
            site=self.site,
            user=self.request.user,
            name=form.cleaned_data["name"],
            arrival_method=form.cleaned_data["arrival_method"],
            geojson=form.cleaned_data["geojson"],
            change_note=form.cleaned_data["change_note"],
        )
        if form.staged_upload is not None:
            form.staged_upload.delete()
        if form.replaced_staged_upload is not None:
            form.replaced_staged_upload.delete()
        messages.success(self.request, "Access record uploaded.")
        return redirect(self.site.get_access_records_url())

    def form_invalid(self, form):
        self._stage_uploaded_geojson(form)
        return super().form_invalid(form)

    def _stage_uploaded_geojson(self, form):
        if form.staged_upload is not None or "geojson" not in form.cleaned_data:
            return
        form.staged_upload = create_access_record_upload_draft(
            user=self.request.user,
            site=self.site,
            geojson=form.cleaned_data["geojson"],
            file_name=form.cleaned_data["geojson_file_name"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.site
        context["form_title"] = "New access record"
        context["cancel_url"] = self.site.get_access_records_url()
        return context


class AccessRecordDetailView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_detail.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = build_access_record_snapshots([self.object]).get(self.object.pk)
        context["access_warnings"] = build_access_record_warnings(
            self.object,
            snapshot=snapshot,
        )
        context["access_feature_rows"] = []
        context["access_feature_count"] = 0
        context["access_parse_error"] = None
        context["current_version"] = snapshot.current_version if snapshot else None
        if snapshot and snapshot.current_version:
            if snapshot.parse_error:
                context["access_parse_error"] = (
                    "Latest revision could not be parsed for feature summary."
                )
            elif snapshot.parsed is not None:
                feature_rows = []
                for point in snapshot.parsed.points:
                    details = point_details(point) or "-"
                    feature_rows.append(
                        {
                            "type_display": POINT_TYPE_DISPLAY.get(
                                point.feature_type, point.feature_type
                            ),
                            "type_badge_class": POINT_TYPE_BADGE_CLASS.get(
                                point.feature_type, "bg-secondary-lt"
                            ),
                            "label": point.label or "-",
                            "coordinates": (
                                f"{point.latitude:.6f}, {point.longitude:.6f}"
                            ),
                            "details": details,
                        }
                    )
                for track in snapshot.parsed.tracks:
                    details = "-"
                    if track.suitability:
                        suitability_display = TRACK_SUITABILITY_DISPLAY.get(
                            track.suitability, track.suitability
                        )
                        details = f"Suitability: {suitability_display}"
                    feature_rows.append(
                        {
                            "type_display": "Track",
                            "type_badge_class": "bg-red-lt",
                            "label": track.label or "-",
                            "coordinates": f"{len(track.coordinates)} points",
                            "details": details,
                        }
                    )
                context["access_feature_rows"] = feature_rows
                context["access_feature_count"] = len(feature_rows)
        context["detail_sections"] = access_record_detail_sections(
            self.object, "overview"
        )
        context["detail_navigation_label"] = "Access record sections"
        return context


class AccessRecordMapView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_map.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = build_access_record_snapshots([self.object]).get(self.object.pk)
        snapshots_by_record_id = {self.object.pk: snapshot} if snapshot else {}
        context["access_warnings"] = build_access_record_warnings(
            self.object,
            snapshot=snapshot,
        )
        context["site_access_map_data"] = build_site_access_map_data(
            [self.object],
            snapshots_by_record_id,
        )
        context["site_access_map_preference"] = {
            "key": "",
            "value": {
                "visible_record_ids": [self.object.pk],
                "animate_tracks": True,
            },
        }
        context["map_tile_layer"] = map_tile_layer()
        context["detail_sections"] = access_record_detail_sections(self.object, "map")
        context["detail_navigation_label"] = "Access record sections"
        return context


class AccessRecordHistoryView(
    PaginatedObjectHistoryMixin,
    LoginRequiredMixin,
    DetailView,
):
    model = AccessRecord
    template_name = "sites/access_record_history.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = access_record_detail_sections(
            self.object, "history"
        )
        context["detail_navigation_label"] = "Access record sections"
        context.update(self.get_history_context())
        return context


class AccessRecordRevisionsView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_revisions.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = access_record_detail_sections(
            self.object, "revisions"
        )
        context["detail_navigation_label"] = "Access record sections"
        return context


class AccessRecordUpdateView(LoginRequiredMixin, UpdateView):
    model = AccessRecord
    form_class = AccessRecordForm
    template_name = "object_form.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site")

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Edit {self.object.name}"
        context["cancel_url"] = self.get_cancel_url()
        return context


class AccessRecordVersionCreateView(LoginRequiredMixin, FormView):
    form_class = AccessRecordVersionUploadForm
    template_name = "sites/access_record_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.access_record = get_object_or_404(
            AccessRecord.objects.select_related("site"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["access_record"] = self.access_record
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        create_access_record_version_from_upload(
            access_record=self.access_record,
            user=self.request.user,
            geojson=form.cleaned_data["geojson"],
            change_note=form.cleaned_data["change_note"],
        )
        if form.staged_upload is not None:
            form.staged_upload.delete()
        if form.replaced_staged_upload is not None:
            form.replaced_staged_upload.delete()
        messages.success(self.request, "Access record revision uploaded.")
        return redirect(self.access_record.site.get_absolute_url())

    def form_invalid(self, form):
        self._stage_uploaded_geojson(form)
        return super().form_invalid(form)

    def _stage_uploaded_geojson(self, form):
        if form.staged_upload is not None or "geojson" not in form.cleaned_data:
            return
        form.staged_upload = create_access_record_upload_draft(
            user=self.request.user,
            access_record=self.access_record,
            geojson=form.cleaned_data["geojson"],
            file_name=form.cleaned_data["geojson_file_name"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.access_record.site
        context["access_record"] = self.access_record
        context["form_title"] = f"Upload Revision > {self.access_record.name}"
        context["cancel_url"] = self.access_record.site.get_absolute_url()
        return context
