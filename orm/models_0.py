from django.db import models


# Create your models here.
class Album(models.Model):
    id = models.BigIntegerField(primary_key=True)
    title = models.TextField(blank=True, null=True)
    artist = models.TextField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    label = models.TextField(blank=True, null=True)
    path = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'album'


class Song(models.Model):
    title = models.TextField(blank=True, null=True)
    id = models.BigIntegerField(primary_key=True)
    track_id = models.IntegerField(blank=True, null=True)
    album = models.ForeignKey(Album, models.DO_NOTHING, blank=True, null=True)
    genre = models.TextField(blank=True, null=True)
    artist = models.TextField(blank=True, null=True)  # This field type is a guess.
    composer = models.TextField(blank=True, null=True)
    performer = models.TextField(blank=True, null=True)
    file = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'song'
