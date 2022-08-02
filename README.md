# music_base

Music Base (musics_base) is a personal experiment to build a solution that makes it easier to
search through a music collection and automatically create playlists. 

The driver behind is project was frustration with the limitations of the search
functionality in VLC and on my NAS (QNAP) and Kodi.  

## Status

The project thus far has offered good scope for experimenting with: 

- Django’s ORM 
- asynchronous processing (coroutines)

Planned enhancements:

- create a Web GUI with a search box and an area to display the search results: 
- search to be text- and regex-based
- build a playlist from the query results
- play the playlist on a music player – either local or a network resource

