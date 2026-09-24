"""Database outage state and notifications that do not depend on PostgreSQL."""

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"


def _state_path():
    return Path(settings.DATABASE_OUTAGE_STATE_FILE)


def _default_state():
    return {
        "database": UNKNOWN,
        "incident_alerted": False,
        "last_outage_alert_attempt": 0,
    }


def _read_state():
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return _default_state()
    if not isinstance(data, dict):
        return _default_state()
    return {**_default_state(), **data}


def _write_state(state):
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
    temporary_path.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary_path, path)


@contextmanager
def _state_lock():
    """Acquire a small cross-process lock without requiring another service."""
    lock_path = _state_path().with_suffix(f"{_state_path().suffix}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 2
    file_descriptor = None
    while file_descriptor is None:
        try:
            file_descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            try:
                is_stale = time.time() - lock_path.stat().st_mtime > 30
            except OSError:
                is_stale = False
            if is_stale:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                yield False
                return
            time.sleep(0.05)
    try:
        os.write(file_descriptor, str(os.getpid()).encode("ascii"))
        yield True
    finally:
        os.close(file_descriptor)
        try:
            lock_path.unlink()
        except OSError:
            pass


def database_status():
    """Return the last observed database status without querying the database."""
    return _read_state()["database"]


def _send_notification(subject, body):
    recipients = settings.OUTAGE_ADMIN_EMAILS
    if not recipients:
        logger.warning(
            "Database status changed, but OUTAGE_ADMIN_EMAILS is not configured."
        )
        return False
    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        ).send(fail_silently=False)
    except Exception:
        # Email delivery must never turn an outage response into another error.
        logger.exception("Database status notification could not be delivered.")
        return False
    return True


def mark_database_unavailable():
    """Record an outage and send at most one alert per incident/cooldown."""
    now = int(time.time())
    should_notify = False
    with _state_lock() as acquired:
        if not acquired:
            return
        state = _read_state()
        if state["database"] != UNAVAILABLE:
            state["database"] = UNAVAILABLE
            state["incident_alerted"] = False

        cooldown = settings.DATABASE_OUTAGE_ALERT_COOLDOWN_SECONDS
        outside_cooldown = now - state["last_outage_alert_attempt"] >= cooldown
        if not state["incident_alerted"] and outside_cooldown:
            state["last_outage_alert_attempt"] = now
            should_notify = True
        _write_state(state)

    if not should_notify:
        return

    delivered = _send_notification(
        "Tsavo Hub Service Interruption",
        (
            "Tsavo Innovation & Incubation Hub is currently experiencing a "
            "database service interruption. Some platform features may be "
            "temporarily unavailable. The technical team has been notified."
        ),
    )
    if delivered:
        with _state_lock() as acquired:
            if acquired:
                state = _read_state()
                if state["database"] == UNAVAILABLE:
                    state["incident_alerted"] = True
                    _write_state(state)


def mark_database_available():
    """Record recovery and notify once when a reported incident is restored."""
    should_notify = False
    with _state_lock() as acquired:
        if not acquired:
            return
        state = _read_state()
        if state["database"] == AVAILABLE:
            return
        if state["database"] == UNAVAILABLE and state["incident_alerted"]:
            should_notify = True
        state["database"] = AVAILABLE
        state["incident_alerted"] = False
        _write_state(state)

    if should_notify:
        _send_notification(
            "Tsavo Hub Services Restored",
            (
                "Database connectivity for Tsavo Innovation & Incubation Hub "
                "has been restored and normal platform services are available again."
            ),
        )
