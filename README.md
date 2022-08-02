# music_base #

Music base is a personal experiment to build a solution that makes it easier to
find search through a music collection and automatically create playlists. 

The driver behind is project was frustration with the limitations of the search
functionality in VLC and on my NAS (QNAP) and Kodi.  

# Status #

Work in progress.

The existing code works, but there is no provision for a deployment package.

The code uses Python (3.10+) to traverse directories, extracting metadata and
writing that metadata to a database asynchronously (uses coroutines).

