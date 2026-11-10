"""Safely create the IdeaMix superuser account."""

import getpass
import os
import sys

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

DEFAULT_USERNAME = 'max'
DEFAULT_EMAIL = 'max@ideamix.local'


class Command(BaseCommand):
    help = (
        'Интерактивно создаёт суперпользователя IdeaMix. '
        'Существующие аккаунты не изменяются.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default=DEFAULT_USERNAME,
            help=f'Логин администратора (по умолчанию: {DEFAULT_USERNAME}).',
        )
        parser.add_argument(
            '--email',
            default=DEFAULT_EMAIL,
            help=f'Email администратора (по умолчанию: {DEFAULT_EMAIL}).',
        )
        parser.add_argument(
            '--password',
            default='',
            help=(
                'Пароль для неинтерактивного запуска. Не рекомендуется: '
                'он может остаться в истории команд. Лучше ввести пароль '
                'интерактивно или через DJANGO_SUPERUSER_PASSWORD.'
            ),
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Не задавать вопросов. Пароль берётся из --password или окружения.',
        )

    def handle(self, *args, **options):
        username = options['username'].strip()
        email = options['email'].strip().lower()
        noinput = options['noinput']

        if not username:
            if noinput:
                raise CommandError('Укажите логин через --username.')
            username = input('Имя пользователя: ').strip()
        if not username:
            raise CommandError('Логин не может быть пустым.')

        existing = User.objects.filter(username=username).first()
        if existing is not None:
            if existing.is_superuser and existing.is_staff:
                self.stdout.write(self.style.SUCCESS(
                    f'Суперпользователь «{username}» уже существует. '
                    'Его пароль и данные не изменены.'
                ))
                return
            raise CommandError(
                f'Пользователь «{username}» уже существует, но не является '
                'суперпользователем. Выберите другой логин или измените права '
                'через Django Admin. Данные пользователя не изменены.'
            )

        if not email:
            if noinput:
                raise CommandError('Укажите email через --email.')
            email = input('Email: ').strip().lower()
        if not email:
            raise CommandError('Email не может быть пустым.')

        password = (
            options['password']
            or os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        )
        if not password:
            if noinput or not sys.stdin.isatty():
                raise CommandError(
                    'Пароль не задан. Используйте --password, переменную '
                    'DJANGO_SUPERUSER_PASSWORD или интерактивный терминал.'
                )
            password = getpass.getpass('Пароль: ')
            confirmation = getpass.getpass('Повторите пароль: ')
            if password != confirmation:
                raise CommandError('Пароли не совпадают.')

        candidate = User(username=username, email=email)
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError(
                'Пароль слишком слабый: ' + ' '.join(exc.messages)
            ) from exc

        with transaction.atomic():
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Суперпользователь «{username}» создан. '
            'Пароль сохранён в виде хеша и не выводится.'
        ))
        self.stdout.write(
            'Откройте http://127.0.0.1:8000/admin/ и войдите под этим аккаунтом.'
        )
