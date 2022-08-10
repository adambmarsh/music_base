import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PostreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'music',
        'USER': 'postgres',
        'PASSWORD': 'postgres',  # 'bromberg58'
        'HOST': '192.168.8.24',  # '127.0.0.1'
        'PORT': '5432',
    }
}

INSTALLED_APPS = (
    'orm',
)

SECRET_KEY = 'django-insecure-$4fy=p%n8^d(*wzxk32ylu!x)keef&463sl#%3_c6can@n5=-%'
