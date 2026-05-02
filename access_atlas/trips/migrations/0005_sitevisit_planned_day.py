from django.db import migrations, models
from django.utils import timezone


def populate_planned_day(apps, schema_editor):
    SiteVisit = apps.get_model("trips", "SiteVisit")
    for site_visit in SiteVisit.objects.select_related("trip").all():
        if site_visit.planned_day:
            continue
        if site_visit.planned_start:
            site_visit.planned_day = timezone.localtime(site_visit.planned_start).date()
        else:
            site_visit.planned_day = site_visit.trip.start_date
        site_visit.save(update_fields=["planned_day"])


class Migration(migrations.Migration):
    dependencies = [
        ("trips", "0004_historicaltrip_approval_round_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="sitevisit",
            options={"ordering": ["trip", "planned_day", "planned_start", "site__code", "id"]},
        ),
        migrations.AddField(
            model_name="historicalsitevisit",
            name="planned_day",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitevisit",
            name="planned_day",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(populate_planned_day, migrations.RunPython.noop),
    ]
