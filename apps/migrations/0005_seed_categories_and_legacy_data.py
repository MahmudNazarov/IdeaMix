"""Populate categories and adapt legacy rows to the extended schema."""

from django.db import migrations


CATEGORY_META = [
    ('Технологии', 'technology', 'bi-cpu', 'Продукты, сервисы и инженерные решения.'),
    ('ИИ и машинное обучение', 'ai-ml', 'bi-stars', 'Интеллектуальные системы и ML-продукты.'),
    ('Бизнес', 'business', 'bi-briefcase', 'Стартапы, рынки и новые модели работы.'),
    ('Образование', 'education', 'bi-mortarboard', 'Обучение, курсы и просветительские проекты.'),
    ('Дизайн', 'design', 'bi-palette', 'Интерфейсы, бренды и визуальные концепции.'),
    ('Здоровье', 'health', 'bi-heart-pulse', 'Медицина, спорт и забота о себе.'),
    ('Экология', 'environment', 'bi-tree', 'Устойчивое развитие и окружающая среда.'),
    ('Продуктивность', 'productivity', 'bi-lightning-charge', 'Инструменты и подходы для эффективной работы.'),
    ('Игры', 'gaming', 'bi-controller', 'Игровые механики, сообщества и интерактивные миры.'),
    ('Другое', 'other', 'bi-grid', 'Идеи, которым пока не нашлось категории.'),
]

EXTRA_CATEGORY_META = [
    ('Искусство', 'art', 'bi-brush', 'Творческие проекты, музыка и медиа.'),
    ('Сообщество', 'community', 'bi-people', 'Городские инициативы и социальные проекты.'),
]


def seed(apps, schema_editor):
    Category = apps.get_model('apps', 'Category')
    Idea = apps.get_model('apps', 'Idea')
    ProjectMember = apps.get_model('apps', 'ProjectMember')
    UserProfile = apps.get_model('apps', 'UserProfile')
    User = apps.get_model('auth', 'User')

    for name, slug, icon, description in CATEGORY_META + EXTRA_CATEGORY_META:
        category = Category.objects.filter(name=name).first()
        if category is None:
            category = Category.objects.filter(slug=slug).first()
        if category is None:
            Category.objects.create(
                name=name,
                slug=slug,
                icon=icon,
                description=description,
            )
            continue
        category.name = name
        category.slug = slug
        category.icon = icon
        if not category.description:
            category.description = description
        category.save()

    for idea in Idea.objects.all():
        description = (idea.description or '').strip()
        short = description[:217] + ('…' if len(description) > 217 else '')
        idea.short_description = short or idea.title
        # Existing ideas were already visible before the status field appeared.
        idea.status = 'published'
        idea.save(update_fields=['short_description', 'status'])

    ProjectMember.objects.filter(role='member').update(role='developer')

    for user in User.objects.all():
        UserProfile.objects.get_or_create(user=user)


def unseed(apps, schema_editor):
    """Keep data intact when rolling back."""


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0004_alter_favorite_options_alter_idealike_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
