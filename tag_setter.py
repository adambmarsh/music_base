"""
Module with code to set audio metadata tags.
"""

import argparse
import os
import re
import sys
from collections import OrderedDict

import music_tag
from mutagen.id3 import ID3

from utils import eval_bool_str, last_dir_in_path, log_it, read_yaml  # pylint: disable=import-error
from utils import USE_FILE_EXTENSIONS  # pylint: disable=import-error

SCRIPT_DESCRIPTION = """Set metadata tags on audio files, e.g. mp3 or flac from a yaml file.
Make sure the audio files have names composed of track numbers and titles as in the YAML file.

See example_yml dir in https://github.com/adambmarsh/music_base
"""

NON_ALNUM_PATTERN = r'[?!\'+\-:;,._()\[\]~@\&%<>= ]+'


class TagSetter:
    """
    This class encapsulates an audio metadata tag setting functionality.
    """

    def __init__(self, in_dir='', in_yml='', in_correcting=False):
        self._correcting = False
        self._dir = ''
        self._yml_file = ''
        self._song_tags = {}
        self._audio_file_ext = ''
        self._track_num_in_filename = False

        self.dir = in_dir
        self.yml_file = in_yml if in_yml else (last_dir_in_path(self.dir) + ".yml")
        self.yml = read_yaml(os.path.join(self.dir, self.yml_file))
        self.song_tags = {}
        self.audio_file_ext = ''
        self.track_num_in_filename = False
        self.correcting = in_correcting

    @property
    def correcting(self):  # pylint: disable=missing-function-docstring
        return self._correcting

    @correcting.setter
    def correcting(self, in_correct):
        self._correcting = in_correct

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

    @property
    def track_num_in_filename(self):  # pylint: disable=missing-function-docstring
        return self._track_num_in_filename

    @track_num_in_filename.setter
    def track_num_in_filename(self, in_flag):
        self._track_num_in_filename = in_flag

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

    def get_audio_file_list(self, use_dir=''):
        """
        Get a list of audio files from a directory stored in a member var.
        :return: A list of audio files on success, and empty list if no files are found
        """
        out_files = []

        for _, _, files in os.walk(self.dir if not use_dir else use_dir):
            out_files += [f for f in files if f.split('.')[-1] in USE_FILE_EXTENSIONS[:-1]]

        return out_files

    @staticmethod
    def clean_non_alnum(in_str, in_num_str="") -> str:
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

    def track_info_all(self) -> OrderedDict:
        """
        This method extracts track names/titles and numbers from the property yml. The original track number is
        preserved and can be either numeric or in vinyl format, e.g. A1, A2, ... C5
        :return:  An ordered dictionary (sorted by key), where the track number is the key and the track name, the
        corresponding value
        """
        tracks_only = {}
        for track in self.yml.get('tracks', []):
            work_track = next(iter(track.keys()), '') if isinstance(track, dict) else track
            track_num = re.sub(r'([A-Z]?\d{,3}).+', '\\1', work_track)

            if not track_num or track_num == work_track:
                continue

            work_track = re.sub(re.compile(f"^{track_num}"), '', work_track).strip()

            tracks_only[track_num] = work_track

        return OrderedDict(sorted(tracks_only.items(), key=lambda item: item[0]))

    def get_track_info_from_yml(self, in_key, in_number='') -> (str, any):
        """
        Get audio track (song) info from YAML (file).
        If YAML contains track numbers in vinyl format, e.g. A1, B1, C2, etc.,
        they are converted to numeric values, where A1 becomes 1, A2, 2, etc.
        :param in_key: base name of track (without number and file ext)
        :param in_number: track number from audio file
        :return: Track title without number and track number on success or empty string and -1
        """
        clean_in_key = self.clean_non_alnum(in_key, in_number).lower()

        yml_titles = []
        track_count = 1
        for track_num, track_name in self.track_info_all().items():
            yml_titles.append(track_name)
            org_track_num = track_num

            if track_num and re.match(r'[A-Z]\d+', track_num):
                track_num = f"{track_count}"

            track_count += 1

            # Clean track name of all punctuation, spaces and digits
            clean_track_key = self.clean_non_alnum(track_name, org_track_num).lower()
            lkey = clean_in_key
            rkey = clean_track_key

            # Order keys, shorter first (lkey):
            if len(clean_in_key) > len(clean_track_key):
                lkey = clean_track_key
                rkey = clean_in_key

            if lkey == rkey:
                return track_name, track_num

        log_it("error", "get_track_info_from_yml", f"{repr(in_key)} not in {repr(yml_titles)}")
        return '', -1

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

        in_tags['composer'] = self.yml.get('composer', " ".join([f"{artist_parts[-1]},"] + artist_parts[:-1]))

        in_tags['albumartist'] = performer

        if in_tags['albumartist'] and in_tags['albumartist'] not in in_tags['artist']:
            in_tags['artist'] = ", ".join([in_tags['artist'], in_tags['albumartist']])

        return in_tags

    @staticmethod
    def extract_track_num_from_file_name(in_name, in_number="") -> int:
        """
        Extract track number
        :param in_name: A string representing a file name
        :param in_number: A string containing a track number
        :return:The track number as int if extracted, -1 on error
        """
        if in_number and (in_number.strip()).isdigit():
            return int(in_number)

        found = re.search(r'^[0-9]{1,3}[_ ]', in_name)

        try:
            track_no = int(in_number if not found else in_name[found.start(): found.end()].strip('_'))
        except ValueError as ve:
            log_it("error", "extract_track_num_from_file_name", {repr(ve)})
            return -1

        return track_no

    def track_tags_from_yml(self, audio_file_name) -> (dict, str):
        """
        Retrieve music track tags from a YAML file
        :param audio_file_name: Name of audio file
        :return: A tuple - a dict of track tags and a track number
        """
        file_base, file_ext = os.path.splitext(audio_file_name)
        base_name = re.sub(r'^\d{,3}[_ ]', '', file_base) if self.track_num_in_filename else file_base
        track_no = file_base[: len(base_name) * -1].strip(" _") if self.track_num_in_filename else ""
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
        track_info, track_no = self.get_track_info_from_yml(base_name, track_no)
        work_title = next(iter(track_info.keys()), '').strip() if isinstance(track_info, dict) else track_info

        if track_no == -1:
            sys.exit(1)

        tags['tracknumber'] = track_no
        tags['title'] = work_title.strip()

        return tags, track_no

    def files_start_with_track_num(self, in_file_names) -> bool:
        """
        Check if all files start with a track number and set a flag on the class. The numbers must be
        consecutive.
        :param in_file_names:
        :return: True if numbers start the file names, otherwise False
        """
        numbered = [f for f in in_file_names if re.match(r'^\d{1,3}[_ ]', f)]

        if not numbered:
            return False

        if len(numbered) != len(in_file_names):
            return False

        track_nos = [self.extract_track_num_from_file_name(f) for f in in_file_names]

        if track_nos and len(str(track_nos[0])) > 2:
            track_nos = [int(str(tn)[1:]) for tn in track_nos]

        maximum = max(track_nos)

        if sum(track_nos) == maximum * (maximum + 1) / 2:
            return True

        return False

    def clear_unwanted_tags_flac(self, file_name: str):
        """
        Clear unwanted tags in the audio file.
        :param file_name: A string containing the name of the audio file (flac, mp3, etc.)
        :return: Modified audio file object on success, otherwise unchanged audio file object
        """
        file_object = music_tag.load_file(os.path.join(self.dir, file_name))

        unwanted = [
            'language',
            'encoder',
            'minor_version',
            'major_band',
            'major_brand',
            'compatible_bands',
            'compatible_brands',
            'replaygain_track_gain',
            'replaygain_track_peak',
            'itunes_cddb_1',
            'PUBLISHER',
            'RECORDED-BY',
            'GRACENOTEFILEID',
            'GRACENOTEEXTDATA',
            'ENCODED-BY',
        ]

        for tag_name in unwanted:
            try:
                file_object.raw[tag_name] = [""]
            except KeyError:
                continue

        return file_object

    def clear_unwanted_tags_mp3(self, file_name: str):
        """
        Clear unwanted tags in the audio file.
        :param file_name: A string containing the name of the audio file (flac, mp3, etc.)
        :return: Modified audio file object on success, otherwise unchanged
        """
        unwanted = [
            'TLAN',
            'TKWD',
            'TMED',
            'TMOO',
            'TPE1',
            'TPE2',
            'TPE3',
            'TPE4',
            'TPUB',
            'TRSN',
            'TSRC',
            'TSSE',
            'UFID',
            'USER',
            'WCOM',
            'WCOP',
            'WOAS',
            'WOAE',
            'WFED',
        ]

        file_object = ID3(os.path.join(self.dir, file_name))

        for tag_name in unwanted:
            try:
                file_object.delall(tag_name)
            except KeyError:
                continue

        file_object.save()

        return music_tag.load_file(os.path.join(self.dir, file_name))

    def set_tags(self):
        """
        Set metadata tags on audio files.
        :return: Always True
        """
        file_names = self.get_audio_file_list()

        # Check if digits  start file names, if all files start with a number, assume it is the track number.
        self.track_num_in_filename = self.files_start_with_track_num(file_names)

        clear_unwanted = {
            'flac': self.clear_unwanted_tags_flac,
            'mp3': self.clear_unwanted_tags_mp3
        }

        for f_name in file_names:
            track_tags, track_num = self.track_tags_from_yml(f_name)
            track_tags['totaltracks'] = len(file_names)

            # noinspection PyArgumentList
            file_obj = clear_unwanted[self.audio_file_ext](f_name)

            for track_tag, tag_value in track_tags.items():
                if track_tag in ['tracknumber', 'year']:
                    try:
                        file_obj[track_tag] = int(tag_value)
                    except ValueError:
                        log_it('error', __name__, f"No value for tag {repr(track_tag)}.")
                        return False
                    continue

                file_obj[track_tag] = str(tag_value)

            file_obj.save()

            if not self.track_num_in_filename:
                source_path = os.path.join(self.dir, f"{f_name}")
                dest_path = os.path.join(self.dir, f"{int(track_num):02d}_{f_name}")
                os.rename(src=source_path, dst=dest_path)

        return True

    def correct_directory(self, in_dir, in_files, in_tags):
        """
        Correct metadata in one audio directory
        :param in_dir:  Path and name of the directory
        :param in_files: A list of files in the directory
        :param in_tags: The tags (and new values)
        :return: number of files changed
        """
        changed_file_count = 0
        for f_name in in_files:
            file_obj = music_tag.load_file(os.path.join(self.dir, in_dir, f_name))

            tag_changes = 0
            for yml_tag in in_tags:
                try:
                    for tag_key, tag_val in yml_tag.items():
                        if tag_key in ['tracknumber', 'year']:
                            file_obj[tag_key] = int(tag_val)
                            continue

                        if file_obj[tag_key].value == tag_val:
                            continue

                        file_obj[tag_key] = tag_val
                        tag_changes += 1
                except AttributeError:
                    log_it("error", f"yml_dir={in_dir} tag={repr(yml_tag)}")
                    sys.exit(111)

            if tag_changes == 0:
                continue

            file_obj.save()
            changed_file_count += 1

        return changed_file_count

    def correct_tags(self):
        """
        Correct metadata tags on audio files.
        :return: Always True
        """

        for yml_dir, yml_tags in self.yml.items():
            file_names = self.get_audio_file_list(use_dir=os.path.join(self.dir, yml_dir))

            changed_file_num = self.correct_directory(yml_dir, file_names, yml_tags)

            log_it("info", "dir", f"{yml_dir}, {changed_file_num} files changed")

        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=SCRIPT_DESCRIPTION)
    parser.add_argument(
        "-d",
        "--directory",
        help="Full path to the directory containing audio "
             "files to which to apply tags (or directory containing "
             "sub-directories with audio files, see -c).",
        type=str,
        dest='audio_dir',
        required=True,
    )
    parser.add_argument(
        "-c",
        "--corrections",
        help="Flag indicating whether to correct metadata "
             "in audio files in this case -y provides a yaml file that "
             "specifies the corrections.",
        type=str,
        dest='corrections',
        required=False,
    )
    parser.add_argument(
        "-y",
        "--yaml",
        help="Name of the yaml file from which to read tag content, for example see "
             "example-tag-change.yml in the directory of tag_setter.py",
        type=str,
        dest='yaml_file',
        required=False,
    )

    args = parser.parse_args()

    ts = TagSetter(in_dir=args.audio_dir, in_yml=args.yaml_file, in_correcting=eval_bool_str(args.corrections))

    if ts.correcting:
        ts.correct_tags()
        sys.exit(0)

    if ts.set_tags():
        sys.exit(0)

    sys.exit(1)
