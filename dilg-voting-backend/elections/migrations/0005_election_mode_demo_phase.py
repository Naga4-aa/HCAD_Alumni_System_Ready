from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("elections", "0004_allow_null_timelines"),
    ]

    operations = [
        migrations.AddField(
            model_name="election",
            name="demo_phase",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name="election",
            name="mode",
            field=models.CharField(
                choices=[("timeline", "Timeline"), ("demo", "Demo")],
                default="timeline",
                max_length=20,
            ),
        ),
    ]

