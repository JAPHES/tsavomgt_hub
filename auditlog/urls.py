from django.urls import path

from . import views

app_name = "auditlog"

urlpatterns = [path("", views.audit_list, name="list")]
