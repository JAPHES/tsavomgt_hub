from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auditlog", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("ACCOUNT_CREATED", "Innovator account added"),
                    ("ACCOUNT_UPDATED", "Account updated"),
                    ("ACCOUNT_ACTIVATED", "Account activated"),
                    ("ACCOUNT_DEACTIVATED", "Account deactivated"),
                    ("OTP_RESENT", "Activation code resent"),
                    ("ATTENDANCE_CORRECTED", "Attendance corrected"),
                    ("INCOMPLETE_SESSION_CLOSED", "Incomplete session closed"),
                    ("ROLE_CHANGED", "User role changed"),
                ],
                max_length=40,
            ),
        ),
    ]
