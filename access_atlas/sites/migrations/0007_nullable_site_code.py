from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0006_sitephoto_image_hash"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalsite",
            name="code",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="site",
            name="code",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
