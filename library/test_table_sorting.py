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

    def test_alphabetical_name_sort_spans_pages_and_preserves_filters(self):
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'0'})
        self.assertEqual([row['item'].name for row in response.context['records']][:3],['Sort 1','Sort 10','Sort 11'])
        self.assertEqual(response.context['records'][-1]['item'].name,sorted(f'Sort {n}' for n in range(1,61))[49])
        self.assertIn('sort=0',response.context['next_url'])
        self.assertIn('q=Sort',response.context['next_url'])
        self.assertIn('sort=0',response.context['records'][0]['url'])
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'0','page':2})
        self.assertEqual(response.context['records'][0]['item'].name,sorted(f'Sort {n}' for n in range(1,61))[50])
        response=self.client.get(self.url,{'kind':'device','q':'Sort','sort':'-0'})
        self.assertEqual(response.context['records'][0]['item'].name,'Sort 9')
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

    def test_all_inventory_columns_break_ties_by_name_then_id_across_pages(self):
        # Reverse insertion order makes an accidental ID-only fallback visible.
        items = InventoryItem.objects.bulk_create([
            InventoryItem(customer=self.f.customer, kind='device', name=f'Tie {number:03}', quantity=2)
            for number in range(60, 0, -1)])
        duplicate = InventoryItem.objects.create(customer=self.f.customer, kind='device',
                                                name='Tie 001', quantity=2)
        expected = sorted([*items, duplicate], key=lambda item:(item.name.lower(), item.pk))
        for column in range(1,4):
            for direction in ['', '-']:
                actual = []
                for page in [1,2]:
                    response = self.client.get(self.url, {'q':'Tie ', 'sort':direction+str(column), 'page':page})
                    actual.extend(row['item'].pk for row in response.context['records'])
                with self.subTest(column=column, direction=direction):
                    self.assertEqual(actual, [item.pk for item in expected])

    def test_compound_sort_retains_quantity_before_name(self):
        for name, quantity in [('Compound Zulu',2),('Compound Alpha',2),('Compound Bravo',10)]:
            InventoryItem.objects.create(customer=self.f.customer, kind='device', name=name, quantity=quantity)
        for token, expected in [('1',['Compound Alpha','Compound Zulu','Compound Bravo']),
                                ('-1',['Compound Bravo','Compound Alpha','Compound Zulu'])]:
            response = self.client.get(self.url, {'q':'Compound ', 'sort':token})
            self.assertEqual([row['item'].name for row in response.context['records']], expected)

    def test_admin_column_ties_use_name_in_both_directions(self):
        from django.contrib import admin
        from django.test import RequestFactory
        from news.admin import SourceAdmin
        from news.models import Source
        Source.objects.bulk_create([
            Source(url='https://zulu.example.test/', name='Tie Zulu', enabled=False),
            Source(url='https://alpha.example.test/', name='Tie Alpha', enabled=False)])
        screen = SourceAdmin(Source, admin.site)
        for direction in ['', '-']:
            request = RequestFactory().get('/admin/news/source/', {'o':direction+'3'})
            request.user = self.f.user
            changelist = screen.get_changelist_instance(request)
            rows = list(changelist.queryset.filter(name__startswith='Tie '))
            self.assertEqual([row.name for row in rows], ['Tie Alpha','Tie Zulu'])

    def test_bad_sort_is_ignored_and_get_does_not_write(self):
        before=self.f.customer.inventory_events.count()
        for invalid in ['999','owner__customer','0; DROP TABLE inventory_inventoryitem','9'*5000]:
            response=self.client.get(self.url,{'sort':invalid})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['sort'],'')
        self.assertEqual(self.f.customer.inventory_events.count(),before)

    def test_sort_only_materializes_and_formats_one_page(self):
        from unittest.mock import Mock
        from django.db import connection
        from django.db.models import F
        from django.db.models.query import QuerySet
        from django.test.utils import CaptureQueriesContext
        from .record_browser import page_selection
        rows = Mock(side_effect=lambda item: (item.name, []))
        queryset = InventoryItem.objects.filter(customer=self.f.customer, name__startswith='Sort ')
        with CaptureQueriesContext(connection) as queries:
            browser = page_selection(queryset, {'sort':'0', 'page':'2'}, {},
                                     row_values=rows, ordering=[[F('quantity')]])
        self.assertIsInstance(browser['page'].paginator.object_list, QuerySet)
        self.assertIsNone(queryset._result_cache)
        self.assertEqual(rows.call_count, 10)
        self.assertEqual([row['item'].quantity for row in browser['records']], list(range(51,61)))
        self.assertEqual(len(queries), 2)
        self.assertIn('COUNT(', queries[0]['sql'])
        self.assertIn('LIMIT 10 OFFSET 50', queries[1]['sql'])
        self.assertIn('ORDER BY', queries[1]['sql'])

    def test_all_browser_columns_execute_in_database(self):
        from engagements.browsers import assessment_browser, evidence_browser, contact_browser
        from engagements.models import Contact
        from inventory.explorer import explorer_context
        browsers = [
            (lambda params: explorer_context(self.f.customer, params), 4),
            (lambda params: assessment_browser(self.f.assessment, params), 5),
            (lambda params: contact_browser(Contact.objects.filter(pk=self.f.person.pk), params), 4),
            (lambda params: contact_browser(self.f.engagement.contact_links.all(), params,
                                           engagement=self.f.engagement), 4),
        ]
        for collection in ['requests', 'evidence', 'findings']:
            browsers.append((lambda params, collection=collection: evidence_browser(
                self.f.engagement, {**params, 'collection':collection}), 4))
        for browser, count in browsers:
            for column in range(count):
                for direction in ['', '-']:
                    with self.subTest(browser=browser, column=column, direction=direction):
                        result = browser({'sort': direction + str(column)})
                        self.assertEqual(result['sort'], direction + str(column))
                        self.assertTrue(result['page'].paginator.object_list.ordered)

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
