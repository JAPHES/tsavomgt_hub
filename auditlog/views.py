from django.core.paginator import Paginator
from django.shortcuts import render

from core.permissions import admin_required

from .models import AuditLog


@admin_required
def audit_list(request):
    records = AuditLog.objects.select_related("actor")
    action = request.GET.get("action", "")
    if action:
        records = records.filter(action=action)
    page_obj = Paginator(records, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "auditlog/audit_list.html",
        {"page_obj": page_obj, "actions": AuditLog.Action.choices, "selected_action": action},
    )
