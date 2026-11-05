from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Control, Baseline, Profile, Modifier
from .services import create_baseline, approve_baseline

class LibraryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_library',verbosity=0)
        cls.user = get_user_model().objects.create_user('consultant',password='test-password-only',is_staff=True)
        cls.other = get_user_model().objects.create_user('outsider',password='test-password-only')
    def baseline(self):
        return create_baseline(user=self.user,version='v0-1',coverage_gaps='Starter content; framework mappings and scoring require review.')
    def test_seed_is_repeatable_and_preserves_edits(self):
        control=Control.objects.first(); control.title='Consultant edit'; control.save()
        call_command('seed_library',verbosity=0)
        self.assertEqual(Profile.objects.count(),20)
        self.assertEqual(Modifier.objects.count(),8)
        self.assertEqual(Control.objects.count(),14)
        control.refresh_from_db(); self.assertEqual(control.title,'Consultant edit')
        self.assertEqual(Baseline.objects.count(),0)
    def test_snapshot_survives_control_and_mapping_edits(self):
        baseline=self.baseline(); original=baseline.snapshot
        control=Control.objects.first(); control.title='Changed later'; control.save(); control.profiles.clear()
        baseline.refresh_from_db(); self.assertEqual(baseline.snapshot,original)
        self.assertNotEqual(baseline.snapshot['controls'][0]['title'],control.title)
    def test_approval_records_actor_and_rejects_repeat(self):
        baseline=self.baseline()
        approve_baseline(pk=baseline.pk,user=self.user,note='Reviewed starter scope and limitations.')
        baseline.refresh_from_db(); self.assertIsNotNone(baseline.approved_at)
        self.assertEqual(baseline.approved_by,self.user)
        with self.assertRaises(ValidationError): approve_baseline(pk=baseline.pk,user=self.user,note='Again')
    def test_invalid_approval_does_not_change_state(self):
        baseline=self.baseline()
        with self.assertRaises(ValidationError): approve_baseline(pk=baseline.pk,user=self.user,note=' ')
        baseline.refresh_from_db(); self.assertIsNone(baseline.approved_at)
    def test_nonstaff_cannot_create_or_approve(self):
        baseline=self.baseline()
        with self.assertRaises(PermissionError): create_baseline(user=self.other,version='bad',coverage_gaps='x')
        with self.assertRaises(PermissionError): approve_baseline(pk=baseline.pk,user=self.other,note='x')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertEqual(self.client.post(reverse('approve_baseline',args=[baseline.pk]),{'note':'x','confirmed':'on'}).status_code,302)
    def test_empty_library_cannot_be_snapshotted(self):
        Control.objects.all().delete()
        with self.assertRaises(ValidationError): self.baseline()
    def test_browser_workflow(self):
        self.assertEqual(self.client.get('/').status_code,302)
        self.client.force_login(self.user)
        response=self.client.get('/'); self.assertContains(response,'Build a baseline')
        response=self.client.post(reverse('create_baseline'),{'version':'v0-1','coverage_gaps':'Mappings require review.'})
        baseline=Baseline.objects.get(); self.assertRedirects(response,reverse('baseline_detail',args=[baseline.pk]))
        self.assertContains(self.client.get(response.url),'Review and approve')
        self.assertEqual(self.client.get(reverse('approve_baseline',args=[baseline.pk])).status_code,405)
        self.assertEqual(self.client.post(reverse('approve_baseline',args=[baseline.pk]),{'note':'Reviewed'}).status_code,400)
        response=self.client.post(reverse('approve_baseline',args=[baseline.pk]),{'note':'Reviewed scope','confirmed':'on','coverage_reviewed':'on','applicability_reviewed':'on','sources_reviewed':'on'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'This snapshot is preserved')
    def test_profile_filter_includes_universal_and_relevant_controls(self):
        self.client.force_login(self.user)
        profile=Profile.objects.get(name='Software, SaaS, and application development')
        response=self.client.get('/',{'profile':profile.pk})
        self.assertContains(response,'SW-01'); self.assertContains(response,'RC-01'); self.assertNotContains(response,'PAY-01')
    def test_approval_requires_csrf(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(reverse('approve_baseline',args=[self.baseline().pk]),{'note':'x','confirmed':'on'}).status_code,403)

    def test_captured_content_cannot_be_edited(self):
        baseline=self.baseline()
        baseline.coverage_gaps='Silently changed'
        with self.assertRaises(ValidationError): baseline.save()
        with self.assertRaises(ValidationError): baseline.delete()
    def test_approved_record_cannot_be_rewritten(self):
        baseline=self.baseline()
        baseline=approve_baseline(pk=baseline.pk,user=self.user,note='Original review')
        baseline.approval_note='Rewritten review'
        with self.assertRaises(ValidationError): baseline.save()

    def test_all_starter_controls_have_ordered_actionable_guidance(self):
        for control in Control.objects.all():
            actions = list(control.actions.all())
            self.assertGreaterEqual(len(actions), 3, control.code)
            self.assertEqual([a.position for a in actions], list(range(1, len(actions)+1)))
            for action in actions:
                self.assertTrue(action.instruction and action.applicability and action.verification)
        self.assertIn('phishing', Control.objects.get(code='PR-01').recommendation)

    def test_action_edits_do_not_rewrite_snapshot(self):
        baseline = self.baseline()
        original = baseline.snapshot
        action = Control.objects.get(code='PR-01').actions.first()
        action.instruction = 'Later edited action'
        action.save()
        baseline.refresh_from_db()
        self.assertEqual(original, baseline.snapshot)
        self.client.force_login(self.user)
        response = self.client.get(reverse('baseline_detail', args=[baseline.pk]))
        self.assertContains(response, 'FIDO2/WebAuthn')
        self.assertNotContains(response, 'Later edited action')

    def test_enrichment_upgrades_legacy_starters_but_preserves_custom_guidance(self):
        from library.management.commands.seed_library import ROWS
        from library.models import ControlAction
        ControlAction.objects.all().delete()
        for row in ROWS:
            Control.objects.filter(code=row[0]).update(recommendation=row[6])
        customized = Control.objects.get(code='PR-02')
        customized.recommendation = 'Customer-specific guidance'
        customized.save()
        baseline = self.baseline()
        before = baseline.snapshot
        call_command('seed_library')
        self.assertEqual(ControlAction.objects.count(), 0)
        call_command('seed_library', enrich_existing=True)
        self.assertEqual(Control.objects.get(code='PR-01').actions.count(), 7)
        customized.refresh_from_db()
        self.assertEqual(customized.recommendation, 'Customer-specific guidance')
        self.assertFalse(customized.actions.exists())
        count = ControlAction.objects.count()
        action = Control.objects.get(code='PR-01').actions.first()
        action.instruction = 'Consultant revised action'
        action.save()
        call_command('seed_library', enrich_existing=True)
        self.assertEqual(ControlAction.objects.count(), count)
        action.refresh_from_db()
        self.assertEqual(action.instruction, 'Consultant revised action')
        baseline.refresh_from_db()
        self.assertEqual(baseline.snapshot, before)

    def test_legacy_snapshots_without_actions_remain_readable(self):
        baseline = self.baseline()
        snapshot = baseline.snapshot
        for control in snapshot['controls']:
            control.pop('actions')
        Baseline.objects.filter(pk=baseline.pk).update(snapshot=snapshot)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('baseline_detail', args=[baseline.pk])), 'Baseline v0-1')

    def test_action_detail_is_visible_and_escaped(self):
        self.client.force_login(self.user)
        action = Control.objects.get(code='PR-01').actions.first()
        action.instruction = '<script>alert(1)</script>'
        action.save()
        response = self.client.get('/')
        self.assertContains(response, 'Specific actions')
        self.assertContains(response, 'Synced passkeys are not necessarily device-bound')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_revision_preserves_source_and_captures_working_edits(self):
        from .services import revise_draft
        source = self.baseline()
        original = source.snapshot
        control = Control.objects.first()
        control.title = 'Revised working title'
        control.save()
        replacement = revise_draft(pk=source.pk,user=self.user,version='v0-2',coverage_gaps='Updated limitations',revision_note='Clarify guidance before approval.')
        source.refresh_from_db()
        self.assertEqual(source.snapshot,original)
        self.assertEqual(source.status,'Superseded')
        self.assertEqual(source.superseded_by,replacement)
        self.assertEqual(source.superseded_actor,self.user)
        self.assertIsNotNone(source.superseded_at)
        self.assertEqual(replacement.snapshot['controls'][0]['title'],'Revised working title')
        self.assertIsNone(replacement.approved_at)
        with self.assertRaises(ValidationError): approve_baseline(pk=source.pk,user=self.user,note='Cannot approve old draft')
        with self.assertRaises(ValidationError): source.save()
        approve_baseline(pk=replacement.pk,user=self.user,note='Reviewed replacement separately')

    def test_revision_failures_leave_no_orphan_or_supersession(self):
        from .services import revise_draft
        from django.db import IntegrityError
        source = self.baseline()
        with self.assertRaises(ValidationError):
            revise_draft(pk=source.pk,user=self.user,version='v0-2',coverage_gaps='Gaps',revision_note=' ')
        self.assertEqual(Baseline.objects.count(),1)
        with self.assertRaises(IntegrityError):
            revise_draft(pk=source.pk,user=self.user,version=source.version,coverage_gaps='Gaps',revision_note='Duplicate version')
        source.refresh_from_db()
        self.assertIsNone(source.superseded_by_id)
        with self.assertRaises(PermissionError):
            revise_draft(pk=source.pk,user=self.other,version='v0-2',coverage_gaps='Gaps',revision_note='Unauthorized')

    def test_existing_replacement_and_revision_chain(self):
        from .services import supersede_draft, revise_draft
        first = self.baseline()
        second = create_baseline(user=self.user,version='v0-2',coverage_gaps='Gaps')
        with self.assertRaises(ValidationError):
            supersede_draft(pk=second.pk,replacement_pk=first.pk,user=self.user,note='Cannot point backwards')
        supersede_draft(pk=first.pk,replacement_pk=second.pk,user=self.user,note='Already captured replacement')
        third = revise_draft(pk=second.pk,user=self.user,version='v0-3',coverage_gaps='More review',revision_note='Another revision')
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.superseded_by,second)
        self.assertEqual(second.superseded_by,third)
        with self.assertRaises(ValidationError):
            revise_draft(pk=first.pk,user=self.user,version='unused',coverage_gaps='Gaps',revision_note='Stale form')
        approve_baseline(pk=third.pk,user=self.user,note='Final review')
        with self.assertRaises(ValidationError):
            revise_draft(pk=third.pk,user=self.user,version='unused',coverage_gaps='Gaps',revision_note='Approved source')

    def test_revision_browser_flow_and_superseded_ui(self):
        source = self.baseline()
        self.client.force_login(self.user)
        url = reverse('revise_baseline',args=[source.pk])
        self.assertContains(self.client.get(url),'Edit working controls')
        self.assertContains(self.client.get(reverse('baseline_detail',args=[source.pk])),'Revise this draft')
        response = self.client.post(url,{'version':'v0-2','coverage_gaps':'Revised gaps','revision_note':'Clarify actions'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Replaces')
        old_page = self.client.get(reverse('baseline_detail',args=[source.pk]))
        self.assertContains(old_page,'Superseded')
        self.assertNotContains(old_page,'Approve this version')
        self.assertEqual(self.client.get(url).status_code,409)
        self.assertEqual(self.client.post(url,{'version':'v0-3'}).status_code,409)
        self.assertContains(self.client.get('/'),'replacement')

    def test_supersession_requires_post_and_csrf(self):
        from django.test import Client
        source = self.baseline()
        replacement = create_baseline(user=self.user,version='v0-2',coverage_gaps='Gaps')
        self.client.force_login(self.user)
        url = reverse('supersede_baseline',args=[source.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(url,{'replacement':replacement.pk,'note':'test'}).status_code,403)
        self.assertEqual(client.post(reverse('revise_baseline',args=[source.pk]),{'version':'v0-3'}).status_code,403)
        response = self.client.post(url,{'replacement':replacement.pk,'note':'Previously captured revised snapshot'})
        self.assertEqual(response.status_code,302)
