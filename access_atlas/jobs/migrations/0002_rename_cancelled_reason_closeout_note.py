from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="job",
            old_name="cancelled_reason",
            new_name="closeout_note",
        ),
        migrations.RenameField(
            model_name="historicaljob",
            old_name="cancelled_reason",
            new_name="closeout_note",
        ),
    ]
