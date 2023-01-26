import os

from utils import read_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST_ADDRESS = f'{read_file(".host_address", os.getcwd())}'

# PostreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'music',
        'USER': 'postgres',
        'PASSWORD': 'postgres',  # 'bromberg58'
        'HOST': HOST_ADDRESS,  # '127.0.0.1'
        'PORT': '5432',
    }
}

INSTALLED_APPS = (
    'orm',
)

SECRET_KEY = 'django-insecure-$4fy=p%n8^d(*wzxk32ylu!x)keef&463sl#%3_c6can@n5=-%'
