from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("elections", "0003_election_results_published_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="election",
            name="nomination_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="election",
            name="nomination_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="election",
            name="voting_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="election",
            name="voting_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
