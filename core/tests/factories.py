import secrets

from accounts.models import User
from innovators.models import InnovatorProfile, InnovatorProject


def make_test_password():
    """Create a validator-compliant credential at runtime, never in source control."""
    return f"T9!a-{secrets.token_urlsafe(18)}"


DEFAULT_PASSWORD = make_test_password()


def create_admin(email="admin@ttu.ac.ke", password=DEFAULT_PASSWORD):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Hub",
        last_name="Administrator",
        role=User.Role.ADMIN,
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        must_change_password=False,
        is_active=True,
        is_staff=True,
    )


def create_innovator(
    email="innovator@students.ttu.ac.ke",
    registration_number="TTU/INN/001",
    password=DEFAULT_PASSWORD,
    active=True,
    first_name="Amina",
    last_name="Juma",
    project="BlueWatch",
    project_details="A water-quality monitoring and alert platform for local communities.",
    area_of_focus="Climate technology",
    must_change_password=False,
):
    user = User.objects.create_user(
        email=email,
        password=password if active else None,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.INNOVATOR,
        account_status=(
            User.AccountStatus.PENDING
            if must_change_password
            else User.AccountStatus.ACTIVE if active else User.AccountStatus.INACTIVE
        ),
        email_verified=active and not must_change_password,
        must_change_password=must_change_password,
        is_active=active,
    )
    if not active:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    profile = InnovatorProfile.objects.create(
        user=user,
        registration_number=registration_number,
        phone_number="0712345678",
        innovation_project_name=project,
        project_description=project_details,
    )
    InnovatorProject.objects.create(
        profile=profile,
        name=project,
        details=project_details,
        area_of_focus=area_of_focus,
    )
    return user
