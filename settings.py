"""
Django settings
"""

import os

from utils import read_file  # pylint: disable=import-error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST_ADDRESS = f'{read_file(".host_address", os.getcwd())}'

ALLOWED_HOSTS = ['192.168.8.24']

# PostgreSQL
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
