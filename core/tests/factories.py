from accounts.models import User
from innovators.models import InnovatorProfile


DEFAULT_PASSWORD = "StrongPass!739"


def create_admin(email="admin@ttu.ac.ke", password=DEFAULT_PASSWORD):
    return User.objects.create_user(
        email=email,
        password=password,
        first_name="Hub",
        last_name="Administrator",
        role=User.Role.ADMIN,
        account_status=User.AccountStatus.ACTIVE,
        email_verified=True,
        activation_completed=True,
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
):
    user = User.objects.create_user(
        email=email,
        password=password if active else None,
        first_name=first_name,
        last_name=last_name,
        role=User.Role.INNOVATOR,
        account_status=User.AccountStatus.ACTIVE if active else User.AccountStatus.PENDING,
        email_verified=active,
        activation_completed=active,
        is_active=active,
    )
    if not active:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    InnovatorProfile.objects.create(
        user=user,
        registration_number=registration_number,
        phone_number="0712345678",
        innovation_project_name=project,
    )
    return user
