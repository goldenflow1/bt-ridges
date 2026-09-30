INSTALLED_APPS = ['clinic']
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'practice',
             'USER': 'practice', 'PASSWORD': 'practice-local', 'HOST': 'postgres'}}
SECRET_KEY = 'clinic-task-development-only'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
