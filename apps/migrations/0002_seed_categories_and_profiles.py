"""Seed useful categories and profiles for existing users."""

from django.db import migrations
from django.utils.text import slugify


CATEGORIES = [
    ('Технологии', 'Продукты, сервисы и инженерные решения.'),
    ('Бизнес', 'Идеи для стартапов и развития компаний.'),
    ('Дизайн', 'Интерфейсы, бренды и визуальные концепции.'),
    ('Образование', 'Обучение, курсы и просветительские проекты.'),
    ('Экология', 'Устойчивое развитие и забота об окружающей среде.'),
    ('Здоровье', 'Медицина, спорт и wellbeing.'),
    ('Искусство', 'Творческие проекты, музыка и медиа.'),
    ('Сообщество', 'Городские инициативы и социальные проекты.'),
]


def seed(apps, schema_editor):
    Category = apps.get_model('apps', 'Category')
    Profile = apps.get_model('apps', 'Profile')
    User = apps.get_model('auth', 'User')

    for name, description in CATEGORIES:
        slug = slugify(name, allow_unicode=False) or 'category'
        base_slug = slug
        counter = 2
        while Category.objects.filter(slug=slug).exists():
            slug = f'{base_slug}-{counter}'
            counter += 1
        Category.objects.get_or_create(
            name=name,
            defaults={'slug': slug, 'description': description},
        )

    for user in User.objects.all():
        Profile.objects.get_or_create(user=user)


def unseed(apps, schema_editor):
    Category = apps.get_model('apps', 'Category')
    Category.objects.filter(name__in=[name for name, _ in CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('apps', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
