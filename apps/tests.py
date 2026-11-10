"""Automated tests for IdeaMix.

The suite is intentionally written against the public behaviour of the
application: routes, rendered templates, permissions and the shape of the
JSON responses used by the progressive-enhancement layer.
"""

import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import CommentForm, ProfileForm, RegisterForm
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
from .profanity import contains_profanity, validate_no_profanity
from .templatetags.admin_dashboard import admin_dashboard

PASSWORD = 'Str0ngPass!2024'

SHORT_DESCRIPTION = 'Короткое, но содержательное описание идеи для каталога.'
DESCRIPTION = (
    'Подробное описание идеи: проблема, решение, аудитория и польза '
    'для сообщества. Этого текста достаточно для прохождения валидации.'
)
PROJECT_DESCRIPTION = (
    'Описание проекта: цель, текущий этап работы и ближайшие задачи '
    'команды. Этого текста достаточно для прохождения валидации.'
)


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            'alice', 'alice@example.com', PASSWORD, first_name='Алиса'
        )
        cls.bob = User.objects.create_user('bob', 'bob@example.com', PASSWORD)
        cls.carol = User.objects.create_user(
            'carol', 'carol@example.com', PASSWORD
        )
        cls.category = Category.objects.create(
            name='Тестовая категория', description='Для тестов'
        )
        cls.public_idea = Idea.objects.create(
            author=cls.alice,
            title='Публичная идея про роботов',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            category=cls.category,
            status=Idea.PUBLISHED,
        )
        cls.private_idea = Idea.objects.create(
            author=cls.alice,
            title='Секретная приватная идея',
            short_description='Приватная идея, доступная только избранным.',
            description=DESCRIPTION,
            visibility=Idea.PRIVATE,
            status=Idea.PUBLISHED,
        )

    def login(self, user=None):
        self.client.force_login(user or self.alice)


class AuthTests(BaseTestCase):
    def test_register_page_renders(self):
        response = self.client.get(reverse('ideas:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')

    def test_registration_creates_user_and_profile(self):
        response = self.client.post(
            reverse('ideas:register'),
            {
                'username': 'diana',
                'email': 'diana@example.com',
                'first_name': 'Диана',
                'last_name': 'Тестова',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
            follow=True,
        )
        self.assertRedirects(response, reverse('ideas:home'))
        user = User.objects.get(username='diana')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_registration_rejects_duplicate_email(self):
        response = self.client.post(
            reverse('ideas:register'),
            {
                'username': 'diana',
                'email': 'BOB@example.com',
                'first_name': '',
                'last_name': '',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'уже существует')
        self.assertFalse(User.objects.filter(username='diana').exists())

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(
            reverse('ideas:register'),
            {
                'username': 'ALICE',
                'email': 'new@example.com',
                'password1': PASSWORD,
                'password2': PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'уже занято')
        self.assertEqual(User.objects.filter(username='ALICE').count(), 0)

    def test_registration_rejects_password_mismatch(self):
        response = self.client.post(
            reverse('ideas:register'),
            {
                'username': 'diana',
                'email': 'diana@example.com',
                'password1': PASSWORD,
                'password2': 'AnotherPass!2024',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='diana').exists())

    def test_login_and_logout_flow(self):
        response = self.client.post(
            reverse('ideas:login'),
            {'username': 'alice', 'password': PASSWORD},
            follow=True,
        )
        self.assertRedirects(response, reverse('ideas:home'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.alice.pk)

        get_response = self.client.get(reverse('ideas:logout'))
        self.assertEqual(get_response.status_code, 405)

        response = self.client.post(reverse('ideas:logout'), follow=True)
        self.assertRedirects(response, reverse('ideas:home'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_shows_error_for_wrong_password(self):
        response = self.client.post(
            reverse('ideas:login'),
            {'username': 'alice', 'password': 'wrong-password'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Неверное имя пользователя или пароль')

    def test_login_respects_safe_next(self):
        response = self.client.post(
            reverse('ideas:login') + '?next=/my-ideas/',
            {'username': 'alice', 'password': PASSWORD},
        )
        self.assertRedirects(response, reverse('ideas:my_ideas'))

    def test_login_ignores_external_next(self):
        response = self.client.post(
            reverse('ideas:login') + '?next=https://evil.example/',
            {'username': 'alice', 'password': PASSWORD},
        )
        self.assertRedirects(response, reverse('ideas:home'))

    def test_authenticated_user_is_redirected_from_auth_pages(self):
        self.login()
        self.assertRedirects(
            self.client.get(reverse('ideas:login')), reverse('ideas:home')
        )
        self.assertRedirects(
            self.client.get(reverse('ideas:register')), reverse('ideas:home')
        )

    def test_profile_created_by_signal(self):
        self.assertTrue(hasattr(self.alice, 'profile'))
        self.assertTrue(hasattr(self.bob, 'profile'))

    def test_password_change(self):
        self.login()
        response = self.client.post(
            reverse('ideas:password_change'),
            {
                'old_password': PASSWORD,
                'new_password1': 'N3wStr0ng!Pass',
                'new_password2': 'N3wStr0ng!Pass',
            },
        )
        self.assertRedirects(response, reverse('ideas:profile_edit'))
        self.alice.refresh_from_db()
        self.assertTrue(self.alice.check_password('N3wStr0ng!Pass'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.alice.pk)

    def test_password_change_requires_login(self):
        response = self.client.get(reverse('ideas:password_change'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('ideas:login'), response.url)


class ProfileTests(BaseTestCase):
    def test_profile_page_and_public_ideas(self):
        response = self.client.get(
            reverse('ideas:profile', args=[self.alice.username])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertContains(response, self.public_idea.title)
        self.assertNotContains(response, self.private_idea.title)

    def test_owner_sees_private_ideas_on_profile(self):
        self.login()
        response = self.client.get(
            reverse('ideas:profile', args=[self.alice.username])
        )
        self.assertContains(response, self.private_idea.title)

    def test_profile_tabs(self):
        self.login(self.bob)
        for tab in ('ideas', 'projects', 'teams'):
            with self.subTest(tab=tab):
                response = self.client.get(
                    reverse('ideas:profile', args=[self.alice.username]),
                    {'tab': tab},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['tab'], tab)

        response = self.client.get(
            reverse('ideas:profile', args=[self.alice.username]),
            {'tab': 'favorites'},
        )
        self.assertNotEqual(response.context['tab'], 'favorites')

    def test_owner_favorites_tab(self):
        Favorite.objects.create(idea=self.public_idea, user=self.alice)
        self.login()
        response = self.client.get(
            reverse('ideas:profile', args=['alice']), {'tab': 'favorites'}
        )
        self.assertEqual(response.context['tab'], 'favorites')
        self.assertContains(response, self.public_idea.title)

    def test_profile_edit(self):
        self.login()
        response = self.client.post(
            reverse('ideas:profile_edit'),
            {
                'first_name': 'Алиса',
                'last_name': 'Иванова',
                'email': 'alice@example.com',
                'bio': 'Люблю идеи.',
                'location': 'Москва',
                'website': 'https://example.com',
                'skills': 'Python, UX, маркетинг',
            },
            follow=True,
        )
        self.assertRedirects(
            response, reverse('ideas:profile', args=['alice'])
        )
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.last_name, 'Иванова')
        self.assertEqual(self.alice.profile.bio, 'Люблю идеи.')
        self.assertEqual(
            self.alice.profile.skills, 'python, ux, маркетинг'
        )

    def test_profile_edit_rejects_taken_email(self):
        self.login()
        response = self.client.post(
            reverse('ideas:profile_edit'),
            {
                'first_name': '',
                'last_name': '',
                'email': 'bob@example.com',
                'bio': '',
                'location': '',
                'website': '',
                'skills': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Этот email уже занят')

    def test_avatar_upload(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, True)
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
            b'\x00\x00\x02\x02D\x01\x00;'
        )
        with override_settings(MEDIA_ROOT=media_root):
            self.login()
            response = self.client.post(
                reverse('ideas:profile_edit'),
                {
                    'first_name': 'Алиса',
                    'last_name': '',
                    'email': 'alice@example.com',
                    'bio': '',
                    'location': '',
                    'website': '',
                    'skills': '',
                    'avatar': SimpleUploadedFile(
                        'avatar.gif', gif, content_type='image/gif'
                    ),
                },
                follow=True,
            )
            self.assertEqual(response.status_code, 200)
            self.alice.profile.refresh_from_db()
            self.assertTrue(
                self.alice.profile.avatar.name.startswith('avatars/')
            )

    def test_unknown_profile_returns_404(self):
        response = self.client.get(reverse('ideas:profile', args=['nobody']))
        self.assertEqual(response.status_code, 404)


class IdeaCrudTests(BaseTestCase):
    def test_create_requires_login(self):
        response = self.client.get(reverse('ideas:idea_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('ideas:login'), response.url)

    def test_create_idea(self):
        self.login()
        response = self.client.post(
            reverse('ideas:idea_create'),
            {
                'title': 'Новая идея для города',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'category': self.category.pk,
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
            },
        )
        idea = Idea.objects.get(title='Новая идея для города')
        self.assertRedirects(response, idea.get_absolute_url())
        self.assertEqual(idea.author, self.alice)
        self.assertTrue(idea.slug)
        self.assertEqual(idea.status, Idea.PUBLISHED)

    def test_create_draft(self):
        self.login()
        response = self.client.post(
            reverse('ideas:idea_create'),
            {
                'title': 'Черновик новой идеи',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'visibility': Idea.PUBLIC,
                'status': Idea.DRAFT,
            },
        )
        idea = Idea.objects.get(title='Черновик новой идеи')
        self.assertRedirects(response, idea.get_absolute_url())
        self.assertEqual(idea.status, Idea.DRAFT)

    def test_create_idea_validation_errors(self):
        self.login()
        response = self.client.post(
            reverse('ideas:idea_create'),
            {
                'title': 'Идея',
                'short_description': 'Коротко',
                'description': 'Коротко',
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Название должно быть длиннее')
        self.assertContains(response, 'минимум 20 символов')
        self.assertContains(response, 'минимум 30 символов')
        self.assertFalse(Idea.objects.filter(title='Идея').exists())

    def test_too_many_tags_rejected(self):
        self.login()
        response = self.client.post(
            reverse('ideas:idea_create'),
            {
                'title': 'Идея с лишними тегами',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
                'tags': 'one, two, three, four, five, six',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'не более 5 тегов')
        self.assertFalse(Idea.objects.filter(title='Идея с лишними тегами').exists())

    def test_slug_is_unique(self):
        first = Idea.objects.create(
            author=self.alice,
            title='Одинаковое название',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
        )
        second = Idea.objects.create(
            author=self.alice,
            title='Одинаковое название',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
        )
        self.assertNotEqual(first.slug, second.slug)

    def test_edit_own_idea(self):
        self.login()
        response = self.client.post(
            reverse('ideas:idea_edit', args=[self.public_idea.slug]),
            {
                'title': 'Обновлённая публичная идея',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'category': self.category.pk,
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
            },
        )
        self.assertRedirects(response, self.public_idea.get_absolute_url())
        self.public_idea.refresh_from_db()
        self.assertEqual(self.public_idea.title, 'Обновлённая публичная идея')

    def test_cannot_edit_foreign_idea(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:idea_edit', args=[self.public_idea.slug]),
            {
                'title': 'Взломанная идея',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.public_idea.refresh_from_db()
        self.assertEqual(self.public_idea.title, 'Публичная идея про роботов')

    def test_edit_page_renders_for_owner(self):
        self.login()
        response = self.client.get(
            reverse('ideas:idea_edit', args=[self.public_idea.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ideas/idea_edit.html')
        self.assertContains(response, 'Улучшите идею')

    def test_cannot_delete_foreign_idea(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:idea_delete', args=[self.public_idea.slug])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Idea.objects.filter(pk=self.public_idea.pk).exists())

    def test_delete_own_idea(self):
        self.login()
        confirm = self.client.get(
            reverse('ideas:idea_delete', args=[self.public_idea.slug])
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertTemplateUsed(confirm, 'ideas/idea_delete.html')

        response = self.client.post(
            reverse('ideas:idea_delete', args=[self.public_idea.slug]),
            follow=True,
        )
        self.assertRedirects(response, reverse('ideas:my_ideas'))
        self.assertFalse(Idea.objects.filter(pk=self.public_idea.pk).exists())

    def test_private_idea_hidden_from_others(self):
        detail_url = reverse(
            'ideas:idea_detail', args=[self.private_idea.slug]
        )
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        self.login(self.bob)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        response = self.client.get(reverse('ideas:home'))
        self.assertNotContains(response, self.private_idea.title)

    def test_owner_sees_private_idea(self):
        self.login()
        response = self.client.get(
            reverse('ideas:idea_detail', args=[self.private_idea.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Приватная идея')

    def test_draft_idea_hidden_from_others(self):
        draft = Idea.objects.create(
            author=self.alice,
            title='Черновик, который не должен утечь',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            status=Idea.DRAFT,
        )
        self.login(self.bob)
        self.assertEqual(
            self.client.get(draft.get_absolute_url()).status_code, 404
        )

    def test_project_member_sees_attached_private_idea(self):
        project = Project.objects.create(
            creator=self.alice,
            title='Закрытый проект',
            description=PROJECT_DESCRIPTION,
            visibility=Project.PRIVATE,
        )
        project.ideas.add(self.private_idea)
        ProjectMember.objects.create(project=project, user=self.bob)

        self.login(self.bob)
        response = self.client.get(
            reverse('ideas:idea_detail', args=[self.private_idea.slug])
        )
        self.assertEqual(response.status_code, 200)

    def test_project_owner_sees_attached_private_idea(self):
        project = Project.objects.create(
            creator=self.bob,
            title='Проект без явного членства',
            description=PROJECT_DESCRIPTION,
            visibility=Project.PRIVATE,
        )
        project.ideas.add(self.private_idea)

        self.login(self.bob)
        response = self.client.get(
            reverse('ideas:idea_detail', args=[self.private_idea.slug])
        )
        self.assertEqual(response.status_code, 200)

    def test_detail_page_shows_comments_and_reactions(self):
        self.login(self.bob)
        response = self.client.get(self.public_idea.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ideas/idea_detail.html')
        self.assertContains(response, 'Комментарии')

    def test_view_counter_increments_once_per_session(self):
        self.login(self.bob)
        url = self.public_idea.get_absolute_url()
        self.client.get(url)
        self.public_idea.refresh_from_db()
        first_count = self.public_idea.views_count
        self.assertGreaterEqual(first_count, 1)
        self.client.get(url)
        self.public_idea.refresh_from_db()
        self.assertEqual(self.public_idea.views_count, first_count)

    def test_cover_image_upload(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, True)
        gif = (
            b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
            b'\x00\x00\x02\x02D\x01\x00;'
        )
        with override_settings(MEDIA_ROOT=media_root):
            self.login()
            response = self.client.post(
                reverse('ideas:idea_create'),
                {
                    'title': 'Идея с обложкой',
                    'short_description': SHORT_DESCRIPTION,
                    'description': DESCRIPTION,
                    'visibility': Idea.PUBLIC,
                    'status': Idea.PUBLISHED,
                    'cover_image': SimpleUploadedFile(
                        'cover.gif', gif, content_type='image/gif'
                    ),
                },
            )
            idea = Idea.objects.get(title='Идея с обложкой')
            self.assertRedirects(response, idea.get_absolute_url())
            self.assertTrue(idea.cover_image.name.startswith('ideas/covers/'))


class DiscoveryTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.extra = []
        for index in range(12):
            cls.extra.append(
                Idea.objects.create(
                    author=cls.alice,
                    title=f'Городская идея номер {index:02d}',
                    short_description=SHORT_DESCRIPTION,
                    description=DESCRIPTION,
                    category=cls.category,
                    status=Idea.PUBLISHED,
                )
            )

    def test_search_by_title(self):
        response = self.client.get(
            reverse('ideas:search'), {'q': 'роботов'}
        )
        self.assertContains(response, self.public_idea.title)
        self.assertNotContains(response, self.extra[3].title)

    def test_search_by_author(self):
        response = self.client.get(reverse('ideas:search'), {'q': 'alice'})
        self.assertEqual(response.context['total_count'], 13)
        object_list = list(
            response.context['page_obj'].paginator.object_list
        )
        self.assertIn(self.public_idea, object_list)
        self.assertNotIn(self.private_idea, object_list)

    def test_search_without_query_returns_nothing(self):
        response = self.client.get(reverse('ideas:search'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 0)

    def test_category_filter(self):
        other = Category.objects.create(name='Другая категория')
        idea = Idea.objects.create(
            author=self.alice,
            title='Идея в другой категории',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            category=other,
            status=Idea.PUBLISHED,
        )
        response = self.client.get(
            reverse('ideas:explore'), {'category': self.category.slug}
        )
        self.assertEqual(response.context['total_count'], 13)
        object_list = list(
            response.context['page_obj'].paginator.object_list
        )
        self.assertIn(self.public_idea, object_list)
        self.assertNotIn(idea, object_list)

    def test_status_and_tag_filters(self):
        tagged = Idea.objects.create(
            author=self.alice,
            title='Идея с уникальным тегом',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            tags='экология, транспорт',
            status=Idea.IN_PROGRESS,
        )
        response = self.client.get(
            reverse('ideas:explore'), {'tag': 'экология', 'status': 'in_progress'}
        )
        self.assertEqual(response.context['total_count'], 1)
        self.assertEqual(response.context['page_obj'].object_list[0], tagged)

    def test_draft_status_filter_is_ignored(self):
        response = self.client.get(
            reverse('ideas:explore'), {'status': Idea.DRAFT}
        )
        self.assertEqual(response.context['filters']['status'], '')
        self.assertEqual(response.context['total_count'], 13)

    def test_sort_popular(self):
        IdeaLike.objects.create(idea=self.extra[0], user=self.bob)
        IdeaLike.objects.create(idea=self.extra[0], user=self.carol)
        response = self.client.get(
            reverse('ideas:explore'), {'sort': 'popular'}
        )
        self.assertEqual(response.context['page_obj'].object_list[0], self.extra[0])

    def test_pagination(self):
        response = self.client.get(reverse('ideas:explore'))
        self.assertEqual(len(response.context['page_obj'].object_list), 9)
        self.assertTrue(response.context['page_obj'].has_next())

        response = self.client.get(reverse('ideas:explore'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['page_obj'].has_previous())
        self.assertEqual(len(response.context['page_obj'].object_list), 4)

    def test_invalid_and_out_of_range_page(self):
        response = self.client.get(reverse('ideas:explore'), {'page': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 1)

        response = self.client.get(reverse('ideas:explore'), {'page': 999})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['page_obj'].number,
            response.context['page_obj'].paginator.num_pages,
        )

    def test_private_ideas_excluded_from_catalog(self):
        self.client.force_login(self.carol)
        response = self.client.get(reverse('ideas:explore'))
        self.assertNotContains(response, self.private_idea.title)

    def test_my_ideas_requires_login_and_includes_private(self):
        response = self.client.get(reverse('ideas:my_ideas'))
        self.assertEqual(response.status_code, 302)

        self.login()
        response = self.client.get(reverse('ideas:my_ideas'))
        object_list = list(
            response.context['page_obj'].paginator.object_list
        )
        self.assertIn(self.public_idea, object_list)
        self.assertIn(self.private_idea, object_list)

    def test_my_ideas_status_filter_and_counts(self):
        Idea.objects.create(
            author=self.alice,
            title='Черновик Алисы',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            status=Idea.DRAFT,
        )
        self.login()
        response = self.client.get(
            reverse('ideas:my_ideas'), {'status': Idea.DRAFT}
        )
        self.assertEqual(response.context['active_status'], Idea.DRAFT)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['counts'][Idea.DRAFT], 1)

    def test_favorites_page(self):
        Favorite.objects.create(idea=self.public_idea, user=self.alice)
        self.login()
        response = self.client.get(reverse('ideas:favorites'))
        self.assertContains(response, self.public_idea.title)
        self.assertNotContains(response, self.extra[0].title)

    def test_home_renders_sections(self):
        response = self.client.get(reverse('ideas:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pages/home.html')
        self.assertEqual(response.context['stats']['ideas'], 13)
        self.assertTrue(response.context['has_ideas'])


class ReactionTests(BaseTestCase):
    def test_like_requires_login(self):
        response = self.client.post(
            reverse('ideas:idea_like', args=[self.public_idea.slug])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('ideas:login'), response.url)
        self.assertFalse(
            IdeaLike.objects.filter(
                idea=self.public_idea, user=self.alice
            ).exists()
        )

    def test_anonymous_ajax_like_returns_401(self):
        response = self.client.post(
            reverse('ideas:idea_like', args=[self.public_idea.slug]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertIn('login_url', payload)
        self.assertIn(reverse('ideas:login'), payload['login_url'])

    def test_like_toggle_and_json(self):
        self.login(self.bob)
        url = reverse('ideas:idea_like', args=[self.public_idea.slug])
        response = self.client.post(
            url, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'active': True, 'count': 1})
        self.assertTrue(
            IdeaLike.objects.filter(
                idea=self.public_idea, user=self.bob
            ).exists()
        )

        response = self.client.post(
            url, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'active': False, 'count': 0})
        self.assertFalse(
            IdeaLike.objects.filter(
                idea=self.public_idea, user=self.bob
            ).exists()
        )

    def test_like_without_ajax_redirects_with_message(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:idea_like', args=[self.public_idea.slug])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('#reactions', response.url)

    def test_like_get_not_allowed(self):
        self.login()
        response = self.client.get(
            reverse('ideas:idea_like', args=[self.public_idea.slug])
        )
        self.assertEqual(response.status_code, 405)

    def test_favorite_toggle(self):
        self.login(self.bob)
        url = reverse('ideas:idea_favorite', args=[self.public_idea.slug])
        response = self.client.post(
            url, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.json(), {'active': True, 'count': 1})
        self.assertTrue(
            Favorite.objects.filter(
                idea=self.public_idea, user=self.bob
            ).exists()
        )

        response = self.client.get(reverse('ideas:favorites'))
        self.assertContains(response, self.public_idea.title)

        self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertFalse(
            Favorite.objects.filter(
                idea=self.public_idea, user=self.bob
            ).exists()
        )

    def test_add_comment(self):
        self.login(self.bob)
        response = self.client.post(
            self.public_idea.get_absolute_url(),
            {'text': 'Очень полезная идея, спасибо!'},
            follow=True,
        )
        self.assertContains(response, 'Очень полезная идея, спасибо!')
        comment = Comment.objects.get(idea=self.public_idea)
        self.assertEqual(comment.author, self.bob)
        self.assertEqual(comment.text, 'Очень полезная идея, спасибо!')

    def test_comment_validation_error_is_rendered(self):
        self.login(self.bob)
        response = self.client.post(
            self.public_idea.get_absolute_url(), {'text': 'x'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Комментарий слишком короткий')
        self.assertFalse(Comment.objects.filter(idea=self.public_idea).exists())

    def test_anonymous_cannot_comment(self):
        response = self.client.post(
            self.public_idea.get_absolute_url(), {'text': 'Привет!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('ideas:login'), response.url)
        self.assertFalse(Comment.objects.exists())

    def test_comment_edit(self):
        comment = Comment.objects.create(
            idea=self.public_idea, author=self.bob, text='Исходный комментарий'
        )
        self.login(self.bob)
        response = self.client.get(
            reverse('ideas:comment_edit', args=[comment.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ideas/comment_edit.html')

        response = self.client.post(
            reverse('ideas:comment_edit', args=[comment.pk]),
            {'text': 'Обновлённый комментарий'},
        )
        self.assertRedirects(
            response,
            f'{self.public_idea.get_absolute_url()}#comment-{comment.pk}',
        )
        comment.refresh_from_db()
        self.assertEqual(comment.text, 'Обновлённый комментарий')

    def test_cannot_edit_foreign_comment(self):
        comment = Comment.objects.create(
            idea=self.public_idea, author=self.bob, text='Комментарий Боба'
        )
        self.login(self.carol)
        response = self.client.post(
            reverse('ideas:comment_edit', args=[comment.pk]),
            {'text': 'Чужая правка'},
        )
        self.assertEqual(response.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.text, 'Комментарий Боба')

    def test_comment_delete_permissions(self):
        comment = Comment.objects.create(
            idea=self.public_idea, author=self.bob, text='Комментарий Боба'
        )
        self.login(self.carol)
        response = self.client.post(
            reverse('ideas:comment_delete', args=[comment.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())

        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:comment_delete', args=[comment.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_comment_on_private_idea_hidden(self):
        self.login(self.bob)
        response = self.client.post(
            self.private_idea.get_absolute_url(),
            {'text': 'Чужой комментарий'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Comment.objects.exists())


class ProjectTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.project = Project.objects.create(
            creator=cls.alice,
            title='Открытый проект',
            description=PROJECT_DESCRIPTION,
            category=cls.category,
            technologies='Python, Django',
            needed_specialists='Дизайнер, исследователь',
        )
        ProjectMember.objects.create(
            project=cls.project,
            user=cls.alice,
            role=ProjectMember.OWNER,
        )

    def test_project_list_renders(self):
        response = self.client.get(reverse('ideas:project_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_list.html')
        self.assertContains(response, self.project.title)

    def test_project_list_filters(self):
        response = self.client.get(
            reverse('ideas:project_list'), {'q': 'Django'}
        )
        self.assertEqual(response.context['total_count'], 1)
        response = self.client.get(
            reverse('ideas:project_list'), {'q': 'совершенно другой запрос'}
        )
        self.assertEqual(response.context['total_count'], 0)

    def test_create_project_adds_owner_membership(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:project_create'),
            {
                'title': 'Проект Боба',
                'description': PROJECT_DESCRIPTION,
                'status': Project.PLANNING,
                'visibility': Project.PUBLIC,
                'is_open': 'on',
                'technologies': 'Python, Django',
                'needed_specialists': 'Frontend-разработчик',
            },
        )
        project = Project.objects.get(title='Проект Боба')
        self.assertRedirects(response, project.get_absolute_url())
        membership = ProjectMember.objects.get(
            project=project, user=self.bob
        )
        self.assertEqual(membership.role, ProjectMember.OWNER)

    def test_create_project_from_idea(self):
        self.login(self.alice)
        response = self.client.get(
            reverse('ideas:project_create'), {'idea': self.public_idea.pk}
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial['related_idea'], self.public_idea)

    def test_private_project_hidden(self):
        private = Project.objects.create(
            creator=self.alice,
            title='Приватный проект',
            description=PROJECT_DESCRIPTION,
            visibility=Project.PRIVATE,
        )
        self.login(self.bob)
        response = self.client.get(reverse('ideas:project_list'))
        self.assertNotContains(response, private.title)
        response = self.client.get(private.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_project_detail_renders_for_public(self):
        response = self.client.get(self.project.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_detail.html')
        self.assertContains(response, self.project.title)

    def test_public_project_detail_shows_only_public_ideas(self):
        self.project.ideas.add(self.public_idea, self.private_idea)
        response = self.client.get(self.project.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.public_idea.title)
        self.assertNotContains(response, self.private_idea.title)

    def test_member_can_see_private_idea_in_project(self):
        self.project.ideas.add(self.private_idea)
        ProjectMember.objects.create(project=self.project, user=self.bob)
        self.login(self.bob)
        response = self.client.get(self.project.get_absolute_url())
        self.assertContains(response, self.private_idea.title)

    def test_add_member_by_owner(self):
        self.login()
        response = self.client.post(
            reverse('ideas:project_member_add', args=[self.project.slug]),
            {'username': 'bob', 'role': ProjectMember.DESIGNER},
            follow=True,
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        membership = ProjectMember.objects.get(
            project=self.project, user=self.bob
        )
        self.assertEqual(membership.role, ProjectMember.DESIGNER)

    def test_add_unknown_member_shows_error(self):
        self.login()
        response = self.client.post(
            reverse('ideas:project_member_add', args=[self.project.slug]),
            {'username': 'nobody', 'role': ProjectMember.DEVELOPER},
            follow=True,
        )
        self.assertContains(response, 'не найден')
        self.assertEqual(
            ProjectMember.objects.filter(project=self.project).count(), 1
        )

    def test_duplicate_member_shows_error(self):
        ProjectMember.objects.create(project=self.project, user=self.bob)
        self.login()
        response = self.client.post(
            reverse('ideas:project_member_add', args=[self.project.slug]),
            {'username': 'bob', 'role': ProjectMember.DEVELOPER},
            follow=True,
        )
        self.assertContains(response, 'уже участвует')
        self.assertEqual(
            ProjectMember.objects.filter(
                project=self.project, user=self.bob
            ).count(),
            1,
        )

    def test_non_owner_cannot_manage_members(self):
        ProjectMember.objects.create(project=self.project, user=self.bob)
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:project_member_add', args=[self.project.slug]),
            {'username': 'carol', 'role': ProjectMember.DEVELOPER},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.project, user=self.carol
            ).exists()
        )

    def test_remove_member(self):
        ProjectMember.objects.create(project=self.project, user=self.bob)
        self.login()
        response = self.client.post(
            reverse(
                'ideas:project_member_remove',
                args=[self.project.slug, self.bob.pk],
            ),
            follow=True,
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.project, user=self.bob
            ).exists()
        )

    def test_owner_cannot_be_removed(self):
        self.login()
        response = self.client.post(
            reverse(
                'ideas:project_member_remove',
                args=[self.project.slug, self.alice.pk],
            ),
            follow=True,
        )
        self.assertContains(response, 'Нельзя удалить создателя')
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.project, user=self.alice
            ).exists()
        )

    def test_change_member_role(self):
        membership = ProjectMember.objects.create(
            project=self.project, user=self.bob, role=ProjectMember.DEVELOPER
        )
        self.login()
        response = self.client.post(
            reverse(
                'ideas:project_member_role',
                args=[self.project.slug, self.bob.pk],
            ),
            {'role': ProjectMember.RESEARCHER},
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        membership.refresh_from_db()
        self.assertEqual(membership.role, ProjectMember.RESEARCHER)

    def test_invalid_member_role_is_rejected(self):
        membership = ProjectMember.objects.create(
            project=self.project, user=self.bob, role=ProjectMember.DEVELOPER
        )
        self.login()
        self.client.post(
            reverse(
                'ideas:project_member_role',
                args=[self.project.slug, self.bob.pk],
            ),
            {'role': 'owner'},
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, ProjectMember.DEVELOPER)

    def test_add_and_remove_idea(self):
        self.login()
        response = self.client.post(
            reverse('ideas:project_idea_add', args=[self.project.slug]),
            {'idea': self.public_idea.pk},
            follow=True,
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        self.assertIn(self.public_idea, self.project.ideas.all())

        response = self.client.post(
            reverse(
                'ideas:project_idea_remove',
                args=[self.project.slug, self.public_idea.pk],
            ),
            follow=True,
        )
        self.assertNotIn(self.public_idea, self.project.ideas.all())

    def test_non_owner_cannot_add_ideas(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:project_idea_add', args=[self.project.slug]),
            {'idea': self.public_idea.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_join_and_leave_project(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:project_join', args=[self.project.slug]),
            {'role': ProjectMember.DESIGNER},
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        membership = ProjectMember.objects.get(
            project=self.project, user=self.bob
        )
        self.assertEqual(membership.role, ProjectMember.DESIGNER)

        response = self.client.post(
            reverse('ideas:project_leave', args=[self.project.slug])
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.project, user=self.bob
            ).exists()
        )

    def test_creator_cannot_leave_own_project(self):
        self.login()
        response = self.client.post(
            reverse('ideas:project_leave', args=[self.project.slug]),
            follow=True,
        )
        self.assertContains(response, 'Создатель не может покинуть')
        self.assertTrue(
            ProjectMember.objects.filter(
                project=self.project, user=self.alice
            ).exists()
        )

    def test_closed_project_cannot_be_joined(self):
        self.project.is_open = False
        self.project.save(update_fields=['is_open'])
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:project_join', args=[self.project.slug]),
            {'role': ProjectMember.DEVELOPER},
            follow=True,
        )
        self.assertContains(response, 'не принимает новых участников')
        self.assertFalse(
            ProjectMember.objects.filter(
                project=self.project, user=self.bob
            ).exists()
        )

    def test_project_edit_and_delete_permissions(self):
        self.login(self.bob)
        self.assertEqual(
            self.client.get(
                reverse('ideas:project_edit', args=[self.project.slug])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('ideas:project_delete', args=[self.project.slug])
            ).status_code,
            403,
        )

        self.login(self.alice)
        response = self.client.post(
            reverse('ideas:project_edit', args=[self.project.slug]),
            {
                'title': 'Обновлённый проект',
                'description': PROJECT_DESCRIPTION,
                'status': Project.ACTIVE,
                'visibility': Project.PUBLIC,
                'is_open': 'on',
                'technologies': 'Python, Django, PostgreSQL',
                'needed_specialists': 'Дизайнер',
            },
        )
        self.assertRedirects(response, self.project.get_absolute_url())
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, 'Обновлённый проект')
        self.assertEqual(self.project.status, Project.ACTIVE)

        response = self.client.get(
            reverse('ideas:project_delete', args=[self.project.slug])
        )
        self.assertTemplateUsed(response, 'projects/project_delete.html')

        response = self.client.post(
            reverse('ideas:project_delete', args=[self.project.slug]),
            follow=True,
        )
        self.assertRedirects(response, reverse('ideas:project_list'))
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())


class InfrastructureTests(BaseTestCase):
    def test_all_named_urls_resolve(self):
        names = {
            'home': [],
            'about': [],
            'explore': [],
            'search': [],
            'idea_create': [],
            'idea_detail': ['demo-idea'],
            'idea_edit': ['demo-idea'],
            'idea_delete': ['demo-idea'],
            'idea_like': ['demo-idea'],
            'idea_favorite': ['demo-idea'],
            'comment_edit': [1],
            'comment_delete': [1],
            'register': [],
            'login': [],
            'logout': [],
            'password_change': [],
            'profile': ['alice'],
            'profile_edit': [],
            'my_ideas': [],
            'favorites': [],
            'project_list': [],
            'project_create': [],
            'project_detail': ['demo-project'],
            'project_edit': ['demo-project'],
            'project_delete': ['demo-project'],
            'project_join': ['demo-project'],
            'project_leave': ['demo-project'],
            'project_member_add': ['demo-project'],
            'project_member_remove': ['demo-project', 1],
            'project_member_role': ['demo-project', 1],
            'project_idea_add': ['demo-project'],
            'project_idea_remove': ['demo-project', 1],
        }
        for name, args in names.items():
            with self.subTest(name=name):
                self.assertTrue(reverse(f'ideas:{name}', args=args))

    def test_public_pages_render(self):
        pages = [
            (reverse('ideas:home'), 'pages/home.html'),
            (reverse('ideas:about'), 'pages/about.html'),
            (reverse('ideas:explore'), 'pages/explore.html'),
            (
                reverse('ideas:search') + '?q=идея',
                'pages/search.html',
            ),
            (self.public_idea.get_absolute_url(), 'ideas/idea_detail.html'),
            (reverse('ideas:profile', args=['alice']), 'accounts/profile.html'),
            (reverse('ideas:project_list'), 'projects/project_list.html'),
            (reverse('ideas:login'), 'accounts/login.html'),
            (reverse('ideas:register'), 'accounts/register.html'),
        ]
        for url, template in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_authenticated_pages_render(self):
        self.login()
        pages = [
            (reverse('ideas:my_ideas'), 'ideas/my_ideas.html'),
            (reverse('ideas:favorites'), 'ideas/favorites.html'),
            (reverse('ideas:idea_create'), 'ideas/idea_create.html'),
            (reverse('ideas:profile_edit'), 'accounts/profile_edit.html'),
            (reverse('ideas:password_change'), 'accounts/password_change.html'),
            (reverse('ideas:project_create'), 'projects/project_create.html'),
        ]
        for url, template in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_admin_is_available(self):
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_unknown_page_uses_404_template(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, 'errors/404.html')

    def test_permission_denied_uses_403_template(self):
        self.login(self.bob)
        response = self.client.post(
            reverse('ideas:idea_edit', args=[self.public_idea.slug]),
            {
                'title': 'Чужая идея',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'visibility': Idea.PUBLIC,
                'status': Idea.PUBLISHED,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'errors/403.html')

    def test_static_files_are_found(self):
        from django.contrib.staticfiles import finders

        for path in (
            'css/style.css',
            'css/responsive.css',
            'js/main.js',
            'img/favicon.svg',
            'img/logo-mark.svg',
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))

    def test_theme_toggle_and_bootstrap_are_rendered(self):
        response = self.client.get(reverse('ideas:home'))
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'ideamix-theme')
        self.assertContains(response, 'data-theme="light"')

        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'ideamix-theme', status_code=404)

    def test_media_and_templates_are_configured(self):
        self.assertTrue(settings.MEDIA_ROOT)
        self.assertEqual(settings.MEDIA_URL, '/media/')
        self.assertIn(settings.BASE_DIR / 'templates', settings.TEMPLATES[0]['DIRS'])
        self.assertIn('apps.apps.AppsConfig', settings.INSTALLED_APPS)
        self.assertEqual(settings.LANGUAGE_CODE, 'ru-ru')
        self.assertEqual(settings.TIME_ZONE, 'Asia/Tashkent')

    def test_no_pending_migrations(self):
        call_command(
            'makemigrations',
            'apps',
            check=True,
            dry_run=True,
            verbosity=0,
        )

    def test_catalog_query_count_does_not_grow_with_ideas(self):
        with CaptureQueriesContext(connection) as first:
            self.client.get(reverse('ideas:explore'))

        for index in range(6):
            Idea.objects.create(
                author=self.alice,
                title=f'Идея для проверки N+1 {index}',
                short_description=SHORT_DESCRIPTION,
                description=DESCRIPTION,
                status=Idea.PUBLISHED,
            )

        with CaptureQueriesContext(connection) as second:
            self.client.get(reverse('ideas:explore'))

        self.assertLessEqual(len(second), len(first) + 2)


class ProfanityFilterTests(TestCase):
    """The moderation filter must catch abuse without blocking normal words."""

    def test_rejects_russian_profanity_and_obfuscation(self):
        samples = [
            'хуй',
            'нахуй',
            'нихуя',
            'пиздец',
            'распиздяй',
            'блядь',
            'блять',
            'бл@дь',
            '6лядь',
            'сука',
            'сучка',
            'ебать',
            'заебал',
            'выебываться',
            'долбоёб',
            'отъебись',
            'разъебать',
            'мудак',
            'пидор',
            'пидорас',
            'гандон',
            'жопа',
            'говно',
            'срать',
            'херня',
            'шлюха',
            'ублюдок',
            'мразь',
            'падла',
            'манда',
            'чмо',
            'х*у*й',
            'х.у.й',
            'хуууй',
            'бляяядь',
            'пuздa',
            'e6aть',
            'blyat',
            'pizda',
            'huy',
            'suka',
            'mudak',
            'pidor',
            'govno',
            'zhopa',
            'dolboeb',
            'fuck',
            'fucking',
            'shit',
            'bullshit',
            'bitch',
            'asshole',
            'cunt',
            'whore',
            'slut',
            'faggot',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(contains_profanity(sample))

    def test_allows_safe_words_and_technical_terms(self):
        samples = [
            'хлеб',
            'себе',
            'тебе',
            'небо',
            'небеса',
            'сукно',
            'сук',
            'бляха',
            'бляшка',
            'блямба',
            'мандат',
            'мандарин',
            'команда',
            'потребление',
            'учебник',
            'волшебник',
            'стебель',
            'лебедь',
            'сразу',
            'сравнить',
            'сработать',
            'класс',
            'pass',
            'Python',
            'Django',
            'дизайн',
            'стратегия',
            'мастер',
            'проект',
            'дебаты',
            'гребень',
            'погреб',
            'изба',
            'избегать',
            'себастьян',
            'херсон',
            'херувим',
            'шлюз',
            'дрофа',
            'говорить',
            'аналитика',
            'маркетинг',
            'стартап',
            'команда мечты',
            'идея для города',
            'классный проект',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertFalse(contains_profanity(sample))

    def test_model_field_validator_blocks_publication(self):
        author = User.objects.create_user('author', 'author@example.com', PASSWORD)
        idea = Idea(
            author=author,
            title='Идея хуй',
            short_description=SHORT_DESCRIPTION,
            description=DESCRIPTION,
            status=Idea.PUBLISHED,
        )
        with self.assertRaises(ValidationError) as context:
            idea.full_clean()
        self.assertIn('title', context.exception.message_dict)

    def test_all_public_content_models_are_protected(self):
        author = User.objects.create_user('contentauthor', 'c@example.com', PASSWORD)
        project = Project(
            creator=author,
            title='Проект блядь',
            description=PROJECT_DESCRIPTION,
        )
        with self.assertRaises(ValidationError) as context:
            project.full_clean()
        self.assertIn('title', context.exception.message_dict)

        category = Category(name='Пиздец', description='Описание')
        with self.assertRaises(ValidationError) as context:
            category.full_clean()
        self.assertIn('name', context.exception.message_dict)

        profile = author.profile
        profile.bio = 'Немного о себе: хуйня'
        with self.assertRaises(ValidationError) as context:
            profile.full_clean()
        self.assertIn('bio', context.exception.message_dict)

    def test_clean_idea_passes_model_validation(self):
        author = User.objects.create_user('cleanauthor', 'clean@example.com', PASSWORD)
        idea = Idea(
            author=author,
            title='Сервис обмена книгами',
            short_description='Помогаем соседям обмениваться книгами и знаниями.',
            description=DESCRIPTION,
            status=Idea.PUBLISHED,
        )
        idea.full_clean()

    def test_view_does_not_publish_profane_idea(self):
        author = User.objects.create_user('viewauthor', 'view@example.com', PASSWORD)
        self.client.force_login(author)
        response = self.client.post(
            reverse('ideas:idea_create'),
            {
                'title': 'Новая хуйня',
                'short_description': SHORT_DESCRIPTION,
                'description': DESCRIPTION,
                'status': Idea.PUBLISHED,
                'visibility': Idea.PUBLIC,
                'tags': 'тест',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Idea.objects.filter(author=author).count(), 0)
        self.assertContains(response, 'нецензурная')

    def test_comment_form_rejects_profanity(self):
        form = CommentForm(data={'text': 'Это полная хуйня, а не проект.'})
        self.assertFalse(form.is_valid())
        self.assertIn('text', form.errors)
        self.assertIn('нецензурная', form.errors['text'][0])

    def test_comment_form_accepts_clean_text(self):
        form = CommentForm(data={'text': 'Отличная идея, обязательно попробую!'})
        self.assertTrue(form.is_valid(), form.errors)

    def test_profile_form_rejects_profanity_in_names(self):
        user = User.objects.create_user(
            'profileuser', 'profile@example.com', PASSWORD
        )
        form = ProfileForm(
            data={
                'first_name': 'Пидор',
                'last_name': 'Иванов',
                'email': 'profile@example.com',
                'bio': 'Люблю делать полезные сервисы.',
                'location': 'Ташкент',
                'website': '',
                'skills': 'Python, Django',
            },
            instance=user.profile,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_register_form_rejects_profanity_in_username_and_name(self):
        form = RegisterForm(
            data={
                'username': 'blyat',
                'email': 'new@example.com',
                'first_name': 'Нормально',
                'last_name': 'Нормально',
                'password1': PASSWORD,
                'password2': PASSWORD,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

        form = RegisterForm(
            data={
                'username': 'cleanuser',
                'email': 'new@example.com',
                'first_name': 'Хуй',
                'last_name': 'Нормально',
                'password1': PASSWORD,
                'password2': PASSWORD,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    @override_settings(PROFANITY_FILTER_ENABLED=False)
    def test_setting_can_disable_validator(self):
        validate_no_profanity('хуй')
        self.assertTrue(contains_profanity('хуй'))


class AdminDashboardTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = User.objects.create_superuser(
            'siteadmin', 'siteadmin@example.com', PASSWORD
        )

    def test_admin_index_renders_dashboard(self):
        self.login(self.admin)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/index.html')
        self.assertContains(response, 'Пульс платформы')
        self.assertContains(response, 'Фильтр нецензурной лексики включён')
        self.assertContains(response, 'Онлайн за 7 дней')
        self.assertContains(response, 'imx-online__chart')
        self.assertContains(response, 'График онлайна пользователей за последние 7 дней')
        for title in ('Аудитория', 'Идеи', 'Проекты', 'Сообщество'):
            with self.subTest(title=title):
                self.assertContains(response, title)
        self.assertContains(response, 'Управление платформой')

    def test_dashboard_metrics_match_database(self):
        Comment.objects.create(
            idea=self.public_idea, author=self.bob, text='Полезная идея.'
        )
        IdeaLike.objects.create(idea=self.public_idea, user=self.bob)
        Favorite.objects.create(idea=self.public_idea, user=self.bob)
        Project.objects.create(
            creator=self.alice,
            title='Проект для проверки метрик',
            description=PROJECT_DESCRIPTION,
            status=Project.ACTIVE,
        )

        data = admin_dashboard({'user': self.admin})
        groups = {group['title']: group for group in data['groups']}

        def metric(title, label):
            return next(
                item for item in groups[title]['metrics'] if item['label'] == label
            )

        self.assertEqual(metric('Аудитория', 'Пользователи')['value'], 4)
        self.assertEqual(metric('Идеи', 'Всего идей')['value'], 2)
        self.assertEqual(metric('Идеи', 'Опубликовано')['value'], 2)
        self.assertEqual(metric('Проекты', 'Всего проектов')['value'], 1)
        self.assertEqual(metric('Проекты', 'В работе')['value'], 1)
        self.assertEqual(metric('Сообщество', 'Комментарии')['value'], 1)
        self.assertEqual(metric('Сообщество', 'Лайки')['value'], 1)
        self.assertEqual(metric('Сообщество', 'В избранном')['value'], 1)
        self.assertEqual(
            metric('Сообщество', 'Категории')['value'],
            Category.objects.count(),
        )

    def test_online_chart_covers_last_seven_days(self):
        today = timezone.localdate()
        now = timezone.now()
        for offset, users in ((0, (self.alice, self.bob)), (3, (self.carol,))):
            for user in users:
                UserActivity.objects.create(
                    user=user,
                    date=today - timedelta(days=offset),
                    first_seen=now,
                    last_seen=now,
                    requests=1,
                )

        online = admin_dashboard({'user': self.admin})['online']

        self.assertEqual(len(online['points']), 7)
        self.assertEqual(online['points'][-1]['date'], today)
        self.assertEqual(online['points'][-1]['value'], 2)
        self.assertEqual(online['points'][-4]['value'], 1)
        self.assertEqual(online['today'], 2)
        self.assertEqual(online['peak'], 2)
        self.assertEqual(online['now'], 3)
        self.assertEqual(len(online['chart']['points']), 7)
        self.assertEqual(len(online['chart']['grid']), 5)
        self.assertTrue(online['chart']['area'].startswith('M '))
        self.assertEqual(len(online['chart']['line'].split()), 7)

    def test_non_staff_cannot_open_dashboard(self):
        self.login(self.alice)
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_create_admin_command_is_idempotent(self):
        output = StringIO()
        call_command(
            'create_admin',
            username='rootadmin',
            email='root@example.com',
            password=PASSWORD,
            stdout=output,
        )
        user = User.objects.get(username='rootadmin')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertNotIn(PASSWORD, output.getvalue())

        call_command(
            'create_admin',
            username='rootadmin',
            email='root@example.com',
            password='AnotherStr0ng!2025',
            stdout=StringIO(),
        )
        user.refresh_from_db()
        self.assertEqual(User.objects.filter(username='rootadmin').count(), 1)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.email, 'root@example.com')

    def test_create_admin_does_not_touch_existing_superuser(self):
        output = StringIO()
        call_command(
            'create_admin',
            username=self.admin.username,
            email='changed@example.com',
            password='AnotherStr0ng!2025',
            stdout=output,
        )
        self.admin.refresh_from_db()
        self.assertIn('уже существует', output.getvalue())
        self.assertTrue(self.admin.check_password(PASSWORD))
        self.assertEqual(self.admin.email, 'siteadmin@example.com')

    def test_create_admin_refuses_existing_regular_user(self):
        with self.assertRaises(CommandError):
            call_command(
                'create_admin',
                username=self.alice.username,
                email='alice-admin@example.com',
                password=PASSWORD,
                stdout=StringIO(),
            )
        self.alice.refresh_from_db()
        self.assertFalse(self.alice.is_staff)
        self.assertFalse(self.alice.is_superuser)
        self.assertTrue(self.alice.check_password(PASSWORD))
        self.assertEqual(self.alice.email, 'alice@example.com')

    def test_create_admin_rejects_weak_password(self):
        with self.assertRaises(CommandError):
            call_command(
                'create_admin',
                username='weakadmin',
                email='weak@example.com',
                password='123',
                stdout=StringIO(),
            )
        self.assertFalse(User.objects.filter(username='weakadmin').exists())

    def test_admin_registers_every_project_model(self):
        registered = set(admin.site._registry)
        for model in (
            User,
            UserProfile,
            Category,
            Idea,
            IdeaLike,
            Favorite,
            Comment,
            Project,
            ProjectMember,
            UserActivity,
        ):
            with self.subTest(model=model.__name__):
                self.assertIn(model, registered)

    def test_admin_changelists_render(self):
        self.login(self.admin)
        for model in (
            User,
            UserProfile,
            Category,
            Idea,
            IdeaLike,
            Favorite,
            Comment,
            Project,
            ProjectMember,
            UserActivity,
        ):
            with self.subTest(model=model.__name__):
                opts = model._meta
                url = reverse(
                    f'admin:{opts.app_label}_{opts.model_name}_changelist'
                )
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)


class OnlineTrackingTests(BaseTestCase):
    """The presence middleware must feed the seven-day chart."""

    def test_authenticated_visit_is_recorded_once_per_minute(self):
        self.login(self.alice)
        self.client.get(reverse('ideas:home'))

        activity = UserActivity.objects.get(user=self.alice)
        self.assertEqual(activity.date, timezone.localdate())
        self.assertEqual(activity.requests, 1)
        self.assertGreaterEqual(activity.last_seen, activity.first_seen)

        self.client.get(reverse('ideas:home'))
        activity.refresh_from_db()
        self.assertEqual(activity.requests, 1)

    def test_visit_is_recorded_after_throttle_window(self):
        self.login(self.alice)
        self.client.get(reverse('ideas:home'))

        session = self.client.session
        session['online_tracked_at'] = timezone.now().timestamp() - 120
        session.save()

        self.client.get(reverse('ideas:home'))
        activity = UserActivity.objects.get(user=self.alice)
        self.assertEqual(activity.requests, 2)

    def test_anonymous_visits_are_not_recorded(self):
        self.client.get(reverse('ideas:home'))
        self.assertFalse(UserActivity.objects.exists())


class SeedIdeaMixCommandTests(BaseTestCase):
    demo_category_slugs = {
        'technology',
        'ai-ml',
        'business',
        'education',
        'design',
        'health',
        'environment',
        'productivity',
        'gaming',
        'community',
    }

    def run_seed(self):
        output = StringIO()
        call_command('seed_ideamix', stdout=output, stderr=StringIO())
        return output.getvalue()

    def test_seed_creates_expected_demo_data(self):
        self.run_seed()

        demo_users = User.objects.filter(username__startswith='demo_')
        self.assertEqual(demo_users.count(), 15)
        self.assertFalse(demo_users.filter(is_staff=True).exists())
        self.assertFalse(demo_users.filter(is_superuser=True).exists())
        for user in demo_users:
            with self.subTest(user=user.username):
                self.assertFalse(user.has_usable_password())
                self.assertTrue(hasattr(user, 'profile'))
                self.assertTrue(user.profile.bio)

        self.assertEqual(
            Category.objects.filter(slug__in=self.demo_category_slugs).count(),
            10,
        )

        demo_ideas = Idea.objects.filter(author__username__startswith='demo_')
        self.assertEqual(demo_ideas.count(), 20)
        self.assertEqual(
            set(demo_ideas.values_list('category__slug', flat=True)),
            self.demo_category_slugs,
        )
        self.assertEqual(
            set(demo_ideas.values_list('status', flat=True)),
            {Idea.DRAFT, Idea.PUBLISHED, Idea.IN_PROGRESS, Idea.COMPLETED},
        )
        self.assertTrue(demo_ideas.filter(visibility=Idea.PRIVATE).exists())
        self.assertFalse(demo_ideas.filter(tags='').exists())
        self.assertTrue(all(not idea.cover_image for idea in demo_ideas))
        self.assertFalse(demo_ideas.filter(title='github').exists())

        self.assertEqual(
            Project.objects.filter(creator__username__startswith='demo_').count(),
            10,
        )
        self.assertEqual(
            Comment.objects.filter(author__username__startswith='demo_').count(),
            30,
        )
        self.assertEqual(
            IdeaLike.objects.filter(user__username__startswith='demo_').count(),
            40,
        )
        self.assertEqual(
            Favorite.objects.filter(user__username__startswith='demo_').count(),
            15,
        )
        self.assertGreater(
            ProjectMember.objects.filter(
                project__creator__username__startswith='demo_'
            ).count(),
            20,
        )

        for project in Project.objects.filter(
            creator__username__startswith='demo_'
        ):
            with self.subTest(project=project.title):
                self.assertTrue(
                    project.memberships.filter(
                        user=project.creator, role=ProjectMember.OWNER
                    ).exists()
                )
                self.assertTrue(project.ideas.exists())

        self.assertEqual(
            IdeaLike.objects.values('idea', 'user').distinct().count(),
            IdeaLike.objects.count(),
        )
        self.assertEqual(
            Favorite.objects.values('idea', 'user').distinct().count(),
            Favorite.objects.count(),
        )

    def test_seed_is_idempotent(self):
        self.run_seed()
        totals = {
            'users': User.objects.count(),
            'categories': Category.objects.count(),
            'ideas': Idea.objects.count(),
            'projects': Project.objects.count(),
            'comments': Comment.objects.count(),
            'likes': IdeaLike.objects.count(),
            'favorites': Favorite.objects.count(),
            'members': ProjectMember.objects.count(),
        }

        output = self.run_seed()
        self.assertEqual(
            totals,
            {
                'users': User.objects.count(),
                'categories': Category.objects.count(),
                'ideas': Idea.objects.count(),
                'projects': Project.objects.count(),
                'comments': Comment.objects.count(),
                'likes': IdeaLike.objects.count(),
                'favorites': Favorite.objects.count(),
                'members': ProjectMember.objects.count(),
            },
        )
        for label in ('Идеи', 'Проекты', 'Комментарии', 'Лайки', 'Избранное'):
            with self.subTest(label=label):
                self.assertIn(f'{label}: создано 0', output)

    def test_seed_keeps_existing_demo_account_password(self):
        demo = User.objects.create_user(
            'demo_alexey', 'existing@example.com', PASSWORD
        )
        self.run_seed()
        demo.refresh_from_db()
        self.assertTrue(demo.check_password(PASSWORD))
        self.assertFalse(demo.is_staff)
        self.assertFalse(demo.is_superuser)
        self.assertEqual(
            User.objects.filter(username='demo_alexey').count(),
            1,
        )
