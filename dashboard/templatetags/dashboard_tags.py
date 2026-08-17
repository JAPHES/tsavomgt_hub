from django import template

register = template.Library()


@register.filter
def duration_hm(value):
    if value is None:
        return "—"
    total_minutes = max(0, int(value.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes:02d}m"
