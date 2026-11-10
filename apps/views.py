"""Views for IdeaMix."""

from collections import Counter

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    AddMemberForm,
    CommentForm,
    IdeaAttachForm,
    IdeaForm,
    JoinProjectForm,
    LoginForm,
    ProfileForm,
    ProjectForm,
    RegisterForm,
)
from .models import (
    Category,
    Comment,
    Favorite,
    Idea,
    IdeaLike,
    Project,
    ProjectMember,
    UserProfile,
)
from .utils import split_tags

PAGE_SIZE = 9
CATALOG_PAGE_SIZE = 9


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paginate(request, queryset, per_page=PAGE_SIZE):
    return Paginator(queryset, per_page).get_page(request.GET.get('page'))


def _visible_idea_or_404(request, slug):
    idea = get_object_or_404(Idea.objects.with_stats(), slug=slug)
    if not idea.can_view(request.user):
        raise Http404('Идея не найдена')
    return idea


def _wants_json(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return True
    return 'application/json' in request.headers.get('accept', '')


def _login_url(request):
    return f'{reverse("ideas:login")}?next={request.get_full_path()}'


def _login_redirect(request):
    return redirect(_login_url(request))


def _safe_next(request, candidate):
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def _categories_with_counts():
    return Category.objects.annotate(
        idea_count=Count(
            'ideas',
            filter=Q(
                ideas__visibility=Idea.PUBLIC,
                ideas__status__in=Idea.PUBLIC_STATUSES,
            ),
            distinct=True,
        )
    )


def _published_ideas(user):
    return (
        Idea.objects.visible_to(user)
        .filter(status__in=Idea.PUBLIC_STATUSES)
        .with_stats()
    )


def _popular_tags(user, limit=14):
    rows = (
        Idea.objects.visible_to(user)
        .filter(status__in=Idea.PUBLIC_STATUSES)
        .values_list('tags', flat=True)
    )
    counter = Counter()
    for row in rows:
        for tag in split_tags(row):
            counter[tag] += 1
    return [{'name': name, 'count': count} for name, count in counter.most_common(limit)]


def _idea_status_choices():
    return Idea.STATUS_CHOICES


def _apply_idea_filters(request, queryset):
    """Apply GET filters and return a (queryset, filters) tuple."""
    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
            | Q(author__username__icontains=query)
            | Q(category__name__icontains=query)
        )

    category_slug = request.GET.get('category', '').strip()
    category = None
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category:
            queryset = queryset.filter(category=category)

    status = request.GET.get('status', '').strip()
    valid_statuses = {value for value, _ in Idea.STATUS_CHOICES}
    if status not in valid_statuses or status == Idea.DRAFT:
        status = ''

    tag = request.GET.get('tag', '').strip().lower()
    if tag:
        queryset = queryset.filter(tags__icontains=tag)

    sort = request.GET.get('sort', 'new')
    sort_map = {
        'new': ('-created_at', '-pk'),
        'old': ('created_at', 'pk'),
        'popular': ('-like_count', '-created_at', '-pk'),
        'views': ('-views_count', '-created_at', '-pk'),
    }
    if sort not in sort_map:
        sort = 'new'
    queryset = queryset.order_by(*sort_map[sort])

    filters = {
        'q': query,
        'category': category,
        'category_slug': category_slug,
        'status': status,
        'tag': tag,
        'sort': sort,
    }
    return queryset, filters


def _catalog_context(request, queryset, template, title, subtitle):
    # The caller passes an already annotated queryset.
    queryset, filters = _apply_idea_filters(request, queryset)
    page_obj = _paginate(request, queryset, CATALOG_PAGE_SIZE)
    context = {
        'page_obj': page_obj,
        'filters': filters,
        'categories': _categories_with_counts(),
        'popular_tags': _popular_tags(request.user),
        'total_count': page_obj.paginator.count,
        'page_title': title,
        'page_subtitle': subtitle,
        'status_choices': [
            choice for choice in Idea.STATUS_CHOICES if choice[0] != Idea.DRAFT
        ],
    }
    return context


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------


def home(request):
    published = _published_ideas(request.user)
    total_ideas = published.count()
    popular = published.order_by('-like_count', '-views_count', '-created_at')[:6]
    recent = published.order_by('-created_at', '-pk')[:6]
    projects = (
        Project.objects.visible_to(request.user)
        .with_stats()
        .order_by('-created_at', '-pk')[:3]
    )
    categories = _categories_with_counts().order_by('-idea_count', 'name')[:8]

    public_ideas = Idea.objects.filter(
        visibility=Idea.PUBLIC, status__in=Idea.PUBLIC_STATUSES
    )
    stats = {
        'ideas': public_ideas.count(),
        'users': User.objects.filter(is_active=True).count(),
        'projects': Project.objects.filter(visibility=Project.PUBLIC).count(),
        'likes': IdeaLike.objects.filter(idea__in=public_ideas).count(),
        'comments': Comment.objects.filter(idea__in=public_ideas).count(),
    }

    context = {
        'popular_ideas': popular,
        'recent_ideas': recent,
        'projects': projects,
        'categories': categories,
        'stats': stats,
        'total_ideas': total_ideas,
        'has_ideas': total_ideas > 0,
    }
    return render(request, 'pages/home.html', context)


def about(request):
    public_ideas = Idea.objects.filter(
        visibility=Idea.PUBLIC, status__in=Idea.PUBLIC_STATUSES
    )
    stats = {
        'ideas': public_ideas.count(),
        'users': User.objects.filter(is_active=True).count(),
        'projects': Project.objects.filter(visibility=Project.PUBLIC).count(),
        'likes': IdeaLike.objects.filter(idea__in=public_ideas).count(),
    }
    return render(request, 'pages/about.html', {'stats': stats})


def explore(request):
    queryset = _published_ideas(request.user)
    context = _catalog_context(
        request,
        queryset,
        'pages/explore.html',
        'Исследуйте идеи',
        'Найдите вдохновение, единомышленников и следующий большой проект.',
    )
    return render(request, 'pages/explore.html', context)


def search(request):
    query = request.GET.get('q', '').strip()
    queryset = _published_ideas(request.user).none()
    if query:
        queryset = _published_ideas(request.user).filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(tags__icontains=query)
            | Q(author__username__icontains=query)
            | Q(category__name__icontains=query)
        )
    queryset = queryset.order_by('-created_at', '-pk')
    page_obj = _paginate(request, queryset, CATALOG_PAGE_SIZE)
    context = {
        'query': query,
        'page_obj': page_obj,
        'total_count': page_obj.paginator.count,
        'categories': _categories_with_counts(),
        'popular_tags': _popular_tags(request.user),
    }
    return render(request, 'pages/search.html', context)


def idea_detail(request, slug):
    idea = _visible_idea_or_404(request, slug)
    comment_form = CommentForm()

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return _login_redirect(request)
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.idea = idea
            comment.author = request.user
            comment.save()
            messages.success(request, 'Комментарий добавлен.')
            return redirect(f'{idea.get_absolute_url()}#comment-{comment.pk}')
        messages.error(request, 'Исправьте ошибки в комментарии.')

    if request.method == 'GET':
        seen_key = f'idea_seen_{idea.pk}'
        if not request.session.get(seen_key):
            Idea.objects.filter(pk=idea.pk).update(views_count=F('views_count') + 1)
            request.session[seen_key] = True
            idea.views_count += 1

    comments = idea.comments.select_related('author', 'author__profile')

    liked = (
        request.user.is_authenticated
        and IdeaLike.objects.filter(idea=idea, user=request.user).exists()
    )
    favorited = (
        request.user.is_authenticated
        and Favorite.objects.filter(idea=idea, user=request.user).exists()
    )

    related_ideas = (
        _published_ideas(request.user)
        .exclude(pk=idea.pk)
        .filter(category=idea.category)
        .order_by('-like_count', '-created_at')[:3]
        if idea.category
        else Idea.objects.none()
    )

    related_projects = (
        Project.objects.visible_to(request.user)
        .filter(Q(related_idea=idea) | Q(ideas=idea))
        .with_stats()
        .distinct()
        .order_by('-created_at')[:3]
    )

    context = {
        'idea': idea,
        'comments': comments,
        'comment_form': comment_form,
        'liked': liked,
        'favorited': favorited,
        'can_edit': idea.can_edit(request.user),
        'related_ideas': related_ideas,
        'related_projects': related_projects,
    }
    return render(request, 'ideas/idea_detail.html', context)


# ---------------------------------------------------------------------------
# Idea CRUD
# ---------------------------------------------------------------------------


@login_required
def idea_create(request):
    form = IdeaForm(
        request.POST or None,
        request.FILES or None,
        initial={'status': Idea.PUBLISHED},
    )
    if request.method == 'POST' and form.is_valid():
        idea = form.save(commit=False)
        idea.author = request.user
        idea.save()
        if idea.status == Idea.DRAFT:
            messages.success(
                request, 'Черновик сохранён. Он виден только вам в разделе «Мои идеи».'
            )
        else:
            messages.success(request, 'Идея опубликована. Делитесь ею с сообществом!')
        return redirect(idea)
    return render(
        request,
        'ideas/idea_create.html',
        {'form': form, 'page_title': 'Новая идея'},
    )


@login_required
def idea_edit(request, slug):
    idea = _visible_idea_or_404(request, slug)
    if not idea.can_edit(request.user):
        raise PermissionDenied('Можно редактировать только свои идеи.')

    form = IdeaForm(
        request.POST or None,
        request.FILES or None,
        instance=idea,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Изменения сохранены.')
        return redirect(idea)
    return render(
        request,
        'ideas/idea_edit.html',
        {'form': form, 'idea': idea, 'page_title': 'Редактировать идею'},
    )


@login_required
def idea_delete(request, slug):
    idea = _visible_idea_or_404(request, slug)
    if not idea.can_edit(request.user):
        raise PermissionDenied('Можно удалять только свои идеи.')

    if request.method == 'POST':
        title = idea.title
        if idea.cover_image:
            idea.cover_image.delete(save=False)
        idea.delete()
        messages.success(request, f'Идея «{title}» удалена.')
        return redirect('ideas:my_ideas')
    return render(request, 'ideas/idea_delete.html', {'idea': idea})


@require_POST
def idea_like(request, slug):
    idea = _visible_idea_or_404(request, slug)
    if not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse(
                {
                    'detail': 'Требуется вход',
                    'login_url': _login_url(request),
                },
                status=401,
            )
        return _login_redirect(request)

    like, created = IdeaLike.objects.get_or_create(
        idea=idea, user=request.user
    )
    if not created:
        like.delete()

    count = IdeaLike.objects.filter(idea=idea).count()
    if _wants_json(request):
        return JsonResponse({'active': created, 'count': count})

    if created:
        messages.success(request, 'Спасибо! Лайк добавлен.')
    else:
        messages.info(request, 'Лайк убран.')
    return redirect(f'{idea.get_absolute_url()}#reactions')


@require_POST
def idea_favorite(request, slug):
    idea = _visible_idea_or_404(request, slug)
    if not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse(
                {
                    'detail': 'Требуется вход',
                    'login_url': _login_url(request),
                },
                status=401,
            )
        return _login_redirect(request)

    favorite, created = Favorite.objects.get_or_create(
        idea=idea, user=request.user
    )
    if not created:
        favorite.delete()

    count = Favorite.objects.filter(idea=idea).count()
    if _wants_json(request):
        return JsonResponse({'active': created, 'count': count})

    messages.success(
        request,
        'Идея добавлена в избранное.' if created else 'Идея убрана из избранного.',
    )
    return redirect(f'{idea.get_absolute_url()}#reactions')


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@login_required
def comment_edit(request, pk):
    comment = get_object_or_404(
        Comment.objects.select_related('idea', 'author'), pk=pk
    )
    if not comment.idea.can_view(request.user):
        raise Http404('Комментарий не найден')
    if not comment.can_edit(request.user):
        raise PermissionDenied('Можно редактировать только свои комментарии.')

    form = CommentForm(request.POST or None, instance=comment)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Комментарий обновлён.')
        return redirect(f'{comment.idea.get_absolute_url()}#comment-{comment.pk}')

    return render(
        request,
        'ideas/comment_edit.html',
        {'form': form, 'comment': comment, 'idea': comment.idea},
    )


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(
        Comment.objects.select_related('idea', 'author'), pk=pk
    )
    if not comment.idea.can_view(request.user):
        raise Http404('Комментарий не найден')
    if not comment.can_edit(request.user):
        raise PermissionDenied('Можно удалять только свои комментарии.')

    idea = comment.idea
    comment.delete()
    messages.success(request, 'Комментарий удалён.')
    return redirect(f'{idea.get_absolute_url()}#comments')


# ---------------------------------------------------------------------------
# Authentication and profile
# ---------------------------------------------------------------------------


def register(request):
    if request.user.is_authenticated:
        return redirect('ideas:home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        messages.success(
            request,
            f'Добро пожаловать в IdeaMix, {user.username}! Профиль уже готов.',
        )
        return redirect('ideas:home')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('ideas:home')
    form = LoginForm(request, data=request.POST or None)
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        messages.success(request, 'Вы вошли в аккаунт.')
        target = _safe_next(request, next_url)
        return redirect(target or 'ideas:home')
    return render(
        request,
        'accounts/login.html',
        {'form': form, 'next': next_url},
    )


@require_POST
def logout_view(request):
    auth_logout(request)
    messages.info(request, 'Вы вышли из аккаунта. Возвращайтесь с новыми идеями!')
    return redirect('ideas:home')


@login_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Пароль обновлён.')
        return redirect('ideas:profile_edit')
    return render(
        request,
        'accounts/password_change.html',
        {'form': form, 'page_title': 'Смена пароля'},
    )


def profile(request, username):
    profile_user = get_object_or_404(User.objects.select_related('profile'), username=username)
    profile_obj, _ = UserProfile.objects.get_or_create(user=profile_user)
    is_self = request.user.is_authenticated and request.user.pk == profile_user.pk

    if is_self:
        ideas = Idea.objects.filter(author=profile_user).with_stats()
        projects = Project.objects.filter(creator=profile_user).with_stats()
    else:
        ideas = _published_ideas(request.user).filter(author=profile_user)
        projects = (
            Project.objects.visible_to(request.user)
            .filter(creator=profile_user)
            .with_stats()
        )

    ideas = ideas.order_by('-created_at', '-pk')
    projects = projects.order_by('-created_at', '-pk')

    membership_project_ids = ProjectMember.objects.filter(
        user=profile_user
    ).values_list('project_id', flat=True)
    teams = (
        Project.objects.visible_to(request.user)
        .filter(pk__in=membership_project_ids)
        .with_stats()
        .order_by('-created_at')
    )

    favorites_qs = (
        Idea.objects.visible_to(request.user)
        .filter(favorites=profile_user)
        .with_stats()
        .order_by('-favorite_entries__created_at')
        if is_self
        else Idea.objects.none()
    )

    tab = request.GET.get('tab', 'ideas')
    allowed_tabs = {'ideas', 'projects', 'teams'}
    if is_self:
        allowed_tabs.add('favorites')
    if tab not in allowed_tabs:
        tab = 'ideas'

    counts = {
        'ideas': ideas.count(),
        'projects': projects.count(),
        'teams': teams.count(),
        'favorites': favorites_qs.count() if is_self else 0,
    }

    public_ideas = Idea.objects.filter(
        author=profile_user,
        visibility=Idea.PUBLIC,
        status__in=Idea.PUBLIC_STATUSES,
    )
    public_projects = Project.objects.filter(
        creator=profile_user, visibility=Project.PUBLIC
    )
    stats = {
        'ideas': public_ideas.count(),
        'projects': public_projects.count(),
        'likes': IdeaLike.objects.filter(idea__in=public_ideas).count(),
        'views': public_ideas.aggregate(total=Sum('views_count'))['total'] or 0,
        'teams': Project.objects.filter(
            pk__in=membership_project_ids, visibility=Project.PUBLIC
        ).count(),
    }

    context = {
        'profile_user': profile_user,
        'profile': profile_obj,
        'is_self': is_self,
        'ideas': ideas[:6],
        'projects': projects[:6],
        'teams': teams[:6],
        'favorites': favorites_qs[:6] if is_self else [],
        'tab': tab,
        'stats': stats,
        'counts': counts,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(
        request.POST or None, request.FILES or None, instance=profile_obj
    )
    if request.method == 'POST' and form.is_valid():
        old_avatar = None
        if profile_obj.avatar:
            old_avatar = profile_obj.avatar
        profile = form.save()
        if old_avatar and old_avatar.name != profile.avatar.name:
            old_avatar.delete(save=False)
        messages.success(request, 'Профиль обновлён.')
        return redirect(profile_obj)
    return render(
        request,
        'accounts/profile_edit.html',
        {'form': form, 'profile': profile_obj, 'page_title': 'Настройки профиля'},
    )


@login_required
def my_ideas(request):
    status = request.GET.get('status', '')
    valid = {value for value, _ in Idea.STATUS_CHOICES}
    ideas = Idea.objects.filter(author=request.user).with_stats()
    if status in valid:
        ideas = ideas.filter(status=status)
    else:
        status = ''
    ideas = ideas.order_by('-created_at', '-pk')

    counts = {
        value: Idea.objects.filter(author=request.user, status=value).count()
        for value, _ in Idea.STATUS_CHOICES
    }
    status_tabs = [
        {'value': value, 'label': label, 'count': counts[value]}
        for value, label in Idea.STATUS_CHOICES
    ]
    return render(
        request,
        'ideas/my_ideas.html',
        {
            'page_obj': _paginate(request, ideas),
            'active_status': status,
            'status_choices': Idea.STATUS_CHOICES,
            'status_tabs': status_tabs,
            'counts': counts,
            'total_count': sum(counts.values()),
        },
    )


@login_required
def favorites(request):
    ideas = (
        Idea.objects.visible_to(request.user)
        .filter(favorites=request.user)
        .with_stats()
        .order_by('-favorite_entries__created_at')
    )
    return render(
        request,
        'ideas/favorites.html',
        {'page_obj': _paginate(request, ideas)},
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def project_list(request):
    queryset = Project.objects.visible_to(request.user).with_stats()

    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(technologies__icontains=query)
            | Q(needed_specialists__icontains=query)
            | Q(creator__username__icontains=query)
        )

    category_slug = request.GET.get('category', '').strip()
    category = None
    if category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category:
            queryset = queryset.filter(category=category)

    status = request.GET.get('status', '').strip()
    valid_statuses = {value for value, _ in Project.STATUS_CHOICES}
    if status not in valid_statuses:
        status = ''

    sort = request.GET.get('sort', 'new')
    sort_map = {
        'new': ('-created_at', '-pk'),
        'old': ('created_at', 'pk'),
        'members': ('-member_count', '-created_at'),
    }
    if sort not in sort_map:
        sort = 'new'
    queryset = queryset.order_by(*sort_map[sort])

    page_obj = _paginate(request, queryset, CATALOG_PAGE_SIZE)
    context = {
        'page_obj': page_obj,
        'total_count': page_obj.paginator.count,
        'categories': _categories_with_counts(),
        'status_choices': Project.STATUS_CHOICES,
        'filters': {
            'q': query,
            'category': category,
            'category_slug': category_slug,
            'status': status,
            'sort': sort,
        },
    }
    return render(request, 'projects/project_list.html', context)


def project_detail(request, slug):
    project = get_object_or_404(Project.objects.with_stats(), slug=slug)
    if not project.can_view(request.user):
        raise Http404('Проект не найден')

    ideas = project.ideas.with_stats()
    if not project.is_member(request.user):
        ideas = ideas.filter(
            visibility=Idea.PUBLIC, status__in=Idea.PUBLIC_STATUSES
        )
    ideas = ideas.order_by('-created_at')

    is_manager = project.can_manage(request.user)
    memberships = project.memberships.select_related(
        'user', 'user__profile'
    )

    related_idea_visible = bool(
        project.related_idea and project.related_idea.can_view(request.user)
    )

    context = {
        'project': project,
        'ideas': ideas,
        'memberships': memberships,
        'is_manager': is_manager,
        'is_member': project.is_member(request.user),
        'can_join': project.can_join(request.user),
        'member_form': AddMemberForm(project=project) if is_manager else None,
        'attach_form': (
            IdeaAttachForm(project=project, user=request.user)
            if is_manager
            else None
        ),
        'join_form': JoinProjectForm() if project.can_join(request.user) else None,
        'role_choices': ProjectMember.JOINABLE_ROLES,
        'related_idea_visible': related_idea_visible,
    }
    return render(request, 'projects/project_detail.html', context)


@login_required
def project_create(request):
    initial = {}
    idea_id = request.GET.get('idea')
    if idea_id:
        related = Idea.objects.filter(pk=idea_id, author=request.user).first()
        if related:
            initial['related_idea'] = related
    form = ProjectForm(
        request.POST or None, user=request.user, initial=initial
    )
    if request.method == 'POST' and form.is_valid():
        project = form.save(commit=False)
        project.creator = request.user
        project.save()
        ProjectMember.objects.get_or_create(
            project=project,
            user=request.user,
            defaults={'role': ProjectMember.OWNER},
        )
        if project.related_idea_id:
            project.ideas.add(project.related_idea)
        messages.success(request, 'Проект создан. Теперь можно собирать команду!')
        return redirect(project)
    return render(
        request,
        'projects/project_create.html',
        {'form': form, 'page_title': 'Новый проект'},
    )


@login_required
def project_edit(request, slug):
    project = get_object_or_404(Project.objects.with_stats(), slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Управлять проектом может только создатель.')

    form = ProjectForm(
        request.POST or None, instance=project, user=request.user
    )
    if request.method == 'POST' and form.is_valid():
        project = form.save()
        if project.related_idea_id:
            project.ideas.add(project.related_idea)
        messages.success(request, 'Проект обновлён.')
        return redirect(project)
    return render(
        request,
        'projects/project_edit.html',
        {'form': form, 'project': project, 'page_title': 'Редактировать проект'},
    )


@login_required
def project_delete(request, slug):
    project = get_object_or_404(Project.objects.with_stats(), slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Удалить проект может только создатель.')

    if request.method == 'POST':
        title = project.title
        project.delete()
        messages.success(request, f'Проект «{title}» удалён.')
        return redirect('ideas:project_list')
    return render(
        request,
        'projects/project_delete.html',
        {'project': project},
    )


@login_required
@require_POST
def project_join(request, slug):
    project = get_object_or_404(Project.objects.with_stats(), slug=slug)
    if not project.can_view(request.user):
        raise Http404('Проект не найден')
    if project.is_member(request.user):
        messages.info(request, 'Вы уже участвуете в этом проекте.')
        return redirect(project)
    if not project.is_open:
        messages.error(request, 'Проект сейчас не принимает новых участников.')
        return redirect(project)

    form = JoinProjectForm(request.POST)
    if form.is_valid():
        ProjectMember.objects.get_or_create(
            project=project,
            user=request.user,
            defaults={'role': form.cleaned_data['role']},
        )
        messages.success(request, 'Вы присоединились к команде проекта.')
    else:
        messages.error(request, 'Не удалось определить роль в команде.')
    return redirect(project)


@login_required
@require_POST
def project_leave(request, slug):
    project = get_object_or_404(Project.objects.with_stats(), slug=slug)
    if project.creator_id == request.user.pk:
        messages.error(request, 'Создатель не может покинуть собственный проект.')
        return redirect(project)
    membership = project.memberships.filter(user=request.user).first()
    if not membership:
        messages.info(request, 'Вы не участвуете в этом проекте.')
        return redirect(project)
    membership.delete()
    messages.success(request, 'Вы покинули команду проекта.')
    return redirect(project)


@login_required
@require_POST
def project_member_add(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Добавлять участников может только создатель.')

    form = AddMemberForm(request.POST, project=project)
    if form.is_valid():
        ProjectMember.objects.create(
            project=project,
            user=form.cleaned_user,
            role=form.cleaned_data['role'],
        )
        messages.success(
            request, f'{form.cleaned_user.username} добавлен в проект.'
        )
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(project)


@login_required
@require_POST
def project_member_remove(request, slug, user_id):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Удалять участников может только создатель.')
    if project.creator_id == user_id:
        messages.error(request, 'Нельзя удалить создателя проекта.')
        return redirect(project)

    membership = project.memberships.filter(user_id=user_id).first()
    if membership:
        membership.delete()
        messages.success(request, 'Участник удалён из проекта.')
    else:
        messages.error(request, 'Участник не найден.')
    return redirect(project)


@login_required
@require_POST
def project_member_role(request, slug, user_id):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Менять роли может только создатель.')
    if project.creator_id == user_id:
        messages.error(request, 'Роль создателя изменить нельзя.')
        return redirect(project)

    membership = project.memberships.filter(user_id=user_id).first()
    valid_roles = {value for value, _ in ProjectMember.JOINABLE_ROLES}
    role = request.POST.get('role', '')
    if not membership:
        messages.error(request, 'Участник не найден.')
    elif role not in valid_roles:
        messages.error(request, 'Некорректная роль.')
    else:
        membership.role = role
        membership.save(update_fields=['role'])
        messages.success(request, 'Роль участника обновлена.')
    return redirect(project)


@login_required
@require_POST
def project_idea_add(request, slug):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Добавлять идеи может только создатель.')

    form = IdeaAttachForm(request.POST, project=project, user=request.user)
    if form.is_valid():
        project.ideas.add(form.cleaned_data['idea'])
        messages.success(request, 'Идея добавлена в проект.')
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(project)


@login_required
@require_POST
def project_idea_remove(request, slug, idea_id):
    project = get_object_or_404(Project, slug=slug)
    if not project.can_manage(request.user):
        raise PermissionDenied('Убирать идеи может только создатель.')

    idea = project.ideas.filter(pk=idea_id).first()
    if idea:
        project.ideas.remove(idea)
        messages.success(request, 'Идея убрана из проекта.')
    else:
        messages.error(request, 'Идея не найдена в проекте.')
    return redirect(project)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


def error_400(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def error_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
