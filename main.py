# Django specific settings
import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


application = get_wsgi_application()

# Your application specific imports
from orm.models import Album  # NOQA


if __name__ == '__main__':
    album = None

    # Add a record
    if not Album.objects.filter(artist="Yes"):
        album = Album(title="Test", artist="Yes", comment="Test comment", label="Polydor")
        album.save()

    # Application logic
    # retrieved_cd = Album.objects.all()
    retrieved = Album.objects.filter(artist=album.artist if album else "Yes")

    for album in retrieved:
        print(f"{repr({k: v for k, v in album.__dict__.items() if k not in ['_state', 'len']})}")
