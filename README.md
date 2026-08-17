# Tsavo Innovation & Incubation Hub Management System

A secure, template-based Django application for the Tsavo Innovation & Incubation Hub at Taita Taveta University. It manages administrator-provisioned innovator accounts, email OTP activation, profiles, daily hub attendance, visit outcomes, live monitoring, corrections, and audit history.

The interface uses the requested TTU green, gold, and white identity with a responsive icon sidebar. The supplied Tsavo Hub logo is bundled at `static/image/tsavo_logo.jpeg`; `SITE_LOGO_URL` can override it for a deployment-specific asset.

## Main features

- Email-only authentication with a custom Django user model and extensible roles
- Administrator-created innovator accounts; no public registration
- Secure six-digit activation codes generated with `secrets`, stored as password hashes, valid for 15 minutes, single use, attempt-limited, and resend-limited
- Password creation, password reset, password change, and POST-only logout
- Restricted innovator profile editing and full administrator profile management
- Transactional check-in and check-out with server-owned timestamps
- One-active-session database constraint and automatic incomplete flagging for missed prior-day checkout
- Innovator dashboard with live visual elapsed time and server-calculated weekly totals
- Administrator dashboard with live occupancy, today's work, incomplete sessions, totals, and seven-day visit chart
- Administrator attendance search by innovator first name, last name, or full name
- Reason-required attendance corrections with immutable correction and audit records
- Hardened production settings for HTTPS, cookies, HSTS, framing, secrets, and allowed hosts
- Automated coverage for authentication, OTP rules, permissions, attendance, corrections, filters, and dashboard totals

## Project structure

```text
tsavo_hub/
├── manage.py
├── requirements.txt
├── .env.example
├── README.md
├── tsavo_hub/       # Settings, root URLs, ASGI and WSGI
├── core/            # Shared pages, permissions and branding context
├── accounts/        # Custom user, authentication and activation OTPs
├── innovators/      # Innovator profiles and account management
├── attendance/      # Sessions, transactional services and corrections
├── dashboard/       # Role dashboards, reporting and filters
├── auditlog/        # Administrative audit records
├── templates/       # Shared, page and email templates
├── static/          # TTU-themed CSS and browser-only elapsed-time JS
└── media/           # User-uploaded profile photos
```

## Requirements

- Python 3.12 or newer (developed and verified with Python 3.14)
- Django 6.0
- SQLite for local development, or PostgreSQL for production
- Pillow for profile photos
- A working SMTP provider for production email

## Local installation

Clone the repository, enter its directory, and create an isolated environment.

PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for the local machine. `.env` is ignored by Git and must never be committed. For local SQLite development, these values are sufficient:

```dotenv
SECRET_KEY=generate-a-unique-local-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

Generate a secret without placing it in source control:

```powershell
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

The settings module reads process environment variables and an optional root `.env` file. Existing process variables take precedence.

## Database and first administrator

Apply migrations, then create the initial administrator. The custom manager automatically assigns the `ADMIN` role and active/verified status to a superuser.

```powershell
py manage.py migrate
py manage.py createsuperuser
```

The prompt asks for an email address rather than a username. Start the development server:

```powershell
py manage.py runserver
```

Open `http://127.0.0.1:8000/accounts/login/`. After login, use **Create innovator**. The new user has an unusable password until they verify the emailed code and create one.

## Development email testing

When `DEBUG=True`, Django's console email backend is selected automatically. Creating an innovator prints the complete test email to the server console, which makes the activation flow testable without SMTP. Treat console output as sensitive development data and never use this backend in a shared or production environment.

Password-reset emails also use the console backend during local development. The reset response is deliberately generic whether or not an account exists.

## PostgreSQL and production SMTP

Set `DATABASE_URL` to a PostgreSQL connection string. URL-encode reserved characters in credentials.

```dotenv
DEBUG=False
SECRET_KEY=a-long-unique-secret-from-a-secure-secret-manager
ALLOWED_HOSTS=hub.example.edu
DATABASE_URL=postgresql://tsavo_user:encoded_password@database-host:5432/tsavo_hub
EMAIL_HOST=smtp.example.edu
EMAIL_PORT=587
EMAIL_HOST_USER=smtp-account
EMAIL_HOST_PASSWORD=secret-from-your-secret-manager
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Tsavo Hub <noreply@example.edu>
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://hub.example.edu
```

With `DEBUG=False`, the SMTP backend is selected automatically. Verify sender-domain authentication and delivery before onboarding users.

## Tests and verification

Run the complete automated suite and framework checks:

```powershell
py manage.py test
py manage.py check
py manage.py makemigrations --check --dry-run
py manage.py collectstatic --noinput
```

For an explicit production settings review, provide non-placeholder environment values and run:

```powershell
py manage.py check --deploy
```

## Attendance behavior

- Check-in and checkout timestamps come only from the server.
- An innovator can have one active session. This is enforced in services and with a conditional database uniqueness constraint.
- Starting a new visit on a later Nairobi calendar date changes the old active session to `INCOMPLETE`; it does not invent a checkout time.
- Innovators can view only their own records and cannot submit timestamp fields.
- Administrator corrections require a reason and preserve previous/new values in both a correction record and the audit log.
- Ordinary attendance records cannot be deleted or edited through the Django admin; use the audited correction workflow.

## Production deployment considerations

- Deploy behind a maintained HTTPS reverse proxy and keep `DEBUG=False`.
- Store `SECRET_KEY`, database credentials, and email credentials in the platform's secret manager, not a file in the release artifact.
- Set exact `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`; do not use wildcards.
- If and only if a trusted proxy sets `X-Forwarded-Proto`, set `TRUST_PROXY_SSL_HEADER=True`.
- Run `migrate` and `collectstatic --noinput` during deployment.
- Serve static and uploaded media separately from the Django process. Validate backup and restore procedures for both PostgreSQL and media.
- Use a production WSGI/ASGI server suitable for the deployment platform and configure process health checks, structured logs, monitoring, and error reporting.
- Restrict Django admin access operationally. Application records are view-only there where edits would bypass audit workflows.
- Review retention, privacy, access, and incident-response policies with Taita Taveta University before processing real personal data.
- Keep the supplied Tsavo Hub logo or set `SITE_LOGO_URL` to an authorized replacement asset's static or hosted path.

## Git hygiene

The repository ignores `.env`, SQLite databases, uploaded media, collected static output, virtual environments, caches, coverage files, and logs. Commit migration files whenever models change, but never commit real credentials, activation codes, email output, or user uploads.
