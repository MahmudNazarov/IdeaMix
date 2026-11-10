"""URL routes for IdeaMix."""

from django.urls import path

from . import views

app_name = 'ideas'

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('explore/', views.explore, name='explore'),
    path('search/', views.search, name='search'),

    # Authentication
    path('accounts/register/', views.register, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path(
        'accounts/password-change/',
        views.password_change,
        name='password_change',
    ),

    # Profiles (specific routes first)
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('my-ideas/', views.my_ideas, name='my_ideas'),
    path('favorites/', views.favorites, name='favorites'),

    # Ideas
    path('ideas/create/', views.idea_create, name='idea_create'),
    path('ideas/<slug:slug>/', views.idea_detail, name='idea_detail'),
    path('ideas/<slug:slug>/edit/', views.idea_edit, name='idea_edit'),
    path('ideas/<slug:slug>/delete/', views.idea_delete, name='idea_delete'),
    path('ideas/<slug:slug>/like/', views.idea_like, name='idea_like'),
    path(
        'ideas/<slug:slug>/favorite/',
        views.idea_favorite,
        name='idea_favorite',
    ),
    path(
        'comments/<int:pk>/edit/',
        views.comment_edit,
        name='comment_edit',
    ),
    path(
        'comments/<int:pk>/delete/',
        views.comment_delete,
        name='comment_delete',
    ),

    # Projects
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<slug:slug>/', views.project_detail, name='project_detail'),
    path(
        'projects/<slug:slug>/edit/',
        views.project_edit,
        name='project_edit',
    ),
    path(
        'projects/<slug:slug>/delete/',
        views.project_delete,
        name='project_delete',
    ),
    path(
        'projects/<slug:slug>/join/',
        views.project_join,
        name='project_join',
    ),
    path(
        'projects/<slug:slug>/leave/',
        views.project_leave,
        name='project_leave',
    ),
    path(
        'projects/<slug:slug>/members/add/',
        views.project_member_add,
        name='project_member_add',
    ),
    path(
        'projects/<slug:slug>/members/<int:user_id>/remove/',
        views.project_member_remove,
        name='project_member_remove',
    ),
    path(
        'projects/<slug:slug>/members/<int:user_id>/role/',
        views.project_member_role,
        name='project_member_role',
    ),
    path(
        'projects/<slug:slug>/ideas/add/',
        views.project_idea_add,
        name='project_idea_add',
    ),
    path(
        'projects/<slug:slug>/ideas/<int:idea_id>/remove/',
        views.project_idea_remove,
        name='project_idea_remove',
    ),
]
