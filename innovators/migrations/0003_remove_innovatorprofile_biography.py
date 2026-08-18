from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("innovators", "0002_remove_innovatorprofile_course_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="innovatorprofile",
            name="biography",
        ),
    ]
