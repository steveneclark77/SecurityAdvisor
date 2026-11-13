"""Display sorting happens before pagination and never selects arbitrary ORM fields."""
from django.test import TestCase
from django.urls import reverse
from inventory.models import InventoryItem
from testsupport.csrf_cases import workflow_fixture


class TableSortingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f=workflow_fixture()
        InventoryItem.objects.bulk_create([InventoryItem(customer=cls.f.customer,kind='device',name=f'Sort {number}',quantity=number) for number in range(60,0,-1)])

    def setUp(self):
        self.client.force_login(self.f.user)
        self.url=reverse('inventory_detail',args=[self.f.customer.pk])

    def test_natural_name_sort_spans_pages_and_preserves_filters(self):
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'0'})
        self.assertEqual([row['item'].name for row in response.context['records']][:3],['Sort 1','Sort 2','Sort 3'])
        self.assertEqual(response.context['records'][-1]['item'].name,'Sort 50')
        self.assertIn('sort=0',response.context['next_url'])
        self.assertIn('q=Sort',response.context['next_url'])
        self.assertIn('sort=0',response.context['records'][0]['url'])
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'0','page':2})
        self.assertEqual(response.context['records'][0]['item'].name,'Sort 51')
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'-0'})
        self.assertEqual(response.context['records'][0]['item'].name,'Sort 60')
        self.assertEqual(response.context['sort_headers'][0]['order'],'descending')

    def test_quantity_owner_and_state_use_display_values(self):
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'-1'})
        self.assertEqual(response.context['records'][0]['item'].quantity,60)
        self.f.operation.owner=self.f.person
        self.f.operation.state='reported'
        self.f.operation.provenance='Synthetic fixture'
        self.f.operation.save()
        response=self.client.get(self.url,{'sort':'2'})
        self.assertEqual(response.context['records'][0]['item'].owner,self.f.person)
        response=self.client.get(self.url,{'sort':'3'})
        self.assertEqual(response.context['records'][0]['item'].state,'reported')
        self.assertEqual(len(response.context['sort_headers']),4)
        self.assertNotIn('Action',[header['label'] for header in response.context['sort_headers']])

    def test_bad_sort_is_ignored_and_get_does_not_write(self):
        before=self.f.customer.inventory_events.count()
        for invalid in ['999','owner__customer','0; DROP TABLE inventory_inventoryitem','9'*5000]:
            response=self.client.get(self.url,{'sort':invalid})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['sort'],'')
        self.assertEqual(self.f.customer.inventory_events.count(),before)

    def test_large_numeric_text_is_safe_to_sort(self):
        from .table_sorting import natural_key
        self.assertLess(natural_key('Value 2'),natural_key('Value 10'))
        self.assertLess(natural_key('9'*5000),natural_key('1'+'0'*5000))

    def test_admin_computed_review_status_preserves_legacy_display(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from django.utils import timezone
        from news.models import Source,Scan,Issue,Review
        from news.admin import IssueAdmin
        source,_=Source.objects.get_or_create(url='https://example.test/',defaults={'name':'Synthetic sorting publisher','feed_url':'https://feeds.feedburner.com/synthetic-sort-fixture','enabled':False})
        scan=Scan.objects.create(source=source,feed_url=source.feed_url)
        issue=Issue.objects.create(source=source,first_scan=scan,identity='legacy-sort-check',last_seen_at=timezone.now())
        review=Review.objects.create(issue=issue,actor=self.f.user,decision='ignore',rationale='Synthetic legacy review',issue_snapshot={'name':'Preserved legacy snapshot'})
        request=RequestFactory().get('/admin/news/issue/')
        request.user=self.f.user
        screen=IssueAdmin(Issue,admin.site)
        row=screen.get_queryset(request).get(pk=issue.pk)
        self.assertEqual(screen.review_status(row),issue.review_status())
        review.refresh_from_db()
        self.assertEqual(review.issue_snapshot,{'name':'Preserved legacy snapshot'})
