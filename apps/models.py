"""Database models for IdeaMix."""

from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.text import slugify

from .utils import normalize_tags, split_tags, transliterate
from .validators import (
    validate_avatar,
    validate_cover_image,
    validate_no_profanity,
)


def unique_slug(instance, value, slug_field='slug', max_length=50, fallback='item'):
    """Build a URL slug that is unique for the model instance."""
    base = slugify(transliterate(value), allow_unicode=False) or fallback
    base = base[:max_length].strip('-') or fallback
    model = instance.__class__
    candidate = base
    number = 2
    while model._default_manager.exclude(pk=instance.pk).filter(
        **{slug_field: candidate}
    ).exists():
        suffix = f'-{number}'
        candidate = f'{base[: max_length - len(suffix)].rstrip("-")}{suffix}'
        number += 1
    return candidate


class UserProfile(models.Model):
    """Public profile of a platform member."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='пользователь',
    )
    avatar = models.ImageField(
        'аватар',
        upload_to='avatars/',
        blank=True,
        null=True,
        validators=[validate_avatar],
    )
    bio = models.TextField(
        'о себе',
        max_length=500,
        blank=True,
        validators=[validate_no_profanity],
    )
    location = models.CharField(
        'город',
        max_length=100,
        blank=True,
        validators=[validate_no_profanity],
    )
    website = models.URLField('сайт', max_length=200, blank=True)
    skills = models.CharField(
        'навыки',
        max_length=255,
        blank=True,
        validators=[validate_no_profanity],
        help_text='Перечислите навыки через запятую: Python, UX, маркетинг.',
    )
    created_at = models.DateTimeField('создан', auto_now_add=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True)

    class Meta:
        verbose_name = 'профиль'
        verbose_name_plural = 'профили'

    def __str__(self):
        return f'Профиль {self.user.username}'

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def skills_list(self):
        return split_tags(self.skills)

    def get_absolute_url(self):
        return reverse('ideas:profile', args=[self.user.username])


class Category(models.Model):
    name = models.CharField(
        'название',
        max_length=80,
        unique=True,
        validators=[validate_no_profanity],
    )
    slug = models.SlugField('слаг', max_length=90, unique=True, blank=True)
    description = models.CharField(
        'описание',
        max_length=255,
        blank=True,
        validators=[validate_no_profanity],
    )
    icon = models.CharField(
        'иконка',
        max_length=50,
        default='bi-lightbulb',
        help_text='Класс Bootstrap Icons, например bi-cpu.',
    )
    created_at = models.DateTimeField('создана', auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'категория'
        verbose_name_plural = 'категории'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(
                self, self.name, max_length=90, fallback='category'
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f'{reverse("ideas:explore")}?category={self.slug}'


class IdeaQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status__in=Idea.PUBLIC_STATUSES)

    def visible_to(self, user):
        """Public ideas plus everything the viewer owns or sees via projects."""
        query = Q(visibility=Idea.PUBLIC, status__in=Idea.PUBLIC_STATUSES)
        if user is not None and user.is_authenticated:
            query |= (
                Q(author=user)
                | Q(projects__creator=user)
                | Q(projects__members=user)
            )
        return self.filter(query).distinct()

    def with_stats(self):
        return self.select_related(
            'author', 'author__profile', 'category'
        ).annotate(
            like_count=Count('like_entries', distinct=True),
            favorite_count=Count('favorite_entries', distinct=True),
            comment_count=Count('comments', distinct=True),
        )


class Idea(models.Model):
    DRAFT = 'draft'
    PUBLISHED = 'published'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'

    STATUS_CHOICES = [
        (DRAFT, 'Черновик'),
        (PUBLISHED, 'Опубликована'),
        (IN_PROGRESS, 'В работе'),
        (COMPLETED, 'Реализована'),
    ]
    PUBLIC_STATUSES = (PUBLISHED, IN_PROGRESS, COMPLETED)

    PUBLIC = 'public'
    PRIVATE = 'private'
    VISIBILITY_CHOICES = [
        (PUBLIC, 'Публичная'),
        (PRIVATE, 'Приватная'),
    ]

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ideas',
        verbose_name='автор',
    )
    title = models.CharField(
        'название',
        max_length=140,
        validators=[validate_no_profanity],
    )
    slug = models.SlugField('слаг', max_length=170, unique=True, blank=True)
    short_description = models.CharField(
        'краткое описание',
        max_length=220,
        default='',
        validators=[validate_no_profanity],
        help_text='Одно-два предложения, которые увидят в каталоге.',
    )
    description = models.TextField(
        'полное описание',
        validators=[validate_no_profanity],
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ideas',
        verbose_name='категория',
    )
    cover_image = models.ImageField(
        'обложка',
        upload_to='ideas/covers/',
        blank=True,
        null=True,
        validators=[validate_cover_image],
    )
    tags = models.CharField(
        'теги',
        max_length=200,
        blank=True,
        validators=[validate_no_profanity],
        help_text='До 5 тегов через запятую.',
    )
    status = models.CharField(
        'статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        db_index=True,
    )
    visibility = models.CharField(
        'видимость',
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default=PUBLIC,
        db_index=True,
    )
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='IdeaLike',
        related_name='liked_ideas',
        blank=True,
        verbose_name='лайки',
    )
    favorites = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Favorite',
        related_name='favorite_ideas',
        blank=True,
        verbose_name='в избранном',
    )
    views_count = models.PositiveIntegerField('просмотры', default=0)
    created_at = models.DateTimeField('создана', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('обновлена', auto_now=True)

    objects = IdeaQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'идея'
        verbose_name_plural = 'идеи'
        indexes = [
            models.Index(fields=['visibility', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', '-created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.tags = normalize_tags(self.tags)
        if not self.slug:
            self.slug = unique_slug(
                self, self.title, max_length=160, fallback='idea'
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ideas:idea_detail', args=[self.slug])

    @property
    def tags_list(self):
        return split_tags(self.tags)

    @property
    def is_private(self):
        return self.visibility == self.PRIVATE

    @property
    def is_draft(self):
        return self.status == self.DRAFT

    @property
    def is_publicly_visible(self):
        return self.visibility == self.PUBLIC and self.status in self.PUBLIC_STATUSES

    def can_view(self, user):
        if user is not None and user.is_authenticated and self.author_id == user.pk:
            return True
        if self.status == self.DRAFT:
            return False
        if self.visibility == self.PUBLIC:
            return True
        if user is None or not user.is_authenticated:
            return False
        return self.projects.filter(
            Q(creator=user) | Q(members=user)
        ).exists()

    def can_edit(self, user):
        return bool(
            user and user.is_authenticated and self.author_id == user.pk
        )

    can_delete = can_edit


class IdeaLike(models.Model):
    idea = models.ForeignKey(
        Idea, on_delete=models.CASCADE, related_name='like_entries'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='idea_likes',
    )
    created_at = models.DateTimeField('поставлен', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['idea', 'user'], name='unique_like_per_user'
            )
        ]
        ordering = ['-created_at']
        verbose_name = 'лайк'
        verbose_name_plural = 'лайки'

    def __str__(self):
        return f'{self.user} ♥ {self.idea}'


class Favorite(models.Model):
    idea = models.ForeignKey(
        Idea, on_delete=models.CASCADE, related_name='favorite_entries'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='idea_favorites',
    )
    created_at = models.DateTimeField('добавлено', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['idea', 'user'], name='unique_favorite_per_user'
            )
        ]
        ordering = ['-created_at']
        verbose_name = 'избранное'
        verbose_name_plural = 'избранное'

    def __str__(self):
        return f'{self.user} → {self.idea}'


class Comment(models.Model):
    idea = models.ForeignKey(
        Idea, on_delete=models.CASCADE, related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    text = models.TextField(
        'комментарий',
        max_length=1000,
        validators=[validate_no_profanity],
    )
    created_at = models.DateTimeField('написан', auto_now_add=True)
    updated_at = models.DateTimeField('изменён', auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'комментарий'
        verbose_name_plural = 'комментарии'

    def __str__(self):
        return f'Комментарий {self.author} к {self.idea}'

    @property
    def was_edited(self):
        if not self.updated_at or not self.created_at:
            return False
        return (self.updated_at - self.created_at).total_seconds() > 2

    def can_edit(self, user):
        return bool(
            user and user.is_authenticated and self.author_id == user.pk
        )


class ProjectQuerySet(models.QuerySet):
    def visible_to(self, user):
        query = Q(visibility=Project.PUBLIC)
        if user is not None and user.is_authenticated:
            query |= Q(creator=user) | Q(members=user)
        return self.filter(query).distinct()

    def with_stats(self):
        return self.select_related(
            'creator', 'creator__profile', 'category', 'related_idea'
        ).annotate(
            member_count=Count('memberships', distinct=True),
            idea_count=Count('ideas', distinct=True),
        )


class Project(models.Model):
    PLANNING = 'planning'
    ACTIVE = 'active'
    COMPLETED = 'completed'
    PAUSED = 'paused'

    STATUS_CHOICES = [
        (PLANNING, 'Планирование'),
        (ACTIVE, 'В работе'),
        (COMPLETED, 'Завершён'),
        (PAUSED, 'На паузе'),
    ]

    PUBLIC = 'public'
    PRIVATE = 'private'
    VISIBILITY_CHOICES = [
        (PUBLIC, 'Публичный'),
        (PRIVATE, 'Приватный'),
    ]

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_projects',
        verbose_name='создатель',
    )
    title = models.CharField(
        'название',
        max_length=140,
        validators=[validate_no_profanity],
    )
    slug = models.SlugField('слаг', max_length=170, unique=True, blank=True)
    description = models.TextField(
        'описание',
        validators=[validate_no_profanity],
    )
    related_idea = models.ForeignKey(
        Idea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_projects',
        verbose_name='связанная идея',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects',
        verbose_name='категория',
    )
    status = models.CharField(
        'статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=PLANNING,
        db_index=True,
    )
    technologies = models.CharField(
        'технологии',
        max_length=255,
        blank=True,
        validators=[validate_no_profanity],
        help_text='Например: Python, Django, PostgreSQL.',
    )
    needed_specialists = models.CharField(
        'нужные специалисты',
        max_length=255,
        blank=True,
        validators=[validate_no_profanity],
        help_text='Кого вы ищете: разработчик, дизайнер, исследователь.',
    )
    repository_url = models.URLField('репозиторий', max_length=300, blank=True)
    demo_url = models.URLField('демо', max_length=300, blank=True)
    visibility = models.CharField(
        'видимость',
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default=PUBLIC,
        db_index=True,
    )
    is_open = models.BooleanField(
        'открыт для участников',
        default=True,
        help_text='Разрешить другим пользователям присоединяться к команде.',
    )
    ideas = models.ManyToManyField(
        Idea, related_name='projects', blank=True, verbose_name='идеи'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='ProjectMember',
        related_name='projects',
        blank=True,
        verbose_name='участники',
    )
    created_at = models.DateTimeField('создан', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('обновлён', auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'проект'
        verbose_name_plural = 'проекты'
        indexes = [
            models.Index(fields=['visibility', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(
                self, self.title, max_length=160, fallback='project'
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('ideas:project_detail', args=[self.slug])

    @property
    def technologies_list(self):
        return split_tags(self.technologies)

    @property
    def needed_specialists_list(self):
        return split_tags(self.needed_specialists)

    @property
    def is_private(self):
        return self.visibility == self.PRIVATE

    def is_member(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.creator_id == user.pk:
            return True
        return self.memberships.filter(user_id=user.pk).exists()

    def can_view(self, user):
        if self.visibility == self.PUBLIC:
            return True
        return self.is_member(user)

    def can_manage(self, user):
        return bool(
            user and user.is_authenticated and self.creator_id == user.pk
        )

    def can_join(self, user):
        return bool(
            user
            and user.is_authenticated
            and self.visibility == self.PUBLIC
            and self.is_open
            and not self.is_member(user)
        )


class ProjectMember(models.Model):
    OWNER = 'owner'
    DEVELOPER = 'developer'
    DESIGNER = 'designer'
    RESEARCHER = 'researcher'
    OTHER = 'other'

    ROLE_CHOICES = [
        (OWNER, 'Владелец'),
        (DEVELOPER, 'Разработчик'),
        (DESIGNER, 'Дизайнер'),
        (RESEARCHER, 'Исследователь'),
        (OTHER, 'Другой специалист'),
    ]
    JOINABLE_ROLES = [
        (DEVELOPER, 'Разработчик'),
        (DESIGNER, 'Дизайнер'),
        (RESEARCHER, 'Исследователь'),
        (OTHER, 'Другой специалист'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_memberships',
    )
    role = models.CharField(
        'роль',
        max_length=20,
        choices=ROLE_CHOICES,
        default=DEVELOPER,
    )
    joined_at = models.DateTimeField('присоединился', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'user'], name='unique_project_member'
            )
        ]
        ordering = ['joined_at']
        indexes = [
            models.Index(fields=['project', 'role']),
        ]
        verbose_name = 'участник проекта'
        verbose_name_plural = 'участники проекта'

    def __str__(self):
        return f'{self.user} в {self.project}'


class UserActivity(models.Model):
    """Daily presence of a user on the site.

    One row per user per calendar day keeps the online chart cheap to build:
    the dashboard only needs seven indexed lookups instead of scanning every
    request.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_days',
        verbose_name='пользователь',
    )
    date = models.DateField('дата', db_index=True)
    first_seen = models.DateTimeField('первый визит')
    last_seen = models.DateTimeField('последний визит')
    requests = models.PositiveIntegerField('запросов', default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'], name='unique_user_activity_per_day'
            )
        ]
        ordering = ['-date', '-last_seen']
        verbose_name = 'активность пользователя'
        verbose_name_plural = 'активность пользователей'

    def __str__(self):
        return f'{self.user} · {self.date:%d.%m.%Y}'

    @property
    def duration_minutes(self):
        if not self.first_seen or not self.last_seen:
            return 0
        return max(0, int((self.last_seen - self.first_seen).total_seconds() // 60))
