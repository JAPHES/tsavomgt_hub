from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_alter_attendancesession_planned_activity"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="attendancesession",
            name="planned_activity",
        ),
        migrations.RemoveField(
            model_name="attendancesession",
            name="next_step",
        ),
    ]
