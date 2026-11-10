"""Signal handlers for IdeaMix."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid='create_profile')
def create_profile(sender, instance, created, **kwargs):
    """Every user gets a profile right after registration."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
