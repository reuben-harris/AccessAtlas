from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sites", "0005_historicalsite_tags_site_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalsitephoto",
            name="image_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="sitephoto",
            name="image_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddIndex(
            model_name="sitephoto",
            index=models.Index(
                fields=["site", "image_sha256"],
                name="site_photo_hash_idx",
            ),
        ),
    ]
