from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0006_remove_job_and_template_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicaljob",
            name="completed_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="completed_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
