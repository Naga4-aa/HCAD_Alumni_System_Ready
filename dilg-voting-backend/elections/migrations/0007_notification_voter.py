from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("elections", "0006_nomination_status_rejection_reason"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(default="info", max_length=80)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("is_hidden", models.BooleanField(db_column="dismissed", default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "voter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="notifications",
                        to="elections.voter",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
