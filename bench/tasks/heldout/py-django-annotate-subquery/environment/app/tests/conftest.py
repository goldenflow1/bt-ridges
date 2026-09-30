import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clinic.settings')
import django
django.setup()
import pytest
from django.db import connection, transaction


@pytest.fixture
def conn():
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE doctors, sessions, appointments RESTART IDENTITY CASCADE')
            yield cursor
        transaction.set_rollback(True)
