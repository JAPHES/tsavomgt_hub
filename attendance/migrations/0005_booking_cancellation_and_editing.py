import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0004_hubbooking"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="hubbooking",
            name="unique_daily_booking_per_innovator",
        ),
        migrations.RemoveConstraint(
            model_name="hubbooking",
            name="booking_admission_fields_match_status",
        ),
        migrations.AddField(
            model_name="hubbooking",
            name="cancellation_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="hubbooking",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="hubbooking",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cancelled_hub_bookings",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="hubbooking",
            name="status",
            field=models.CharField(
                choices=[
                    ("BOOKED", "Booked"),
                    ("ADMITTED", "Admitted"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="BOOKED",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="hubbooking",
            constraint=models.UniqueConstraint(
                condition=~models.Q(status="CANCELLED"),
                fields=("innovator", "visit_date"),
                name="unique_active_daily_booking_per_innovator",
                violation_error_message="You already have a hub booking for this date.",
            ),
        ),
        migrations.AddConstraint(
            model_name="hubbooking",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status="BOOKED",
                        admitted_at__isnull=True,
                        admitted_by__isnull=True,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason="",
                    )
                    | models.Q(
                        status="ADMITTED",
                        admitted_at__isnull=False,
                        admitted_by__isnull=False,
                        cancelled_at__isnull=True,
                        cancelled_by__isnull=True,
                        cancellation_reason="",
                    )
                    | (
                        models.Q(
                            status="CANCELLED",
                            admitted_at__isnull=True,
                            admitted_by__isnull=True,
                            cancelled_at__isnull=False,
                            cancelled_by__isnull=False,
                        )
                        & ~models.Q(cancellation_reason="")
                    )
                ),
                name="booking_lifecycle_fields_match_status",
            ),
        ),
    ]
