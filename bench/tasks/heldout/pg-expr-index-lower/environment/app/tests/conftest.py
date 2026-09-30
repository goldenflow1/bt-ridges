import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','library.settings')
import django
django.setup()
import pytest
from django.core.management import call_command
from django.db import connection


@pytest.fixture
def db():
    call_command('migrate',verbosity=0)
    with connection.cursor() as cursor:
        cursor.execute('TRUNCATE library_member RESTART IDENTITY CASCADE')
    yield
