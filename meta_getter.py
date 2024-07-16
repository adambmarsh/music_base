"""
This module contains code to retrieve music metadata.
"""

import argparse
import os
import pathlib
import re
import sys
from datetime import datetime

from discogs_wrapper import DV

from music_text_getter import MusicTextGetter  # pylint: disable=import-error
from utils import log_it, read_yaml, write_yaml_file, USE_FILE_EXTENSIONS  # pylint: disable=import-error

SCRIPT_DESCRIPTION = ""


class MetaGetter(MusicTextGetter):
    """
    This class encapsulates functionality to retrieve music metadata.
    """

    def __init__(self, dest_dir="", artist="", genre="", country="", query="", title="", release_id="", url="",
                 year=None, match=0):
        self._title = self.genre = self._artist = self._country = self._dir = self._data = self._release = \
            self._query = self._org_data_url = ""
        self._cfg = {}
        self._year = None
        self._match = 0

        self.release = release_id
        self.match = match
        self.data = ""
        self.dir = dest_dir
        self.year = year
        self.country = country
        self.artist, self.title = self.resolve_artist_and_title(artist, title)
        self.genre = genre
        self.query = query if query else ""
        script_dir = os.path.dirname(os.path.realpath(__file__))
        self.cfg = read_yaml(os.path.join(script_dir, "discogs.yml"))
        self.dclient = DV("/".join([self.cfg.get("app", 'my_app')]))

        super().__init__(query_str=self.query, album_title=self.title, album_artist=self.artist)
        self.org_data_url = self.parse_url(url)

    @property
    def data(self):  # pylint: disable=missing-function-docstring
        return self._data

    @data.setter
    def data(self, in_data):
        self._data = in_data

    @property
    def match(self):  # pylint: disable=missing-function-docstring
        return self._match

    @match.setter
    def match(self, in_match):
        self._match = int(in_match)

    @property
    def country(self):  # pylint: disable=missing-function-docstring
        return self._country

    @country.setter
    def country(self, in_country):
        self._country = in_country

    @property
    def dir(self):  # pylint: disable=missing-function-docstring
        return self._dir

    @dir.setter
    def dir(self, in_dir):
        self._dir = in_dir

    @property
    def release(self):  # pylint: disable=missing-function-docstring
        return self._release

    @release.setter
    def release(self, in_release):
        self._release = in_release

    @property
    def org_data_url(self):  # pylint: disable=missing-function-docstring
        return self._org_data_url

    @org_data_url.setter
    def org_data_url(self, in_url):
        self._org_data_url = in_url

    @property
    def year(self):  # pylint: disable=missing-function-docstring
        return self._year

    @year.setter
    def year(self, in_year):
        self._year = in_year

    @property
    def artist(self):  # pylint: disable=missing-function-docstring
        return self._artist

    @artist.setter
    def artist(self, in_artist):
        self._artist = in_artist

    @property
    def genre(self):  # pylint: disable=missing-function-docstring
        return self._genre

    @genre.setter
    def genre(self, in_genre):
        self._genre = in_genre

    @property
    def title(self):  # pylint: disable=missing-function-docstring
        return self._title

    @title.setter
    def title(self, in_title):
        self._title = in_title

    @property
    def cfg(self):  # pylint: disable=missing-function-docstring
        return self._cfg

    @cfg.setter
    def cfg(self, in_cfg: dict):
        self._cfg = in_cfg

    @property
    def query(self):  # pylint: disable=missing-function-docstring
        return self._query

    @query.setter
    def query(self, in_query):
        self._query = in_query

    @staticmethod
    def _get_work_artist_from_url(url_str, title_str):
        """
        If the received title (or most of it) ends the url and if so extract what comes before it.
        :param url_str: A string containing a discogs URL of a release
        :param title_str: A string containing a discogs title of a release
        :return: A string containing the artist if artist is found, otherwise an empty string
        """
        title_lwr = title_str.lower()
        url_lwr = url_str.lower()

        # Check if title is in the URL, if not, see if part of the title is - work backwards, shedding
        # the last word at each iteration
        while title_lwr:
            if title_lwr in url_lwr:
                return url_str[:url_lwr.index(title_lwr)].strip('-')

            title_lwr = re.sub(r'-[a-z]+$', '', title_lwr)

        return ''

    def parse_url(self, in_url=""):
        """
        Parse received URL to extract release_id, artist and title.
        Release_id is a sequence of digits,
        :param in_url: e.g. 'https://www.discogs.com/release/15639198-Art-Blakey-The-Jazz-Messengers-Just-Coolin'
        or '15639198-Art-Blakey-The-Jazz-Messengers-Just-Coolin'
        :return: The received URL (after populating `release`, `title`, `author` (if possible)
        """
        if not in_url:
            return ""

        split_on_str = 'release/'
        work_url = in_url.split(split_on_str)[-1]
        self.release = next(iter(work_url.split('-')), '')
        self.release = self.release if self.release.isdigit() else ''

        work_url = work_url[len(self.release) + 1:]
        work_title = self.title.replace('+?!.,:;_[](){}', '').replace(' ', '-')
        work_title = work_title.replace('\'', '')
        work_artist = self._get_work_artist_from_url(work_url, work_title)
        self.artist = work_artist if work_artist else self.artist
        self.title = work_title
        return in_url

    def resolve_artist_and_title(self, in_artist='', in_title=''):
        """
        Get artist and title. If they are supplied by the arguments, keep them, otherwise get them from
        the name of the directory.
        :param in_artist: A string containing the artist name to use
        :param in_title: A string containing the title name to use
        :return: artist and tile
        """
        if in_artist and in_title:
            return in_artist, in_title

        path_end_dir = (self.dir.rstrip("/")).split("/")[-1]
        path_end_parts = re.split(r'\[\d{4}]', path_end_dir)

        if len(path_end_parts) <= 1:
            return in_artist, in_title

        artist = in_artist or re.sub(r'[_\-]+', ' ', path_end_parts[0]).strip()
        title = in_title or path_end_parts[1].replace('_', ' ').strip()

        return artist if artist != self.artist else self.artist, title if title != self.title else self.title

    def resolve_query(self, in_query=''):
        """
        Resolve the query string. If the method receives a non-empty string, keep it, otherwise build it
        from the artist and title
        :param in_query: A string containing the query string to use or an empty string
        :return: The query string either echoed or constructed
        """
        if in_query:
            return in_query

        if self.artist and self.title:
            return " ".join([self.artist, self.title])

        path_end_dir = (self.dir.rstrip("/")).split("/")[-1]
        path_end_parts = re.split(r'\[\d{4}]', path_end_dir)

        if len(path_end_parts) > 1:
            self.artist = re.sub(r'[_\-]+', ' ', path_end_parts[0]).strip()
            self.title = path_end_parts[1].replace('_', ' ').strip()

        return " ".join([self.artist, self.title])

    def expected_audio_file_count(self, album_data) -> bool:
        """
        Determine if the number of tracks in the received album data matches the expected number
        :param album_data: A dictionary containing album track info
        :return: True if the album matches the expect number of tracks, otherwise False
        """
        if self.match < 0:
            return True

        # Count actual tracks, where type_ == 'track'
        count_to_match = len([t for t in album_data.get('tracklist', []) if t.get('type_', '') == 'track'])

        if self.match > 0:
            return self.match == count_to_match

        f_count = len([f for f in pathlib.Path(self.dir).iterdir() if f.is_file() and
                       str(f).rsplit('.', maxsplit=1)[-1] in USE_FILE_EXTENSIONS[:-1]])

        return f_count == count_to_match

    @staticmethod
    def clean_set_from_str(in_str, str_separator=' '):
        """
        Convert a string to a set, leaving out any empty elements.
        :param in_str: A string to convert
        :param str_separator: Sepearator to use to break up the string
        :return: A set on success, otherwise an empty set
        """
        if not in_str:
            return set()

        return {i for i in set(re.sub(r'\W+', ' ', in_str.lower()).split(str_separator)) if i}

    def verify_album(self, in_album):
        """
        Check if the album/CD info we have is the one to use. We expect the artist, title and the number of
        tracks to match
        :param in_album: A dictionary containing album/CD info
        :return: True if the album/CD is the correct one, otherwise False
        """
        # Check if album artist and title actually match what we want ...
        album_artist = self.get_artist(in_album.get('artists', {}))
        album_title = in_album.get('title', '')

        l_artist = self.artist if self.artist else ''
        r_artist = album_artist

        if len(self.artist) > len(album_artist):
            l_artist = album_artist
            r_artist = self.artist

        l_artist_set = self.clean_set_from_str(l_artist)
        r_artist_set = self.clean_set_from_str(r_artist)

        if not l_artist_set.intersection(r_artist_set):
            return False

        title_set = self.clean_set_from_str(self.title)
        album_title_set = self.clean_set_from_str(album_title)

        l_title_set = title_set
        r_title_set = album_title_set

        if len(title_set) < len(album_title_set):
            l_title_set = album_title_set
            r_title_set = title_set

        if not l_title_set.intersection(r_title_set):
            return False

        if self.query and not set(re.split(r'\W', self.query.lower())).intersection(
                set(re.split(r'\W', album_artist.lower() + " " + album_title.lower()))):
            return False

        if self.org_data_url:
            return True
        
        return self.expected_audio_file_count(in_album)

    @staticmethod
    def record_with_credits(in_records: list, analogue=True):
        """
        Find an album/CD/record with credits if available in the received list.
        :param in_records: A list of dictionaries holding album/CD/record info
        :param analogue: A flag indicating if analogue record is acceptable (track numbering A1, B3, etc.)
        :return: A dictionary selected from the received list
        """
        for record in in_records:
            if 'extraartists' in list(record.keys()):
                if analogue:
                    return record

                formats = record.get('formats', [])

                for record_format in formats:
                    format_name = record_format.get('name', '')

                    if not format_name or format_name in ['Vinyl']:
                        continue

                    return record

        return next(iter(in_records), {})

    @staticmethod
    def get_artist(artists=None):
        """
        Get artist name as a string from the received list
        :param artists: A list of strings
        :return: A string containing the artist's name
        """
        if not artists:
            return ''

        return ", ".join([artist.get('name', '') for artist in artists])

    @staticmethod
    def get_label(labels=None):
        """
        Get the record/CD/album label from the received list
        :param labels: A list of strings containing label info
        :return: A string containing the record label
        """
        if not labels:
            return ''

        return ", ".join([f"{label.get('name', '')} {label.get('catno', '')}" for label in labels])

    @staticmethod
    def get_tracks(tracklist=None):
        """
        Build a list of dictionaries, each representing a music track. The main key of each of the dictionaries
        is the track title and its value is dict with duration and credits (list), if available.
        :param tracklist: A list of track info
        :return: A list of dictionaries
        """
        if not tracklist:
            return []

        out_tracks = []
        for track in tracklist:
            track_name = f"{track.get('position', '0')} {track.get('title', '')}"

            duration = track.get('duration', '')
            artists = track.get('extraartists', None)

            if not artists and not duration:
                out_tracks.append(track_name)
                continue

            track_dict = {track_name: {}}

            if duration:
                track_dict[track_name]['duration'] = duration

            if artists:
                track_dict[track_name]['credits'] = \
                    [f"{'-'.join(art.get('role', '').split(' '))} - {art.get('name', '')}" for art in artists]

            out_tracks.append(track_dict)

        return out_tracks

    @staticmethod
    def get_album_credits(in_artists):
        """
        Get the album/CD/record credits from the received info.
        :param in_artists: A list of info to use
        :return: A list of strings, each representing an individual credit line
        """
        album_credits = []

        if not in_artists:
            return album_credits

        for art in in_artists:
            credit_line = f"{'-'.join(art.get('role', '').split(' '))} - {art.get('name', '')}"

            tracks = art.get('tracks', None)

            if tracks:
                credit_line = f"{credit_line} (tracks {tracks})"

            album_credits.append(credit_line)

        return album_credits

    @staticmethod
    def get_album_notes(in_notes=""):
        """
        Get album notes as an array, if available.
        :param in_notes: Notes retrieved from discogs
        :return: An array of strings on success, otherwise an empty array
        """
        if not in_notes:
            return []

        work_notes = re.split(r'[\r\n]+', in_notes)

        return [note for note in work_notes if note]

    @staticmethod
    def extract_series(record_series_dict):
        """
        Get info on album/CD/record series, which can include series name and category.
        :param record_series_dict: A dictionary from which to build series info
        :return: A string holding album/CD/record series information
        """
        if not record_series_dict:
            return ""

        out_series = []
        for series in record_series_dict:
            name = series.get('name', '')
            cat = series.get('catno', '')

            out_series.append(str(" ".join([name, cat])))

        return ", ".join(out_series)

    def build_yaml_dict(self, in_data=None) -> dict:
        """
        Build a dictionary of album/CD/record info that can be saved to a .yaml file.
        :param in_data: A dictionary containing the details of the album/CD/record to use.
        :return: A dictionary
        """
        yml = {}
        if not in_data:
            return yml

        yml['title'] = in_data.get('title', '')
        yml['series'] = self.extract_series(in_data.get('series', []))
        yml['artist'] = self.get_artist(in_data.get('artists', {}))
        yml['label'] = self.get_label(in_data.get('labels', {}))
        release_date = in_data.get('released', '')
        try:
            dt = datetime.strptime(release_date, '%Y-%m-%d')
        except ValueError:
            try:
                dt = datetime.strptime(release_date, '%Y')
            except ValueError:
                dt = None
        if dt:
            yml['released'] = f"{dt.day}/{dt.month}/{dt.year}" if dt else ''
            yml_year = dt.year
        else:
            yml['released'] = in_data.get('released', '')
            yml_year = re.sub(re.compile(re.sub(r'\d{4]', '', yml['released'])), '', yml['released'])

        yml['year'] = int(in_data.get('year', yml_year))
        yml['genre'] = ", ".join(in_data.get('genres', []))
        yml['style'] = ", ".join(in_data.get('styles', []))
        yml['tracks'] = self.get_tracks(in_data.get('tracklist', []))
        yml['credits'] = self.get_album_credits(in_data.get('extraartists', ''))
        yml['description'] = (self.get_text_data() or "") if self.is_jazz_genre(yml.get('genre', '')) else ""
        yml['notes'] = self.get_album_notes(in_data.get('notes', ""))

        return yml

    @staticmethod
    def is_jazz_genre(in_genre=''):
        """
        Check if the record is jazz.
        :param in_genre: A string containing music genre info
        :return: True if genre is "jazz", otherwise False
        """
        if not in_genre:
            return False

        genre_parts = re.split(r', *', in_genre)

        for part in genre_parts:
            if part in ['Jazz']:
                return True

        return False

    def get_data(self):
        """
        This method retrieves music metadata from discogs.com that can be saved to a YAML file.
        :return: A dictionary that contains retrieved info on  an album/CD/record
        """
        if self.release:
            response = self.dclient.get_release(id=self.release)
        else:
            response = self.dclient.get_search(genre=self.genre,
                                               artist=self.artist,
                                               title=self.title,
                                               year=self.year,
                                               country=self.country,
                                               q=self.query,
                                               token=self.cfg.get("access_token", "")
                                               )

        if response and isinstance(response, dict) and 'results' not in response.keys():
            response['type'] = 'release'
            response = {'results': [response]}
        elif not response.get('results', []):
            response = self.dclient.get_search(q=self.query, token=self.cfg.get("access_token", ""))

        results = response.get('results', [])
        found_releases = []
        for res in results:
            if res.get('type') not in ['release', 'master']:
                continue

            album = self.dclient.get_release(res.get('id'))

            if not album or album.get('message', '') == 'Release not found.':
                album = self.dclient.get_masters_release(res.get('id'))

            if not album or album.get('message', '') == 'Release not found.':
                continue

            if not self.verify_album(album):
                continue

            found_releases.append(album)

        extracted_data = self.record_with_credits(in_records=found_releases, analogue=False)

        if not extracted_data:
            extracted_data = self.record_with_credits(in_records=found_releases)

        content_obj = self.build_yaml_dict(extracted_data)

        return content_obj


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument("-a", "--artist", help="Artist nane",
                        type=str,
                        dest='artist',
                        required=False)
    parser.add_argument("-c", "--country", help="Country of release",
                        type=str,
                        dest='country',
                        required=False)
    parser.add_argument("-d", "--directory", help="Full path to the directory containing audio files to which to "
                                                  "apply tags",
                        type=str,
                        dest='audio_dir',
                        required=True)
    parser.add_argument("-g", "--genre", help="Music genre",
                        type=str,
                        dest='genre',
                        required=False)
    parser.add_argument("-m", "--match", help="Number of audio files the located album should match"
                                              ", deafult is 0 (match count of audio file in --directory; -1 means"
                                              " do not check",
                        type=str,
                        dest='match',
                        default=0,
                        required=False)
    parser.add_argument("-r", "--query", help="Search string, for example artist's name and album title",
                        type=str,
                        dest='query',
                        required=False)
    parser.add_argument("-i", "--release_id", help="Numeric identifier of the release (Discogs)",
                        type=str,
                        dest='release_id',
                        required=False)
    parser.add_argument("-t", "--title", help="Album title.",
                        type=str,
                        dest='title',
                        required=False)
    parser.add_argument("-u", "--url", help="URL of discogs page.",
                        type=str,
                        dest='url',
                        required=False)
    parser.add_argument("-y", "--year", help="Numeric year (release year)",
                        type=int,
                        dest='year',
                        required=False)

    args = parser.parse_args()

    mg = MetaGetter(
        dest_dir=args.audio_dir,
        query=args.query,
        title=args.title,
        genre=args.genre,
        artist=args.artist,
        release_id=args.release_id,
        url=args.url,
        year=args.year if args.year else None,
        match=args.match
    )

    yml_data = mg.get_data()

    if not yml_data:
        log_it("info", __name__, "No data found")
        sys.exit(1)

    write_yaml_file(yml_data, out_dir=mg.dir)

    sys.exit(0)
