"""
Module with code to set audio metadata tags.
"""
import argparse
import os
import re
import sys

import music_tag

from music_meta import USE_FILE_EXTENSIONS, MusicMeta  # pylint: disable=import-error
from utils import log_it  # pylint: disable=import-error

SCRIPT_DESCRIPTION = """Set metadata tags on audio files, e.g. mp3 or flac from a yaml file.
Make sure the audio files have names composed of track numbers and titles as in the YAML file.

See example_yml dir in https://github.com/adambmarsh/music_base
"""

NON_ALNUM_PATTERN = r'[?!\'+\-:;,._()\[\]~@\&%<>= ]+'


class TagSetter:
    """
    This class encapsulates an audio metadata tag setting functionality.
    """

    def __init__(self, in_dir='', in_yml=''):
        self._dir = ''
        self._yml_file = ''
        self._song_tags = {}
        self._audio_file_ext = ''

        self.dir = in_dir
        self.yml_file = in_yml if in_yml else (self.last_dir_in_path(self.dir) + ".yml")
        self.yml = MusicMeta(base_dir=self.dir).read_yaml(os.path.join(self.dir, self.yml_file))
        self.song_tags = {}
        self.audio_file_ext = ''

    @property
    def dir(self):  # pylint: disable=missing-function-docstring
        return self._dir

    @dir.setter
    def dir(self, in_dir):
        self._dir = in_dir

    @property
    def yml_file(self):  # pylint: disable=missing-function-docstring
        return self._yml_file

    @yml_file.setter
    def yml_file(self, in_yml):
        self._yml_file = in_yml

    @property
    def audio_file_ext(self):  # pylint: disable=missing-function-docstring
        return self._audio_file_ext

    @audio_file_ext.setter
    def audio_file_ext(self, in_ext):
        self._audio_file_ext = in_ext

    @staticmethod
    def last_dir_in_path(in_path: str):
        """
        Get the last dir in given path.
        :param in_path: Path from which to get the last dir
        :return: String containing the last dir in the given path
        """
        if in_path.endswith("/"):
            in_path = in_path[:-1]

        return in_path.split("/")[-1]

    def get_audio_file_list(self):
        """
        Get a list of audio files from a directory stored in a member var.
        :return: A list of audio files on success, and empty list if no files are found
        """
        out_files = []

        for curr_dir, sub_dirs, files in os.walk(self.dir):
            _ = curr_dir
            _ = sub_dirs
            out_files += [f for f in files if f.split('.')[-1] in USE_FILE_EXTENSIONS[:-1]]

        return out_files

    @staticmethod
    def clean_non_alnum(in_str, in_num_str=""):
        """
        Remove non-alnum chars and, optionally, digits.
        :param in_str: String to clean
        :param in_num_str: A string containing numbers, if provided it is used to extend the replacement pattern
        :return: The received string after clean-up
        """
        work_str = re.sub(NON_ALNUM_PATTERN, '', in_str)
        if not in_num_str:
            return work_str

        return re.sub(re.compile('^' + in_num_str), '', work_str)

    def get_track_info_from_yml(self, in_key, in_number: str):
        """
        Get audio track (song) info from YAML (file).
        :param in_key: base name of track (without number and file ext)
        :param in_number: number of track
        :return: Either a dict representing the track or an empty dict
        """
        clean_in_key = self.clean_non_alnum(in_key, in_number)

        for track in self.yml.get('tracks'):
            work_key = next(iter(track.keys()), '') if isinstance(track, dict) else track
            track_num = re.sub(r'(^\d{,3}).+', '\\1', work_key)

            if in_number and int(in_number) != int(track_num):
                continue

            # Clean track name of all punctuation, spaces and digits
            track_key = self.clean_non_alnum(work_key, track_num)
            lkey = clean_in_key
            rkey = track_key

            # Order keys, shorter first (lkey):
            if len(in_key) > len(track_key):
                lkey = track_key
                rkey = clean_in_key

            if lkey in rkey or lkey.lower() in rkey.lower():
                return track

        return {}

    def set_artist_composer(self, in_genre: str, in_tags: dict) -> dict:
        """
        Set the (album)artist and composer in the received dictionary of metadata tags
        :param in_genre: A string representing the music genre
        :param in_tags: A dict containing existing tags
        :return: Modified dict of metadata tags
        """
        if not isinstance(in_tags, dict):
            log_it("warning", "tags not a dict")
            return in_tags

        artist = self.yml.get('artist', '')

        if not artist:
            log_it("warning", "No artist in YAML")
            return in_tags

        in_tags['artist'] = artist

        if in_genre.lower() not in ['classical', 'opera']:
            return in_tags

        # Assume `artist` is  `composer`, then performer(s)
        performer = self.yml.get('performer', '')
        artist_seq = artist.split(", ")
        artist = next(iter(artist_seq), '')

        if len(artist_seq) > 1:
            performer = ", ".join(artist_seq[1:]) if not performer else performer

        artist_parts = artist.split(" ")

        if not artist_parts:
            return in_tags

        in_tags['composer'] = self.yml.get('composer',
                                           " ".join([f"{artist_parts[-1]},"] + artist_parts[:-1]))

        in_tags['albumartist'] = performer

        if in_tags['albumartist'] and in_tags['albumartist'] not in in_tags['artist']:
            in_tags['artist'] = ", ".join([in_tags['artist'], in_tags['albumartist']])

        return in_tags

    def track_tags_from_yml(self, file_name) -> (dict, int):
        """
        Retrieve music track tags from a YAML file
        :param file_name: Name of the file
        :return: A tuple - a dict of track tags and a track number
        """
        file_base, file_ext = os.path.splitext(file_name)
        base_name = re.sub(r'^\d{,3}', '', file_base)
        track_no = file_base[:len(base_name) * -1]
        bare_ext = file_ext.strip('.')
        tags = {}

        if bare_ext not in USE_FILE_EXTENSIONS:
            return tags, track_no

        self.audio_file_ext = bare_ext if not self.audio_file_ext else self.audio_file_ext
        genre = self.yml.get('genre', '')

        if genre:
            tags['genre'] = genre

        tags['album'] = self.yml.get('title', '')
        tags['year'] = self.yml.get('year', '')
        tags = self.set_artist_composer(genre, tags)

        # Clean file base name of all punctuation, spaces and digits
        track_info = self.get_track_info_from_yml(base_name, track_no)
        work_title = next(iter(track_info.keys()), '').strip() if isinstance(track_info, dict) else track_info

        if not track_no:
            found = re.search(r'^[0-9_]+', work_title)
            track_no = int(track_no if not found else work_title[found.start(): found.end()].strip('_'))

        tags['tracknumber'] = track_no
        tags['title'] = re.sub(r'^[0-9_]+', '', work_title)

        return tags, track_no

    def set_tags(self):
        """
        Set metadata tags on audio files.
        :return: Always True
        """
        file_names = self.get_audio_file_list()

        for f_name in file_names:
            f = music_tag.load_file(os.path.join(self.dir, f_name))
            track_tags, track_num = self.track_tags_from_yml(f_name)
            track_tags['totaltracks'] = len(file_names)

            for track_tag, tag_value in track_tags.items():
                if track_tag in ['tracknumber', 'year']:
                    f[track_tag] = int(tag_value)
                    continue

                f[track_tag] = str(tag_value)

            f.save()

            if not f_name.startswith(str(track_num)):
                source_path = os.path.join(self.dir, f"{f_name}")
                dest_path = os.path.join(self.dir, f"{track_num:02d}_{f_name}")
                os.rename(src=source_path, dst=dest_path)

        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument("-d", "--directory", help="Full path to the directory containing audio files to which to "
                                                  "apply tags",
                        type=str,
                        dest='audio_dir',
                        required=True)
    parser.add_argument("-y", "--yaml",
                        help="Name of the yaml file from which to read tag content",
                        type=str,
                        dest='yaml_file',
                        required=False)

    args = parser.parse_args()

    ts = TagSetter(in_dir=args.audio_dir, in_yml=args.yaml_file)

    if ts.set_tags():
        sys.exit(0)

    sys.exit(1)
