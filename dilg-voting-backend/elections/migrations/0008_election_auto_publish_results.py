from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("elections", "0007_notification_voter"),
    ]

    operations = [
        migrations.AddField(
            model_name="election",
            name="auto_publish_results",
            field=models.BooleanField(default=True),
        ),
    ]
