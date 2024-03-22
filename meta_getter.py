import argparse
import os
import pathlib
import re
from datetime import datetime

from discogs_wrapper import DV
from ruamel.yaml import YAML

from music_meta import USE_FILE_EXTENSIONS, MusicMeta
from music_text_getter import MusicTextGetter
from utils import log_it

script_description = ""


class MetaGetter(MusicTextGetter):

    def __init__(self, dest_dir="", artist="", genre="", query="", title="", release_id="", year=None, match=-1):
        self._title = self.genre = self._artist = self._dir = self._data = self._release = self._query = ""
        self._cfg = dict()
        self._year = None
        self._match = -1

        self.release = release_id
        self.match = match
        self.data = ""
        self.dir = dest_dir
        self.year = year
        self.artist, self.title = self.resolve_artist_and_title(artist, title)
        self.genre = genre
        self.query = self.resolve_query(query)
        script_dir = os.path.dirname(os.path.realpath(__file__))
        self.cfg = MusicMeta(base_dir=script_dir).read_yaml(os.path.join(script_dir, "discogs.yml"))
        self.dclient = DV("/".join([self.cfg.get("app", 'my_app')]))

        super().__init__(query_str=self.query, album_title=self.title, album_artist=self.artist)

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, in_data):
        self._data = in_data

    @property
    def match(self):
        return self._match

    @match.setter
    def match(self, in_match):
        self._match = int(in_match)

    @property
    def dir(self):
        return self._dir

    @dir.setter
    def dir(self, in_dir):
        self._dir = in_dir

    @property
    def release(self):
        return self._release

    @release.setter
    def release(self, in_release):
        self._release = in_release

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, in_year):
        self._year = in_year

    @property
    def artist(self):
        return self._artist

    @artist.setter
    def artist(self, in_artist):
        self._artist = in_artist

    @property
    def genre(self):
        return self._genre

    @genre.setter
    def genre(self, in_genre):
        self._genre = in_genre

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, in_title):
        self._title = in_title

    @property
    def cfg(self):
        return self._cfg

    @cfg.setter
    def cfg(self, in_cfg: dict):
        self._cfg = in_cfg

    @property
    def query(self):
        return self._query

    @query.setter
    def query(self, in_query):
        self._query = in_query

    def resolve_artist_and_title(self, in_artist='', in_title=''):
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

    def expected_file_no(self, album_data) -> bool:
        if self.match < 0:
            return True

        # Count actual tracks, where type_ == 'track'
        count_to_match = len([t for t in album_data.get('tracklist', []) if t.get('type_', '') == 'track'])

        if self.match > 0:
            return self.match == count_to_match

        f_count = len([f for f in pathlib.Path(self.dir).iterdir() if f.is_file() and str(f).split('.')[-1] in
                       USE_FILE_EXTENSIONS[:-1]])

        return f_count == count_to_match

    def verify_album(self, in_album):
        # Check if album artist and title actually match what we want ...
        album_artist = self.get_artist(in_album.get('artists', dict()))
        album_title = in_album.get('title', '')

        l_artist = self.artist if self.artist else ''
        r_artist = album_artist

        if len(self.artist) > len(album_artist):
            l_artist = album_artist
            r_artist = self.artist

        l_artist_set = set(re.sub(r'\W+', ' ', l_artist.lower()).split(' '))
        r_artist_set = set(re.sub(r'\W+', ' ', r_artist.lower()).split(' '))

        if not l_artist_set.intersection(r_artist_set):
            return False

        title_set = set(re.sub(r'\W+', ' ', self.title.lower()).split(' '))
        album_title_set = set(re.sub(r'\W+', ' ', album_title.lower()).split(' '))
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

        return self.expected_file_no(in_album)

    @staticmethod
    def last_dir_in_path(in_path: str):
        if in_path.endswith("/"):
            in_path = in_path[:-1]

        return in_path.split("/")[-1]

    @staticmethod
    def record_with_credits(in_records: list, analogue=True):
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

        return next(iter(in_records), dict())

    @staticmethod
    def get_artist(artists=None):
        if not artists:
            return ''

        return ", ".join([artist.get('name', '') for artist in artists])

    @staticmethod
    def get_label(labels=None):
        if not labels:
            return ''

        return ", ".join([f"{label.get('name', '')} {label.get('catno', '')}" for label in labels])

    @staticmethod
    def get_tracks(tracklist=None):
        if not tracklist:
            return []

        out_tracks = list()
        for track in tracklist:
            track_name = f"{track.get('position', '0')} {track.get('title', '')}"

            duration = track.get('duration', '')
            artists = track.get('extraartists', None)

            if not artists and not duration:
                out_tracks.append(track_name)
                continue

            track_dict = dict()
            track_dict[track_name] = dict()

            if duration:
                track_dict[track_name]['duration'] = duration

            if artists:
                track_dict[track_name]['credits'] = \
                    [f"{'-'.join(art.get('role', '').split(' '))} - {art.get('name', '')}" for art in artists]

            out_tracks.append(track_dict)

        return out_tracks

    @staticmethod
    def get_album_credits(in_artists):
        album_credits = list()

        if not in_artists:
            return album_credits

        for art in in_artists:
            credit_line = f"{'-'.join(art.get('role', '').split(' '))} - {art.get('name', '')}"

            tracks = art.get('tracks', None)

            if tracks:
                credit_line = f"{credit_line} (tracks {tracks}"

            album_credits.append(credit_line)

        return album_credits

    @staticmethod
    def extract_series(record_series_dict):
        if not record_series_dict:
            return ""

        out_series = list()
        for series in record_series_dict:
            name = series.get('name', '')
            cat = series.get('catno', '')

            out_series.append(str(" ".join([name, cat])))

        return ", ".join(out_series)

    def build_yaml_dict(self, in_data=None) -> dict:
        yml = dict()
        if not in_data:
            return yml

        yml['title'] = in_data.get('title', '')
        yml['series'] = self.extract_series(in_data.get('series', list()))
        yml['artist'] = self.get_artist(in_data.get('artists', dict()))
        yml['label'] = self.get_label(in_data.get('labels', dict()))
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
        yml['genre'] = ", ".join(in_data.get('genres', list()))
        yml['style'] = ", ".join(in_data.get('styles', list()))
        yml['tracks'] = self.get_tracks(in_data.get('tracklist', list()))
        yml['credits'] = self.get_album_credits(in_data.get('extraartists', ''))
        yml['description'] = (self.get_text_data() or "") if self.is_jazz_genre(yml.get('genre', '')) else ""

        return yml

    @staticmethod
    def is_jazz_genre(in_genre=''):
        if not in_genre:
            return False

        genre_parts = re.split(r', *', in_genre)

        for part in genre_parts:
            if part in ['Jazz']:
                return True

        return False

    def get_data(self):
        if self.release:
            response = self.dclient.get_release(id=self.release)
        else:
            response = self.dclient.get_search(genre=self.genre,
                                               artist=self.artist,
                                               title=self.title,
                                               year=self.year,
                                               q=self.query,
                                               token=self.cfg.get("access_token", "")
                                               )

        if not response.get('results', list()):
            response = self.dclient.get_search(q=self.query, token=self.cfg.get("access_token", ""))

        results = response.get('results', list())
        found_releases = list()
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

    def write_yaml_file(self, file_data):
        cur_dir = os.getcwd()
        dest_dir = self.dir

        if not dest_dir:
            dest_dir = cur_dir

        if not os.path.isdir(dest_dir):
            os.mkdir(dest_dir)

        filepath = os.path.join(dest_dir, self.last_dir_in_path(dest_dir) + ".yml")

        with open(filepath, 'wb') as out:
            yml = YAML()
            yml.explicit_start = True
            yml.indent(sequence=4, offset=2)
            yml.dump(file_data, out)

        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=script_description)
    parser.add_argument("-a", "--artist", help="Artist nane",
                        type=str,
                        dest='artist',
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
    parser.add_argument("-m", "--match", help="Number of audio files the located album should match",
                        type=str,
                        dest='match',
                        default=-1,
                        required=False)
    parser.add_argument("-r", "--query", help="Search string, for example artist's name and album title",
                        type=str,
                        dest='query',
                        required=False)
    parser.add_argument("-t", "--title", help="Album title.",
                        type=str,
                        dest='title',
                        required=False)
    parser.add_argument("-i", "--release_id", help="Numeric identifier of the release (Discogs)",
                        type=str,
                        dest='release_id',
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
        year=args.year if args.year else None,
        match=args.match
    )

    yml_data = mg.get_data()

    if not yml_data:
        log_it("info", __name__, "No data found")
        exit(1)

    mg.write_yaml_file(yml_data)

    exit(0)
