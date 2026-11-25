"""Application-wide template metadata."""
from django.conf import settings


def app_version(request):
    context={'app_version':settings.APP_VERSION}
    from news.access import is_reviewer
    if is_reviewer(request.user):
        from news.inbox import unread_events
        context['news_reviewer']=True
        context['news_unread']=unread_events(request.user).count()
    return context
