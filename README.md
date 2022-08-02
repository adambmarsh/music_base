# music_base #

This repository contains code for command-line tool to populate a PostgreSQL
database with music metainfo. The information is harvested from a potentially
unlimited number of .flac, .ogg, .mp3 files help in any number of directories as
well as from directory-specific .yml files.

The ultimate goal is to provide a web-GUI with a mechanism to query the
database.

# Status #

Work in progress.

The existing code works, but there is no provision for a deployment package.

The code uses Python (3.10+) to traverse directories, extracting metadata and
writing that metadata to a database asynchronously (uses coroutines).

