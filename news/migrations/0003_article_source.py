from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("news", "0002_roles_and_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="article",
            name="source_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="article",
            name="source_name",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
