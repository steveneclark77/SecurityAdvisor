from django.apps import AppConfig
from django.db.models.signals import post_migrate, post_save


class NewsConfig(AppConfig):
    name='news'

    def ready(self):
        from .models import Issue, IssueProposal
        post_migrate.connect(seed_reviewers,sender=self,dispatch_uid='news_reviewers')
        post_save.connect(profile_changed,sender=Issue,dispatch_uid='news_issue_profile')
        post_save.connect(proposal_created,sender=IssueProposal,dispatch_uid='news_proposal_inbox')


def seed_reviewers(**kwargs):
    from django.contrib.auth.models import Group, Permission
    from .access import REVIEWER_GROUP
    from .models import MatchingConfiguration
    group,created=Group.objects.get_or_create(name=REVIEWER_GROUP)
    if created:
        group.permissions.add(*Permission.objects.filter(content_type__app_label='news',codename__in=[
            'view_issue','view_issueversion','view_article','view_articlerevision','view_issueproposal',
            'view_analysisresult','view_analysisrun','add_matchfeedback','view_matchassessment',
            'add_issue','change_issue','add_issueversion','add_issuearticlelink','add_proposaldecision']))
    MatchingConfiguration.objects.get_or_create(pk=1)


def profile_changed(sender,instance,update_fields=None,**kwargs):
    if instance.current_version_id and (update_fields is None or 'current_version' in update_fields):
        from .match_cache import refresh_profile
        refresh_profile(instance.pk)


def proposal_created(sender,instance,created,**kwargs):
    if created:
        from .models import InboxEvent
        InboxEvent.objects.get_or_create(key=f'pending:{instance.pk}',defaults={
            'kind':'pending','proposal':instance,'title':instance.content.get('name','Potential security issue')[:500]})
        from .models import MatchQueue
        MatchQueue.objects.get_or_create(proposal=instance)
        from .matching import assess
        assess(instance)
