"""Shared unread/task relevance for badges, inboxes and notifications."""
from .models import InboxEvent


def unread_events(user):
    return InboxEvent.objects.exclude(receipts__user=user).exclude(kind='pending',proposal__matching_work__status='resolved')
