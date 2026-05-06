from __future__ import annotations

from django_tomselect.app_settings import Const, PluginRemoveButton, TomSelectConfig


def site_tomselect_config(*, placeholder: str = "Search sites") -> TomSelectConfig:
    """Standard single-select config for site lookups across planning forms."""

    return TomSelectConfig(
        url="autocomplete_sites",
        css_framework="bootstrap5",
        label_field="label",
        placeholder=placeholder,
        minimum_query_length=0,
        preload="focus",
    )


def team_members_tomselect_config() -> TomSelectConfig:
    """Standard multi-select config for trip team members."""

    return TomSelectConfig(
        url="autocomplete_team_members",
        css_framework="bootstrap5",
        label_field="label",
        placeholder="Select team members",
        minimum_query_length=0,
        preload="focus",
        plugin_remove_button=PluginRemoveButton(),
    )


def job_template_tomselect_config(
    *,
    placeholder: str = "Search templates",
) -> TomSelectConfig:
    """Standard single-select config for active job templates."""

    return TomSelectConfig(
        url="autocomplete_job_templates",
        css_framework="bootstrap5",
        label_field="title",
        placeholder=placeholder,
        minimum_query_length=0,
        preload="focus",
    )


def work_programme_tomselect_config(
    *,
    placeholder: str = "Search work programmes",
) -> TomSelectConfig:
    """Standard single-select config for assigning jobs to work programmes."""

    return TomSelectConfig(
        url="autocomplete_work_programmes",
        css_framework="bootstrap5",
        label_field="label",
        placeholder=placeholder,
        minimum_query_length=0,
        preload="focus",
    )


def assignable_jobs_tomselect_config(site_id: int) -> TomSelectConfig:
    """Filter unassigned-job autocomplete results down to one site."""

    return TomSelectConfig(
        url="autocomplete_unassigned_jobs",
        css_framework="bootstrap5",
        label_field="label",
        placeholder="Search jobs",
        minimum_query_length=0,
        preload="focus",
        filter_by=[Const(str(site_id), "site_id")],
    )
