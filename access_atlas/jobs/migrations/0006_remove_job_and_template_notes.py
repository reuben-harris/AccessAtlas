from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0005_workprogramme_nullable_dates"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="historicaljob",
            name="notes",
        ),
        migrations.RemoveField(
            model_name="historicaljobtemplate",
            name="notes",
        ),
        migrations.RemoveField(
            model_name="job",
            name="notes",
        ),
        migrations.RemoveField(
            model_name="jobtemplate",
            name="notes",
        ),
    ]
