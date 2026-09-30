import django
from django.conf import settings

settings.configure(INSTALLED_APPS=['app'], DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql',
                   'NAME': 'practice', 'USER': 'practice', 'PASSWORD': 'practice-local', 'HOST': 'postgres'}},
                   USE_TZ=True, SECRET_KEY='local-practice')
django.setup()
import pytest
from django.db import connection, transaction


@pytest.fixture
def conn():
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE customers, blocks RESTART IDENTITY CASCADE')
            yield cursor
        transaction.set_rollback(True)
