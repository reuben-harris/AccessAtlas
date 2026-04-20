from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from access_atlas.jobs.models import Job, JobStatus, JobTemplate
from access_atlas.sites.models import Site
from access_atlas.trips.models import Trip, TripStatus


@login_required
def dashboard(request):
    context = {
        "planned_trips": Trip.objects.exclude(status=TripStatus.COMPLETED)[:5],
        "unassigned_jobs": Job.objects.filter(
            status=JobStatus.UNASSIGNED,
            site_visit_assignment__isnull=True,
        )[:10],
        "blocked_jobs": Job.objects.filter(status=JobStatus.BLOCKED)[:10],
        "site_count": Site.objects.count(),
        "job_template_count": JobTemplate.objects.filter(is_active=True).count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    results = {
        "sites": [],
        "jobs": [],
        "job_templates": [],
        "trips": [],
    }
    if query:
        results["sites"] = Site.objects.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )[:10]
        results["jobs"] = Job.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(site__code__icontains=query)
            | Q(site__name__icontains=query)
        )[:10]
        results["job_templates"] = JobTemplate.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )[:10]
        results["trips"] = Trip.objects.filter(
            Q(name__icontains=query) | Q(notes__icontains=query)
        )[:10]
    return render(request, "core/search.html", {"query": query, "results": results})
