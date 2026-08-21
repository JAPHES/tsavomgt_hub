# Tsavo Innovation & Incubation Hub Management System

A secure, server-rendered Django application for managing innovator accounts, planned hub visits, and administrator-controlled admission at the Tsavo Innovation & Incubation Hub, Taita Taveta University.

The application uses Django templates, Bootstrap 5, JavaScript, SQLite for local development, and PostgreSQL for production. It is branded in TTU green, gold, and white and displays the bundled Tsavo Hub logo with the label **Tsavo Hub Management System**.

## Current features

- Email-only authentication with a custom Django user model
- Administrator and innovator roles, with an extensible chairperson role definition
- Administrator-controlled innovator onboarding with no public registration
- Strong temporary login passwords generated with Python's `secrets` module and stored only through Django's password hash
- Mandatory first-login password replacement with server-side access enforcement and forced logout after completion
- Professional split-layout password recovery with clear guidance, plus styled first-login and ordinary password-change forms
- POST-only logout and server-side role authorization
- Responsive sidebar navigation with Bootstrap icons, fluid cards and forms, mobile-friendly data tables, touch-sized controls, and a consistent non-overlapping footer shell
- Tsavo Hub logo branding and a circular favicon across application pages
- Professional two-panel login page with a prominent centered circular logo and branded welcome area on the left, and the sign-in form on the right
- Professional administrator, innovator, profile, booking-history, streamlined innovator-record, and legacy attendance-record pages
- Account-deactivation confirmation warning before the destructive request is submitted
- Audit records for important administrative actions

### Innovator management

The **Add innovator** form collects:

- First name
- Last name
- Email address
- Registration number
- Phone number
- Initial project name
- Initial project details
- Initial project area of focus

Email addresses and registration numbers are unique. New accounts receive a cryptographically generated temporary password by email. Django stores only its secure password hash. The account can use the normal login page, but server-side middleware blocks every other page until the innovator creates a personal password. After the change, the temporary password is invalid, the innovator is signed out, and they must log in again with the new password.

Administrators can:

- Add and search innovators
- View professional innovator records
- Update approved account and contact information
- Reissue temporary login credentials for an innovator who has not completed the first-login password change
- Deactivate accounts after an explicit confirmation warning
- Restore inactive accounts
- Download all innovators as a CSV containing full name, email, projects, and areas of focus

The CSV export is administrator-only, includes the complete list regardless of pagination or search, uses UTF-8 for Excel compatibility, and sanitizes spreadsheet-formula prefixes.

Innovators can update only:

- Phone number
- Profile photo

Email, registration number, role, account status, projects, and booking history cannot be changed through the self-service profile form.

### Project portfolios

Each innovator can own multiple projects. Every project records:

- Project name
- Detailed description
- Area of focus

Innovators add projects from their dashboard. Project creation is transactional, duplicate names for the same innovator are rejected case-insensitively, and every successful addition creates an audit record. Administrators can see the innovator's complete project portfolio, including each project's details and area of focus, from the innovator record page. Project names and focus areas are also searchable in the innovator directory and included in the CSV export.

The upgrade copies every existing profile project into the new portfolio model. Existing descriptions are retained; projects created before areas of focus were collected are marked `Not specified` rather than being assigned invented information.

### Hub bookings and admission

The primary innovator-dashboard form records:

- Visit date
- Expected arrival time
- What the innovator intends to do in the hub

Booking statuses are:

- `BOOKED`
- `ADMITTED`

Booking and admission protections include:

- Today or a future date is required when making a booking
- One booking per innovator per visit date, enforced in service logic and by a database constraint
- Purpose text must contain a useful description
- Booking creation and admission transitions are transactional
- Only an administrator can admit an innovator
- Only today's bookings can be admitted
- Admission uses server time and cannot be back-dated through the form
- An admitted booking cannot be admitted a second time
- Admission status, administrator, and timestamp consistency is enforced at model and database levels
- Every admission creates an audit record
- Innovators can view only their own booking history

The previous innovator self check-in/check-out flow is no longer routed. Existing attendance rows are not deleted during the upgrade; administrators can still open legacy records when historical review is necessary.

### Dashboards and reporting

The innovator workspace provides:

- A centered personalized welcome to Tsavo Hub Management System
- Hub booking form
- Project creation form and complete project portfolio
- Monthly booking and admitted-visit totals
- Recent booking records
- A private booking-history page

The administrator dashboard provides:

- Total active innovator accounts
- Total bookings, awaiting admissions, and admitted innovators today
- A time-ordered table of today's expected innovators
- Expected arrival time, intended activity, admission status, and admission time
- A POST-only action for admitting an innovator upon arrival

The separate booking-records page searches by innovator name only.

## Project structure

```text
tsavo_hub/
|-- manage.py
|-- requirements.txt
|-- .env.example
|-- README.md
|-- tsavo_hub/       # Settings, root URLs, ASGI and WSGI
|-- core/            # Shared pages, permissions, branding and test factories
|-- accounts/        # Custom users, authentication and mandatory first-login security
|-- innovators/      # Innovator profiles, multi-project portfolios, management and CSV export
|-- attendance/      # Hub bookings, admission services and retained legacy attendance data
|-- dashboard/       # Role dashboards and booking search
|-- auditlog/        # Administrative audit records
|-- templates/       # Shared, page and email templates
|-- static/          # Branding, responsive CSS and interface JavaScript
`-- media/           # Uploaded profile photos
```

## Requirements

- Python 3.12 or newer; currently verified with Python 3.14
- Django 6.0
- SQLite for local development or PostgreSQL for production
- Pillow for profile-photo handling
- A production SMTP provider when real email delivery is required

Installable dependencies are pinned by compatible ranges in `requirements.txt`.

## Local installation

Clone the repository and enter its root directory, where `manage.py` is located.

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

## Environment configuration

Never commit a real `.env` file. For local SQLite development, configure at least:

```dotenv
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

Generate a local secret with:

```powershell
py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Store that output as `SECRET_KEY` only in your ignored local `.env` file. When `DEBUG=True` and the value is blank, Django generates an ephemeral development key at process startup; setting a persistent local value prevents sessions from becoming invalid after a restart. Production refuses to start without an explicit secret key.

Supported deployment variables include:

```text
SECRET_KEY
DEBUG
ALLOWED_HOSTS
DATABASE_URL
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
EMAIL_USE_TLS
DEFAULT_FROM_EMAIL
PASSWORD_RESET_TIMEOUT
SECURE_SSL_REDIRECT
CSRF_TRUSTED_ORIGINS
SITE_LOGO_URL
STATIC_VERSION
TRUST_PROXY_SSL_HEADER
```

`SITE_LOGO_URL` may point to an authorized deployment-specific logo. When it is blank, the application uses `static/image/tsavo_logo.jpeg`.

`STATIC_VERSION` is appended to the shared CSS, JavaScript and local logo URLs. Change it whenever those assets change during a deployment so browsers request the current files instead of reusing stale cached copies.

`PASSWORD_RESET_TIMEOUT` is measured in seconds and defaults to `3600` (one hour). The forgot-password page explains this lifetime while retaining Django's generic response so the system does not reveal whether an email address exists.

## Database and first administrator

Apply migrations before starting the application:

```powershell
py manage.py migrate
```

Create the first administrator with the project management command:

```powershell
py manage.py createsuperuser
```

Do not run bare `django-admin createsuperuser` from the repository because it may not know which settings module to load. The custom superuser prompt requests an email address rather than a username.

Start the local server:

```powershell
py manage.py runserver
```

Open `http://127.0.0.1:8000/accounts/login/`.

The login page uses a responsive split layout with the Tsavo Hub logo and welcome message on the left and the sign-in form on the right at widths of 768 pixels and above. It stacks vertically on phones. The general public support banner is intentionally omitted from this page to keep the authentication experience focused.

If an updated interface is not visible, stop and restart the development server, then reload the exact page. Asset URLs include `STATIC_VERSION`, so a normal refresh should fetch the current local CSS and JavaScript. For an already-open page that predates this feature, use `Ctrl+Shift+R` once. In browser developer tools, `/static/css/app.css?v=...` should return HTTP 200. Production deployments must update `STATIC_VERSION` and run `py manage.py collectstatic --noinput` whenever local frontend assets change.

## Email credentials and first login

When `DEBUG=True`, Django automatically uses the console email backend. Adding an innovator prints the login-credentials email to the server terminal so the flow can be tested without SMTP credentials.

Local first-login workflow:

1. Sign in as an administrator.
2. Select **Add innovator** from the sidebar.
3. Submit the innovator details.
4. Read the email address and generated temporary password from the development-server terminal.
5. Open `/accounts/login/` and sign in with those credentials.
6. The system redirects the innovator to `/accounts/first-login/password-change/` and blocks all other authenticated pages.
7. Create and confirm a strong personal password. The system signs the innovator out.
8. Sign in again through `/accounts/login/` using the email address and new personal password.

Treat console email output as sensitive development data because it contains the temporary password. Temporary passwords are never written to audit records or application logs. Password-reset responses remain generic whether or not an email exists, and accounts still awaiting their first password change must ask an administrator to reissue credentials.

The forgot-password page uses the same branded two-panel layout as the login page. It instructs established users to enter their registered email, check spam or junk folders, and use the reset link within one hour. A reset link becomes invalid after the password is successfully changed.

After upgrading an existing database, accounts that had not completed the former activation flow are preserved as pending. Open the innovator's administrator record and select **Reissue login credentials** to generate and email a usable temporary password.

For production SMTP, use values similar to:

```dotenv
DEBUG=False
SECRET_KEY=
ALLOWED_HOSTS=hub.example.edu
DATABASE_URL=postgresql://tsavo_user@database-host:5432/tsavo_hub
EMAIL_HOST=smtp.example.edu
EMAIL_PORT=587
EMAIL_HOST_USER=smtp-account
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Tsavo Hub <noreply@example.edu>
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://hub.example.edu
```

The blank `SECRET_KEY` and `EMAIL_HOST_PASSWORD` entries are deliberate. Supply them through the deployment platform's secret manager. Add the database password through the platform's protected `DATABASE_URL` value rather than committing it to documentation or source control.

With `DEBUG=False`, the SMTP backend is selected automatically. Verify the sender domain and delivery before onboarding real users.

## Main routes

```text
/accounts/login/
/accounts/logout/
/accounts/first-login/password-change/
/accounts/password-reset/
/accounts/password-change/

/innovators/profile/
/innovators/profile/edit/
/innovators/manage/
/innovators/export/
/innovators/create/
/innovators/<id>/

/attendance/bookings/
/attendance/session/<id>/admin/

/dashboard/
/dashboard/innovator/
/dashboard/admin/
/dashboard/admin/bookings/<id>/admit/
/dashboard/bookings/

/audit/
```

All management, export, booking, admission, legacy attendance-review, and audit routes enforce authorization on the server. Navigation visibility is not treated as a security boundary. Hub bookings and retained attendance records are read-only in Django Admin; admission occurs only through the protected application workflow.

## Tests and verification

Run the complete automated suite and framework checks:

```powershell
py manage.py check
py manage.py makemigrations --check --dry-run
py manage.py migrate
py manage.py test
py manage.py collectstatic --noinput
```

Tests cover authentication, secure temporary-password generation and hashing, emailed credentials, mandatory first-login routing, password workflows, permissions, multi-project portfolios and migration, booking validation, admission rules and auditing, legacy attendance retention, dashboards, professional record pages, and CSV export.

For a production configuration review, provide non-placeholder environment values and run:

```powershell
py manage.py check --deploy
```

## Production deployment considerations

- Deploy behind a maintained HTTPS reverse proxy with `DEBUG=False`.
- Store secrets and credentials in the deployment platform's secret manager.
- Set exact `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`; do not use wildcards.
- Set `TRUST_PROXY_SSL_HEADER=True` only when a trusted proxy supplies `X-Forwarded-Proto`.
- Use PostgreSQL and test backup/restore procedures before processing real data.
- Run migrations and `collectstatic --noinput` during deployment.
- Serve static and uploaded media separately from the Django process.
- Use a maintained WSGI/ASGI server with health checks, logs, monitoring, and error reporting.
- Restrict Django Admin operationally; sensitive application records are read-only where direct edits would bypass audited workflows.
- Review data retention, privacy, access, and incident-response policies with Taita Taveta University.

## Git hygiene

The repository ignores `.env`, SQLite databases, uploaded media, collected static output, virtual environments, caches, coverage output, and logs.

Commit model migrations together with their corresponding model changes. Never commit real credentials, temporary passwords, email output, database files, or user uploads.
