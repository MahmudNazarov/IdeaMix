"""Aggregated metrics for the custom Django admin dashboard."""

from __future__ import annotations

import math
from datetime import timedelta

from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Count, Q, Sum
from django.template import Library
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.models import (
    Category,
    Comment,
    Favorite,
    Idea,
    IdeaLike,
    Project,
    ProjectMember,
    UserActivity,
    UserProfile,
)
from apps.utils import compact_number

register = Library()

# Geometry of the inline SVG chart on the dashboard.
CHART_WIDTH = 720
CHART_HEIGHT = 250
CHART_PAD_LEFT = 40
CHART_PAD_RIGHT = 30
CHART_PAD_TOP = 24
CHART_PAD_BOTTOM = 46
CHART_TICKS = 4


def _admin_url(model, action='changelist'):
    opts = model._meta
    try:
        return reverse(f'admin:{opts.app_label}_{opts.model_name}_{action}')
    except NoReverseMatch:
        return ''


def _metric(label, value, *, url='', hint=''):
    try:
        numeric = int(value or 0)
    except (TypeError, ValueError):
        numeric = 0
    return {
        'label': label,
        'value': numeric,
        'display': compact_number(numeric),
        'url': url,
        'hint': hint,
    }


def _detail(label, value):
    try:
        numeric = int(value or 0)
    except (TypeError, ValueError):
        numeric = 0
    return {'label': label, 'value': compact_number(numeric)}


def _has_perm(user, model, action='view'):
    opts = model._meta
    return bool(user and user.has_perm(f'{opts.app_label}.{action}_{opts.model_name}'))


def _axis_step(max_value, ticks=CHART_TICKS):
    """Pick a round axis step so every tick label is a whole number."""
    if max_value <= ticks:
        return 1
    raw = max_value / ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if magnitude * factor >= raw:
            return magnitude * factor
    return magnitude * 10


def _format_tick(value):
    return f'{value:g}'


def _online_chart(points):
    """Build SVG coordinates for the seven-day presence chart."""
    plot_width = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
    plot_height = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
    baseline = CHART_PAD_TOP + plot_height
    step = _axis_step(max((point['value'] for point in points), default=0))
    top = step * CHART_TICKS
    last_index = max(len(points) - 1, 1)

    chart_points = []
    for index, point in enumerate(points):
        x = CHART_PAD_LEFT + plot_width * index / last_index
        y = baseline - (point['value'] / top) * plot_height
        chart_points.append(
            {
                'date': point['date'],
                'value': point['value'],
                'x': round(x, 1),
                'y': round(y, 1),
                'label_y': round(max(y - 11, CHART_PAD_TOP - 4), 1),
            }
        )

    line = ' '.join(f"{point['x']},{point['y']}" for point in chart_points)
    area = ''
    if chart_points:
        first, last = chart_points[0], chart_points[-1]
        area = (
            f"M {first['x']},{baseline} "
            f"L {line.replace(' ', ' L ')} "
            f"L {last['x']},{baseline} Z"
        )

    grid = []
    for tick in range(CHART_TICKS + 1):
        value = step * tick
        grid.append(
            {
                'y': round(baseline - (value / top) * plot_height, 1),
                'label': _format_tick(value),
            }
        )

    return {
        'width': CHART_WIDTH,
        'height': CHART_HEIGHT,
        'left': CHART_PAD_LEFT,
        'right': CHART_WIDTH - CHART_PAD_RIGHT,
        'baseline': baseline,
        'grid': grid,
        'points': chart_points,
        'line': line,
        'area': area,
    }


def _online_overview(now, days=7):
    """Unique daily visitors for the last ``days`` days (today included)."""
    today = timezone.localdate(now)
    start = today - timedelta(days=days - 1)

    rows = (
        UserActivity.objects.filter(date__gte=start, date__lte=today)
        .values('date')
        .annotate(total=Count('user', distinct=True))
    )
    counts = {row['date']: row['total'] for row in rows}
    dates = [start + timedelta(days=offset) for offset in range(days)]
    points = [{'date': day, 'value': counts.get(day, 0)} for day in dates]
    values = [point['value'] for point in points]

    window = timedelta(
        minutes=getattr(settings, 'ONLINE_WINDOW_MINUTES', 15)
    )
    online_now = (
        UserActivity.objects.filter(last_seen__gte=now - window).aggregate(
            total=Count('user', distinct=True)
        )['total']
        or 0
    )

    return {
        'now': online_now,
        'today': values[-1],
        'peak': max(values),
        'average': round(sum(values) / days, 1),
        'total': sum(values),
        'points': points,
        'chart': _online_chart(points),
    }


@register.simple_tag(takes_context=True)
def admin_dashboard(context):
    """Return grouped platform metrics for ``admin/index.html``.

    Every model is aggregated separately on purpose: joining ideas with likes
    and comments in a single query would multiply the view counter and skew
    the dashboard.
    """
    user = context.get('user')
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    users = User.objects.aggregate(
        total=Count('pk'),
        active=Count('pk', filter=Q(is_active=True)),
        staff=Count('pk', filter=Q(is_staff=True)),
        superusers=Count('pk', filter=Q(is_superuser=True)),
        new_week=Count('pk', filter=Q(date_joined__gte=week_ago)),
    )
    profiles = UserProfile.objects.aggregate(
        total=Count('pk'),
        with_bio=Count('pk', filter=~Q(bio='')),
    )
    ideas = Idea.objects.aggregate(
        total=Count('pk'),
        published=Count('pk', filter=Q(status=Idea.PUBLISHED)),
        in_progress=Count('pk', filter=Q(status=Idea.IN_PROGRESS)),
        completed=Count('pk', filter=Q(status=Idea.COMPLETED)),
        drafts=Count('pk', filter=Q(status=Idea.DRAFT)),
        private=Count('pk', filter=Q(visibility=Idea.PRIVATE)),
        uncategorised=Count('pk', filter=Q(category__isnull=True)),
        new_week=Count('pk', filter=Q(created_at__gte=week_ago)),
        views=Sum('views_count'),
    )
    projects = Project.objects.aggregate(
        total=Count('pk'),
        planning=Count('pk', filter=Q(status=Project.PLANNING)),
        active=Count('pk', filter=Q(status=Project.ACTIVE)),
        completed=Count('pk', filter=Q(status=Project.COMPLETED)),
        paused=Count('pk', filter=Q(status=Project.PAUSED)),
        private=Count('pk', filter=Q(visibility=Project.PRIVATE)),
        open=Count('pk', filter=Q(is_open=True)),
        new_week=Count('pk', filter=Q(created_at__gte=week_ago)),
    )
    categories = Category.objects.aggregate(
        total=Count('pk'),
        used=Count('pk', filter=Q(ideas__isnull=False), distinct=True),
    )
    comments = Comment.objects.aggregate(
        total=Count('pk'),
        new_week=Count('pk', filter=Q(created_at__gte=week_ago)),
    )
    likes = IdeaLike.objects.aggregate(
        total=Count('pk'),
        new_week=Count('pk', filter=Q(created_at__gte=week_ago)),
    )
    favorites = Favorite.objects.aggregate(
        total=Count('pk'),
        new_week=Count('pk', filter=Q(created_at__gte=week_ago)),
    )
    members = ProjectMember.objects.aggregate(
        total=Count('pk'),
        new_week=Count('pk', filter=Q(joined_at__gte=week_ago)),
    )

    idea_list = _admin_url(Idea)
    project_list = _admin_url(Project)
    user_list = _admin_url(User)
    comment_list = _admin_url(Comment)
    category_list = _admin_url(Category)

    def group(model, title, icon, metrics, details, add_action='add'):
        add_url = (
            _admin_url(model, add_action)
            if _has_perm(user, model, 'add')
            else ''
        )
        list_url = _admin_url(model) if _has_perm(user, model) else ''
        return {
            'title': title,
            'icon': icon,
            'metrics': metrics,
            'details': details,
            'list_url': list_url,
            'add_url': add_url,
            'add_label': f'Добавить: {model._meta.verbose_name}',
        }

    groups = [
        group(
            User,
            'Аудитория',
            'bi-people',
            [
                _metric('Пользователи', users['total'], url=user_list),
                _metric(
                    'Активные',
                    users['active'],
                    hint=f"+{users['new_week']} за 7 дней",
                ),
                _metric('Администраторы', users['staff']),
                _metric('Суперпользователи', users['superusers']),
            ],
            [
                _detail('Профили', profiles['total']),
                _detail('Заполнили «о себе»', profiles['with_bio']),
                _detail('Новые за 7 дней', users['new_week']),
            ],
        ),
        group(
            Idea,
            'Идеи',
            'bi-lightbulb',
            [
                _metric('Всего идей', ideas['total'], url=idea_list),
                _metric(
                    'Опубликовано',
                    ideas['published'],
                    hint=f"+{ideas['new_week']} за 7 дней",
                ),
                _metric('В работе', ideas['in_progress']),
                _metric('Реализовано', ideas['completed']),
            ],
            [
                _detail('Черновики', ideas['drafts']),
                _detail('Приватные', ideas['private']),
                _detail('Без категории', ideas['uncategorised']),
                _detail('Просмотры', ideas['views']),
            ],
        ),
        group(
            Project,
            'Проекты',
            'bi-kanban',
            [
                _metric('Всего проектов', projects['total'], url=project_list),
                _metric(
                    'В работе',
                    projects['active'],
                    hint=f"+{projects['new_week']} за 7 дней",
                ),
                _metric('Открыты для участия', projects['open']),
                _metric('Завершено', projects['completed']),
            ],
            [
                _detail('Планирование', projects['planning']),
                _detail('На паузе', projects['paused']),
                _detail('Приватные', projects['private']),
                _detail('Участники команд', members['total']),
            ],
        ),
        group(
            Comment,
            'Сообщество',
            'bi-chat-dots',
            [
                _metric('Комментарии', comments['total'], url=comment_list),
                _metric(
                    'Лайки',
                    likes['total'],
                    hint=f"+{likes['new_week']} за 7 дней",
                ),
                _metric(
                    'В избранном',
                    favorites['total'],
                    hint=f"+{favorites['new_week']} за 7 дней",
                ),
                _metric(
                    'Категории',
                    categories['total'],
                    url=category_list,
                ),
            ],
            [
                _detail('Комментарии за 7 дней', comments['new_week']),
                _detail('Лайки за 7 дней', likes['new_week']),
                _detail('Избранное за 7 дней', favorites['new_week']),
                _detail('Категории с идеями', categories['used']),
            ],
        ),
    ]

    return {
        'groups': groups,
        'online': _online_overview(now),
        'period_start': week_ago,
        'ideas_total': ideas['total'] or 0,
        'ideas_published': ideas['published'] or 0,
        'profanity_filter_enabled': getattr(
            settings, 'PROFANITY_FILTER_ENABLED', True
        ),
    }
