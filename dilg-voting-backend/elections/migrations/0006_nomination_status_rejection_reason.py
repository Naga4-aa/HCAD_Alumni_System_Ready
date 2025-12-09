from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("elections", "0005_election_mode_demo_phase"),
    ]

    operations = [
        migrations.AddField(
            model_name="nomination",
            name="rejection_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="nomination",
            name="status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("promoted", "Promoted"), ("rejected", "Rejected")],
                default="pending",
                max_length=20,
            ),
        ),
    ]
