"""Align model names and field names with the IdeaMix domain language."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apps', '0002_seed_categories_and_profiles'),
    ]

    operations = [
        migrations.RenameModel(old_name='Profile', new_name='UserProfile'),
        migrations.RenameModel(old_name='Like', new_name='IdeaLike'),
        migrations.RenameField(
            model_name='idea',
            old_name='content',
            new_name='description',
        ),
        migrations.RenameField(
            model_name='comment',
            old_name='body',
            new_name='text',
        ),
        migrations.RenameField(
            model_name='project',
            old_name='owner',
            new_name='creator',
        ),
    ]
