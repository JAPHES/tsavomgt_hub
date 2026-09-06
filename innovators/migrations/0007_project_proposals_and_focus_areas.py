import django.core.validators
from django.db import migrations, models

import innovators.models


CURATED_FOCUS_AREAS = (
    "Agriculture and Food Systems",
    "Artificial Intelligence and Machine Learning",
    "Biotechnology",
    "Climate Change and Environmental Sustainability",
    "Construction and Built Environment",
    "Creative Industries and Digital Media",
    "Cybersecurity",
    "Education Technology",
    "Financial Technology",
    "Health and Medical Technology",
    "Information and Communication Technology",
    "Internet of Things",
    "Manufacturing and Industrial Innovation",
    "Renewable Energy and Clean Technology",
    "Robotics and Automation",
    "Social Innovation",
    "Transport and Mobility",
    "Water and Sanitation",
)


def create_focus_areas_and_migrate_existing_projects(apps, schema_editor):
    ProjectFocusArea = apps.get_model("innovators", "ProjectFocusArea")
    InnovatorProject = apps.get_model("innovators", "InnovatorProject")

    focus_by_normalized_name = {}
    for name in CURATED_FOCUS_AREAS:
        focus, _ = ProjectFocusArea.objects.get_or_create(name=name)
        focus_by_normalized_name[name.casefold()] = focus

    for project in InnovatorProject.objects.all().iterator():
        old_focus = " ".join((project.legacy_area_of_focus or "").split())
        if not old_focus:
            continue
        focus = focus_by_normalized_name.get(old_focus.casefold())
        if focus is None:
            focus, _ = ProjectFocusArea.objects.get_or_create(name=old_focus)
            focus_by_normalized_name[old_focus.casefold()] = focus
        project.focus_areas.add(focus)


class Migration(migrations.Migration):
    dependencies = [
        ("innovators", "0006_add_required_profile_details"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectFocusArea",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddField(
            model_name="innovatorproject",
            name="focus_areas",
            field=models.ManyToManyField(
                related_name="projects",
                to="innovators.projectfocusarea",
            ),
        ),
        migrations.AddField(
            model_name="innovatorproject",
            name="proposal",
            field=models.FileField(
                blank=True,
                max_length=500,
                upload_to=innovators.models.project_proposal_upload_to,
                validators=[django.core.validators.FileExtensionValidator(["pdf"])],
            ),
        ),
        migrations.RemoveIndex(
            model_name="innovatorproject",
            name="innovators__area_of_40a37e_idx",
        ),
        migrations.RenameField(
            model_name="innovatorproject",
            old_name="details",
            new_name="legacy_details",
        ),
        migrations.RenameField(
            model_name="innovatorproject",
            old_name="area_of_focus",
            new_name="legacy_area_of_focus",
        ),
        migrations.AlterField(
            model_name="innovatorproject",
            name="legacy_details",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.AlterField(
            model_name="innovatorproject",
            name="legacy_area_of_focus",
            field=models.CharField(
                blank=True,
                default="",
                editable=False,
                max_length=150,
            ),
        ),
        migrations.RunPython(
            create_focus_areas_and_migrate_existing_projects,
            migrations.RunPython.noop,
        ),
    ]
