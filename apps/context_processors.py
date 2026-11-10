"""Template context shared by every page."""

from django.core.cache import cache

from .models import Category


def navigation(request):
    """Expose a short category list for the header and footer menus."""
    categories = cache.get('nav_categories')
    if categories is None:
        categories = list(Category.objects.all()[:8])
        cache.set('nav_categories', categories, 120)
    return {'nav_categories': categories}
