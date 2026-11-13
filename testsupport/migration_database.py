"""Subprocess harness for migrations against an isolated database on either backend."""
ISOLATED_DATABASE = r'''
import os
import tempfile
os.environ['DJANGO_SECRET_KEY'] = 'synthetic-migration-test'
import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from contextlib import contextmanager
from uuid import uuid4

@contextmanager
def temporary_database():
    from django.db import connection
    if connection.vendor == 'sqlite':
        with tempfile.TemporaryDirectory(prefix='synthetic-migration-') as folder:
            settings.DATABASES['default']['NAME'] = folder + '/migration.sqlite3'
            connection.settings_dict['NAME'] = settings.DATABASES['default']['NAME']
            yield
            connection.close()
    else:
        name = 'test_app_migration_' + uuid4().hex
        with connection._nodb_cursor() as cursor:
            cursor.execute('CREATE DATABASE ' + connection.ops.quote_name(name))
        settings.DATABASES['default']['NAME'] = name
        connection.settings_dict['NAME'] = name
        try:
            yield
        finally:
            connection.close()
            with connection._nodb_cursor() as cursor:
                cursor.execute('DROP DATABASE ' + connection.ops.quote_name(name))

django.setup()
'''
