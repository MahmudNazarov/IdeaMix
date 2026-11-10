"""Small template helpers used across IdeaMix templates."""

from django import template

from apps.utils import compact_number, split_tags

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Return the current query string with some parameters replaced."""
    request = context.get('request')
    if request is None:
        return ''
    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.filter
def initials(user):
    """Return up to two uppercase initials for an avatar placeholder."""
    if not user:
        return '?'
    source = user.get_full_name() or user.username
    parts = [part for part in source.split() if part]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


@register.filter
def field_class(field, css_class):
    """Replace a bound field's widget class (used for compact forms)."""
    field.field.widget.attrs['class'] = css_class
    return field


@register.filter
def card_hue(idea):
    """Stable hue for generated idea covers."""
    try:
        return (int(idea.pk or 0) * 47 + 18) % 360
    except (TypeError, ValueError):
        return 250


@register.filter
def status_class(value):
    mapping = {
        'draft': 'status-draft',
        'published': 'status-published',
        'in_progress': 'status-progress',
        'completed': 'status-completed',
        'planning': 'status-planning',
        'active': 'status-progress',
        'paused': 'status-paused',
    }
    return mapping.get(value, 'status-default')


@register.filter
def compact(value):
    return compact_number(value)


@register.filter
def tags_list(value):
    return split_tags(value)


@register.simple_tag
def elided_page_range(page_obj):
    return page_obj.paginator.get_elided_page_range(page_obj.number)
