from .models import AuditLog


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def record_audit(
    *, actor, action, target, previous_values=None, new_values=None, reason="", request=None
):
    """Record only explicitly supplied, non-secret values."""
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model=target._meta.label,
        target_id=str(target.pk),
        target_repr=str(target)[:255],
        previous_values=previous_values or {},
        new_values=new_values or {},
        reason=reason,
        ip_address=client_ip(request),
    )
