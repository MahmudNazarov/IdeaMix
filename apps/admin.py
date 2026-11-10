"""Django Admin configuration for IdeaMix."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils.html import format_html

from .models import (
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

admin.site.site_header = 'IdeaMix — администрирование'
admin.site.site_title = 'IdeaMix Admin'
admin.site.index_title = 'Управление платформой'


class UserProfileInline(admin.StackedInline):
    """Profile fields are edited on the same page as the account."""

    model = UserProfile
    can_delete = False
    extra = 0
    fields = ('avatar', 'bio', 'skills', 'location', 'website', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    verbose_name = 'профиль'
    verbose_name_plural = 'профиль'


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """User list with activity counters and an inline profile."""

    list_display = (
        'username',
        'email',
        'full_name',
        'is_staff',
        'is_active',
        'ideas_total',
        'comments_total',
        'projects_total',
        'date_joined',
    )
    list_filter = BaseUserAdmin.list_filter + ('date_joined',)
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    date_hierarchy = 'date_joined'
    list_per_page = 50
    list_select_related = ('profile',)
    inlines = (UserProfileInline,)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('profile')
            .annotate(
                ideas_total_count=Count('ideas', distinct=True),
                comments_total_count=Count('comments', distinct=True),
                projects_total_count=Count('created_projects', distinct=True),
            )
        )

    @admin.display(description='Имя', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Идеи', ordering='ideas_total_count')
    def ideas_total(self, obj):
        return getattr(obj, 'ideas_total_count', obj.ideas.count())

    @admin.display(description='Комментарии', ordering='comments_total_count')
    def comments_total(self, obj):
        return getattr(obj, 'comments_total_count', obj.comments.count())

    @admin.display(description='Проекты', ordering='projects_total_count')
    def projects_total(self, obj):
        return getattr(obj, 'projects_total_count', obj.created_projects.count())


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'website', 'skills', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'bio', 'skills', 'location')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Аккаунт', {'fields': ('user',)}),
        ('О пользователе', {'fields': ('avatar', 'bio', 'skills', 'location', 'website')}),
        ('Служебное', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'ideas_total', 'projects_total', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'slug', 'description')
    ordering = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                ideas_total_count=Count('ideas', distinct=True),
                projects_total_count=Count('projects', distinct=True),
            )
        )

    @admin.display(description='Идей', ordering='ideas_total_count')
    def ideas_total(self, obj):
        return getattr(obj, 'ideas_total_count', obj.ideas.count())

    @admin.display(description='Проектов', ordering='projects_total_count')
    def projects_total(self, obj):
        return getattr(obj, 'projects_total_count', obj.projects.count())


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ('author', 'text', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('author',)
    verbose_name = 'комментарий'
    verbose_name_plural = 'комментарии'


@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'author',
        'category',
        'status_badge',
        'visibility',
        'views_count',
        'likes_total',
        'comments_total',
        'created_at',
    )
    list_filter = ('status', 'visibility', 'category', 'created_at')
    search_fields = (
        'title',
        'short_description',
        'description',
        'tags',
        'author__username',
        'author__email',
    )
    ordering = ('-created_at',)
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views_count', 'created_at', 'updated_at')
    autocomplete_fields = ('author', 'category')
    date_hierarchy = 'created_at'
    list_select_related = ('author', 'category')
    list_per_page = 25
    inlines = (CommentInline,)
    actions = ('publish_selected', 'mark_in_progress', 'mark_completed', 'mark_draft')
    fieldsets = (
        ('Основное', {'fields': ('title', 'slug', 'author', 'category', 'short_description', 'description')}),
        ('Медиа и теги', {'fields': ('cover_image', 'tags')}),
        ('Публикация', {'fields': ('status', 'visibility')}),
        ('Статистика', {'fields': ('views_count', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('author', 'category')
            .annotate(
                likes_total_count=Count('like_entries', distinct=True),
                comments_total_count=Count('comments', distinct=True),
            )
        )

    @admin.display(description='Статус', ordering='status')
    def status_badge(self, obj):
        colors = {
            Idea.DRAFT: '#6b6880',
            Idea.PUBLISHED: '#2563eb',
            Idea.IN_PROGRESS: '#d97706',
            Idea.COMPLETED: '#059669',
        }
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            'background:{};color:#fff;font-size:11px;">{}</span>',
            colors.get(obj.status, '#6b6880'),
            obj.get_status_display(),
        )

    @admin.display(description='Лайки', ordering='likes_total_count')
    def likes_total(self, obj):
        return getattr(obj, 'likes_total_count', obj.like_entries.count())

    @admin.display(description='Комментарии', ordering='comments_total_count')
    def comments_total(self, obj):
        return getattr(obj, 'comments_total_count', obj.comments.count())

    @admin.action(description='Опубликовать выбранные идеи')
    def publish_selected(self, request, queryset):
        updated = queryset.update(status=Idea.PUBLISHED)
        self.message_user(request, f'Опубликовано идей: {updated}.')

    @admin.action(description='Перевести в статус «В работе»')
    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status=Idea.IN_PROGRESS)
        self.message_user(request, f'Обновлено идей: {updated}.')

    @admin.action(description='Отметить как реализованные')
    def mark_completed(self, request, queryset):
        updated = queryset.update(status=Idea.COMPLETED)
        self.message_user(request, f'Обновлено идей: {updated}.')

    @admin.action(description='Вернуть в черновики')
    def mark_draft(self, request, queryset):
        updated = queryset.update(status=Idea.DRAFT)
        self.message_user(request, f'Перенесено в черновики: {updated}.')


@admin.register(IdeaLike)
class IdeaLikeAdmin(admin.ModelAdmin):
    list_display = ('idea', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('idea__title', 'user__username', 'user__email')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('idea', 'user')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('idea', 'user')
    list_per_page = 50


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('idea', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('idea__title', 'user__username', 'user__email')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('idea', 'user')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('idea', 'user')
    list_per_page = 50


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'idea', 'author', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('text', 'author__username', 'idea__title')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    list_select_related = ('idea', 'author')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('idea', 'author')
    list_per_page = 50

    @admin.display(description='Комментарий')
    def short_text(self, obj):
        return obj.text[:80] + ('…' if len(obj.text) > 80 else '')


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    fields = ('user', 'role', 'joined_at')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('user',)
    verbose_name = 'участник'
    verbose_name_plural = 'участники'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'creator',
        'category',
        'status_badge',
        'visibility',
        'members_total',
        'ideas_total',
        'created_at',
    )
    list_filter = ('status', 'visibility', 'is_open', 'category', 'created_at')
    search_fields = (
        'title',
        'description',
        'technologies',
        'creator__username',
        'creator__email',
    )
    ordering = ('-created_at',)
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('creator', 'category', 'related_idea')
    date_hierarchy = 'created_at'
    list_select_related = ('creator', 'category', 'related_idea')
    list_per_page = 25
    inlines = (ProjectMemberInline,)
    actions = ('activate_projects', 'complete_projects')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('creator', 'category', 'related_idea')
            .annotate(
                members_total_count=Count('memberships', distinct=True),
                ideas_total_count=Count('ideas', distinct=True),
            )
        )

    @admin.display(description='Статус', ordering='status')
    def status_badge(self, obj):
        colors = {
            Project.PLANNING: '#6b6880',
            Project.ACTIVE: '#2563eb',
            Project.COMPLETED: '#059669',
            Project.PAUSED: '#d97706',
        }
        return format_html(
            '<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
            'background:{};color:#fff;font-size:11px;">{}</span>',
            colors.get(obj.status, '#6b6880'),
            obj.get_status_display(),
        )

    @admin.display(description='Участники', ordering='members_total_count')
    def members_total(self, obj):
        return getattr(obj, 'members_total_count', obj.memberships.count())

    @admin.display(description='Идеи', ordering='ideas_total_count')
    def ideas_total(self, obj):
        return getattr(obj, 'ideas_total_count', obj.ideas.count())

    @admin.action(description='Активировать выбранные проекты')
    def activate_projects(self, request, queryset):
        updated = queryset.update(status=Project.ACTIVE)
        self.message_user(request, f'Активировано проектов: {updated}.')

    @admin.action(description='Завершить выбранные проекты')
    def complete_projects(self, request, queryset):
        updated = queryset.update(status=Project.COMPLETED)
        self.message_user(request, f'Завершено проектов: {updated}.')


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('project__title', 'user__username', 'user__email')
    ordering = ('joined_at',)
    date_hierarchy = 'joined_at'
    list_select_related = ('project', 'user')
    readonly_fields = ('joined_at',)
    autocomplete_fields = ('project', 'user')
    list_per_page = 50


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """Read-only presence log that powers the online chart."""

    list_display = (
        'user',
        'date',
        'first_seen',
        'last_seen',
        'requests',
        'duration_minutes',
    )
    list_filter = ('date',)
    search_fields = ('user__username', 'user__email')
    ordering = ('-date', '-last_seen')
    date_hierarchy = 'date'
    list_select_related = ('user',)
    readonly_fields = ('user', 'date', 'first_seen', 'last_seen', 'requests')
    list_per_page = 50

    @admin.display(description='Длительность, мин')
    def duration_minutes(self, obj):
        return obj.duration_minutes

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

