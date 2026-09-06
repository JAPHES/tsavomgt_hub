from django.urls import path

from . import views

app_name = "innovators"

urlpatterns = [
    path("profile/complete/", views.complete_my_profile, name="profile-complete"),
    path("profile/", views.my_profile, name="profile"),
    path("profile/edit/", views.edit_my_profile, name="profile-edit"),
    path("projects/", views.my_projects, name="projects"),
    path("projects/<int:pk>/edit/", views.update_my_project, name="project-update"),
    path(
        "projects/<int:pk>/proposal/",
        views.download_project_proposal,
        name="project-proposal",
    ),
    path("manage/", views.innovator_list, name="manage"),
    path("project-directory/", views.project_directory, name="project-directory"),
    path("export/", views.export_innovators, name="export"),
    path("create/", views.innovator_create, name="create"),
    path("create/success/<int:pk>/", views.create_success, name="create-success"),
    path("<int:pk>/", views.innovator_detail, name="detail"),
    path("<int:pk>/edit/", views.innovator_update, name="update"),
    path("<int:pk>/delete/", views.innovator_delete, name="delete"),
    path("<int:pk>/status/", views.toggle_status, name="toggle-status"),
    path(
        "<int:pk>/reissue-credentials/",
        views.admin_reissue_credentials,
        name="admin-reissue-credentials",
    ),
]
