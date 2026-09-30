INSTALLED_APPS = ['library']
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':'practice','USER':'practice',
             'PASSWORD':'practice-local','HOST':'postgres'}}
SECRET_KEY = 'library-development-only'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MIGRATION_MODULES = {'library': 'library.schema_migrations'}
