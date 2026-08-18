from django.conf import settings


def branding(request):
    return {
        "site_logo_url": settings.SITE_LOGO_URL,
        "static_version": settings.STATIC_VERSION,
    }
