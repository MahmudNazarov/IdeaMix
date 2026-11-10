"""Forms for IdeaMix."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Category, Comment, Idea, Project, ProjectMember, UserProfile
from .profanity import validate_no_profanity
from .utils import normalize_tags, split_tags


class StyledFormMixin:
    """Attach consistent CSS classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'checkbox-input')
            elif isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
                widget.attrs.setdefault('class', 'file-input')
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'input input-select')
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault('class', 'input input-textarea')
            else:
                widget.attrs.setdefault('class', 'input')
            if field.required:
                widget.attrs.setdefault('aria-required', 'true')
            if field.help_text and not isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('aria-describedby', f'id_{name}_help')


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(label='Email', max_length=254, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Имя пользователя'
        self.fields['username'].help_text = (
            'Только буквы, цифры и символы @/./+/-/_. Минимум 3 символа.'
        )
        self.fields['first_name'].label = 'Имя'
        self.fields['last_name'].label = 'Фамилия'
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['password1'].label = 'Пароль'
        self.fields['password1'].help_text = (
            'Минимум 8 символов, не только цифры и не слишком простой.'
        )
        self.fields['password2'].label = 'Повтор пароля'
        self.fields['password2'].help_text = 'Введите пароль ещё раз.'
        placeholders = {
            'username': 'Например, anna',
            'email': 'you@example.com',
            'first_name': 'Как к вам обращаться',
            'last_name': 'Фамилия',
            'password1': 'Придумайте надёжный пароль',
            'password2': 'Повторите пароль',
        }
        for name, placeholder in placeholders.items():
            self.fields[name].widget.attrs.setdefault('placeholder', placeholder)
        for name in ('username', 'email', 'first_name', 'last_name'):
            self.fields[name].widget.attrs.setdefault('autocomplete', 'off')
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        validate_no_profanity(username)
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Это имя пользователя уже занято.')
        return username

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        validate_no_profanity(first_name)
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        validate_no_profanity(last_name)
        return last_name

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Пользователь с таким email уже существует.')
        return email


class LoginForm(StyledFormMixin, AuthenticationForm):
    error_messages = {
        'invalid_login': 'Неверное имя пользователя или пароль.',
        'inactive': 'Этот аккаунт отключён.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Имя пользователя'
        self.fields['username'].widget.attrs.update(
            {'placeholder': 'Введите логин', 'autocomplete': 'username'}
        )
        self.fields['password'].label = 'Пароль'
        self.fields['password'].widget.attrs.update(
            {'placeholder': 'Введите пароль', 'autocomplete': 'current-password'}
        )


class ProfileForm(StyledFormMixin, forms.ModelForm):
    first_name = forms.CharField(label='Имя', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    email = forms.EmailField(label='Email', max_length=254, required=True)

    class Meta:
        model = UserProfile
        fields = ('bio', 'location', 'website', 'skills', 'avatar')
        widgets = {
            'bio': forms.Textarea(
                attrs={'rows': 4, 'placeholder': 'Расскажите, чем вы живёте и что создаёте'}
            ),
            'location': forms.TextInput(attrs={'placeholder': 'Ташкент, Узбекистан'}),
            'website': forms.TextInput(attrs={'placeholder': 'https://example.com'}),
            'skills': forms.TextInput(
                attrs={'placeholder': 'Python, Django, UX/UI, маркетинг'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = self.instance.user
        self.fields['first_name'].initial = user.first_name
        self.fields['last_name'].initial = user.last_name
        self.fields['email'].initial = user.email
        self.fields['email'].widget.attrs['placeholder'] = 'you@example.com'
        self.fields['first_name'].widget.attrs['placeholder'] = 'Имя'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Фамилия'

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.instance.user_id)
            .exists()
        ):
            raise ValidationError('Этот email уже занят.')
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        validate_no_profanity(first_name)
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        validate_no_profanity(last_name)
        return last_name

    def clean_skills(self):
        return normalize_tags(self.cleaned_data.get('skills', ''), max_tags=10)

    def clean_bio(self):
        bio = self.cleaned_data.get('bio', '').strip()
        return bio

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile.save()
        return profile


class IdeaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Idea
        fields = (
            'title',
            'short_description',
            'description',
            'category',
            'tags',
            'cover_image',
            'status',
            'visibility',
        )
        widgets = {
            'title': forms.TextInput(
                attrs={'placeholder': 'Например: приложение для обмена растениями'}
            ),
            'short_description': forms.TextInput(
                attrs={'placeholder': 'Одно предложение о сути идеи', 'maxlength': 220}
            ),
            'description': forms.Textarea(
                attrs={
                    'rows': 9,
                    'placeholder': (
                        'Опишите проблему, решение, целевую аудиторию '
                        'и чем вы можете быть полезны.'
                    ),
                }
            ),
            'tags': forms.TextInput(
                attrs={'placeholder': 'стартап, мобильное приложение, экология'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = 'Выберите категорию'
        self.fields['status'].initial = Idea.PUBLISHED
        self.fields['visibility'].help_text = (
            'Приватную идею видят только вы и участники связанных проектов.'
        )
        self.fields['cover_image'].help_text = (
            'Необязательно. JPG, PNG, WebP или GIF до 5 МБ.'
        )
        self.fields['cover_image'].widget.attrs['accept'] = 'image/*'
        self.fields['cover_image'].widget.attrs['data-preview-target'] = '#coverPreview'
        self.fields['description'].widget.attrs['maxlength'] = 12000

    def clean_title(self):
        title = ' '.join(self.cleaned_data['title'].split())
        if len(title) < 5:
            raise ValidationError('Название должно быть длиннее 4 символов.')
        if len(title) > 140:
            raise ValidationError('Название не должно превышать 140 символов.')
        return title

    def clean_short_description(self):
        short = ' '.join(self.cleaned_data['short_description'].split())
        if len(short) < 20:
            raise ValidationError('Краткое описание должно содержать минимум 20 символов.')
        return short

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        if len(description) < 30:
            raise ValidationError('Полное описание должно содержать минимум 30 символов.')
        return description

    def clean_tags(self):
        tags = split_tags(self.cleaned_data.get('tags', ''))
        if len(tags) > 5:
            raise ValidationError('Можно добавить не более 5 тегов.')
        for tag in tags:
            if len(tag) > 25:
                raise ValidationError('Каждый тег должен быть короче 25 символов.')
        return ', '.join(tags)

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        visibility = cleaned.get('visibility')
        if status == Idea.DRAFT and visibility == Idea.PRIVATE:
            # Drafts are private for their author anyway; this is valid.
            pass
        return cleaned


class CommentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Поделитесь мнением об идее…',
                    'maxlength': 1000,
                }
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['text'].label = ''

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if len(text) < 2:
            raise ValidationError('Комментарий слишком короткий.')
        return text


class ProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            'title',
            'description',
            'category',
            'related_idea',
            'status',
            'technologies',
            'needed_specialists',
            'repository_url',
            'demo_url',
            'visibility',
            'is_open',
        )
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Название проекта'}),
            'description': forms.Textarea(
                attrs={
                    'rows': 7,
                    'placeholder': 'Цель проекта, текущий этап и что уже сделано.',
                }
            ),
            'technologies': forms.TextInput(
                attrs={'placeholder': 'Python, Django, PostgreSQL, Figma'}
            ),
            'needed_specialists': forms.TextInput(
                attrs={'placeholder': 'Frontend-разработчик, продуктовый дизайнер'}
            ),
            'repository_url': forms.TextInput(
                attrs={'placeholder': 'https://github.com/username/project'}
            ),
            'demo_url': forms.TextInput(
                attrs={'placeholder': 'https://project.example.com'}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = 'Без категории'
        self.fields['status'].initial = Project.PLANNING
        related = Idea.objects.filter(author=user) if user else Idea.objects.none()
        if self.instance and self.instance.pk and self.instance.related_idea_id:
            related = related | Idea.objects.filter(pk=self.instance.related_idea_id)
        self.fields['related_idea'].queryset = related.distinct()
        self.fields['related_idea'].empty_label = 'Не связывать с идеей'
        self.fields['related_idea'].help_text = (
            'Выберите собственную идею, которая стала основой проекта.'
        )
        self.fields['technologies'].help_text = 'До 8 технологий через запятую.'
        self.fields['needed_specialists'].help_text = 'Кого вы ищете в команду.'

    def clean_title(self):
        title = ' '.join(self.cleaned_data['title'].split())
        if len(title) < 5:
            raise ValidationError('Название должно быть длиннее 4 символов.')
        return title

    def clean_description(self):
        description = self.cleaned_data['description'].strip()
        if len(description) < 30:
            raise ValidationError('Описание проекта должно содержать минимум 30 символов.')
        return description

    def clean_technologies(self):
        return normalize_tags(self.cleaned_data.get('technologies', ''), max_tags=8)

    def clean_needed_specialists(self):
        return normalize_tags(
            self.cleaned_data.get('needed_specialists', ''), max_tags=6
        )

    def clean_repository_url(self):
        url = self.cleaned_data.get('repository_url', '').strip()
        if url and not url.lower().startswith(('http://', 'https://')):
            raise ValidationError('Ссылка должна начинаться с http:// или https://.')
        return url

    def clean_demo_url(self):
        url = self.cleaned_data.get('demo_url', '').strip()
        if url and not url.lower().startswith(('http://', 'https://')):
            raise ValidationError('Ссылка должна начинаться с http:// или https://.')
        return url


class AddMemberForm(StyledFormMixin, forms.Form):
    username = forms.CharField(
        label='Имя пользователя',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Например, anna'}),
    )
    role = forms.ChoiceField(
        label='Роль',
        choices=ProjectMember.JOINABLE_ROLES,
        initial=ProjectMember.DEVELOPER,
    )

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username'].strip().lstrip('@')
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise ValidationError('Пользователь с таким логином не найден.')
        if self.project and ProjectMember.objects.filter(
            project=self.project, user=user
        ).exists():
            raise ValidationError('Этот пользователь уже участвует в проекте.')
        self.cleaned_user = user
        return user.username


class JoinProjectForm(StyledFormMixin, forms.Form):
    role = forms.ChoiceField(
        label='Ваша роль в команде',
        choices=ProjectMember.JOINABLE_ROLES,
        initial=ProjectMember.DEVELOPER,
    )


class IdeaAttachForm(StyledFormMixin, forms.Form):
    idea = forms.ModelChoiceField(
        label='Идея', queryset=Idea.objects.none(), empty_label='Выберите идею'
    )

    def __init__(self, *args, project=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Idea.objects.filter(author=user)
        if project:
            queryset = queryset.exclude(pk__in=project.ideas.values('pk'))
        self.fields['idea'].queryset = queryset
