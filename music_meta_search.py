"""
This module hosts the class MusicMetSearc.h
It searches through audio file tags (audio files) in the directory specified by
the user.
"""
###############################################################################
#
# Copyright (C) 2022-2024 Adam Bukolt.
# All Rights Reserved.
#
###############################################################################
import argparse
import datetime
import os
import re
import sys
# from ctypes.wintypes import BOOLEAN
from os import listdir
from os.path import isfile, join
from pathlib import Path

import ruamel
from mutagen.easyid3 import EasyID3

from mutagen.flac import FLAC, FLACNoHeaderError  # NOQA # pylint: disable=unused-import

# noinspection PyProtectedMember
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # NOQA  # pylint: disable=unused-import
from tinytag import TinyTag
import application_imports  # NOQA # pylint: disable=unused-import, disable=import-error
from utils import log_it, USE_FILE_EXTENSIONS, eval_bool, write_json_file  # pylint: disable=import-error

composer_classical = ['Beethoven', 'Mozart', 'Chopin']

dir_names = [
    'Chick_Corea___John_Mclaughlin_-_Five_Peace_Band_Live_disc_1',
    'Chick_Corea___John_Mclaughlin_-_Five_Peace_Band_Live_disc_2',
    'Elton John_-_The Very Best Of (CD 1)',
    'EricClapton-Backtrackin_CD2',
    'Emerson, Lake & Palmer-Welcome back (Disc 1)',
    'Glenn Miller - The Lost Recordings (Disc 1 of 2)'
]

MIN_YEAR_DIGITS = 4
MAX_YEAR_DIGITS = 4

DEFAULT_TAG_MAPPING = {-1: -1}


class MusicMetaSearch:
    """
    This class encapsulates music metadata.
    """

    def __init__(self, base_dir, find_txt=None, use_regex=False, max_albums=None):
        self.split_pattern = r'[_-]+$'
        self._base_dir = base_dir
        self._candidate = {}
        self._consider = {}
        self._tags = {}
        self._find_this = self._rx_search = None
        self._max_albums = -1
        self.albums_existing = 0
        self.albums_new_mod = 0
        self.tags = {}
        self.created = False
        self.find_this = find_txt
        self.rx_search = use_regex
        self.max_albums = max_albums

    @property
    def tags(self):  # pylint: disable=missing-function-docstring
        return self._tags

    @tags.setter
    def tags(self, in_tags):
        self._tags = {**self._tags, **in_tags}

    @property
    def base_dir(self):  # pylint: disable=missing-function-docstring
        return self._base_dir

    @base_dir.setter
    def base_dir(self, in_base_dir):
        self._base_dir = in_base_dir

    @property
    def find_this(self):
        """
        This property holds the text to search for or a regex pattern
        to use in the search.
        """
        return self._find_this

    @find_this.setter
    def find_this(self, in_find_what):
        """
        This property holds the text to search for or a regex pattern
        to use in the search.
        :param in_find_what: A string which holds either the text to
        find or a regex patter to use in the search.
        """
        self._find_this = in_find_what

    @property
    def rx_search(self):
        """
        This property indicates whether to use regex search.
        """
        return self._rx_search

    @rx_search.setter
    def rx_search(self, in_val):
        """
        This property holds the text to search for or a regex pattern
        to use in the search.
        :param in_val: A value that indicates whether to run regex searchh.
        """
        self._rx_search = eval_bool(in_val)

    @property
    def max_albums(self):  # pylint: disable=missing-function-docstring
        return self._max_albums

    @max_albums.setter
    def max_albums(self, in_limit):
        self._max_albums = int(in_limit if in_limit else -1)

    @staticmethod
    def map_tags(in_tags):
        """
        Create a tag mapping
        :param in_tags: tags to map
        :return: A dictionary with the mapping
        """
        tag_map = {
            'tracknumber': 'track',
            'date': 'year'
        }

        return {k if k not in tag_map else tag_map[k]: in_tags[k] for k in in_tags}

    def get_tags_from_file(self, file_obj):
        """
        Retrieve metadata tags from a media file.
        :param file_obj: File object
        :return: A dictionary containing the tags
        """
        tag_dict = {}
        f_path = os.path.join(file_obj.get('dir_path', ''), file_obj.get('file', ''))

        if f_path.endswith('.yml'):
            return tag_dict

        try:
            tag_dict = {k.lower(): v for k, v in dict(list(FLAC(f_path).tags)).items()}
            return self.map_tags(tag_dict)

        except FLACNoHeaderError:
            try:
                tag_dict = (TinyTag.get(f_path)).__dict__

            except Exception as ex:  # pylint: disable=broad-exception-caught
                if not f_path.endswith(".yml"):
                    log_it("debug", __name__, repr(ex) + f" file: {f_path}")

        return tag_dict

    @staticmethod
    def fix_comment(in_comment):
        """
        Remove spurious information from a comment, usually starting with "XXX"
        :param in_comment: Comment to fix
        :return: Repaired comment string or an empty string
        """
        if not in_comment:
            return ""

        if 'engID3v1 Comment' in in_comment:
            return ""

        if re.search(r'X{1,3}[A-Z]+DURATION', in_comment):
            return "DURATION " + re.sub(r'[A-Z]+.+:', '', in_comment)

        if re.search(r'X{1,3}[A-Z]+', in_comment):
            return ""

        return in_comment

    def search_in_tags(self, in_tag_dict) -> bool:
        """
        Search tags for specific text.
        :param in_tag_dict:  A dictionary of tags to search through
        :return: True is text is found in a tag, otherwise False
        """
        if not in_tag_dict:
            return False

        for val in in_tag_dict.values():
            if self.rx_search:
                if re.search(re.compile(self.find_this), val):
                    return True
                continue

            if self.find_this in str(val):
                return True

        return False

    def get_music_file_tags(self, in_file_info):
        """
        Get metadata tags from a music file
        :param in_file_info: A dictionary containing file information (path, name)
        :return: True if self.search_in_tags() finds search str in a tag, else False.
        """
        in_file_tags = {}
        in_dir_path = in_file_info.get('dir_path', '')
        in_dir_name = in_file_info.get('dir_name', '')
        in_file = in_file_info.get('file', '')
        in_file_tags['directory'] = re.sub(r'^/', '', re.sub(re.compile(self.base_dir), '', in_dir_path))
        in_file_tags['file'] = in_file.split('/')[-1]
        tag_dict = self.get_tags_from_file(in_file_info)

        if not self.search_in_tags(tag_dict):
            return False

        if in_dir_name and in_dir_name not in self.tags:
            self.tags[in_dir_name] = []

        save_dict = {
            **in_file_tags,
            **{k.lower(): v for k, v in tag_dict.items() if not (k.startswith('_') or k == 'extra')}
        }

        save_dict = {k: v for k, v in save_dict.items() if isinstance(save_dict[k], (str, int, list))}

        save_dict['comment'] = self.fix_comment(save_dict.get('comment', ''))

        self.tags[in_dir_name].append(save_dict)
        return True

    def get_year_from_tags(self, dir_name):
        """
        Retrieve the release year from the audio files in the specified directory
        :param dir_name: Name of the directory containing audio files
        :return: A year or date on success or None on failure
        """
        my_path = str(join(self.base_dir, dir_name))
        only_files = [join(my_path, f) for f in listdir(my_path) if isfile(join(my_path, f))]

        only_files = [f for f in only_files if re.search(r'\.(flac|mp3|ogg|wma)$', f)]

        for f in only_files:
            try:
                log_it("info", __name__, f)
                tag_dict = dict(list(FLAC(f).tags))
                return tag_dict.get('DATE', tag_dict.get('YEAR', ''))

            except FLACNoHeaderError:
                try:
                    rel_date = EasyID3(f).get('date', '')
                    return rel_date if not isinstance(rel_date, list) else next(iter(rel_date), '')

                except Exception as ex:  # pylint: disable=broad-exception-caught
                    if f.endswith(".yml"):
                        continue

                    log_it("debug", repr(ex) + f" file: {f}")
                    continue

        return None

    def get_year(self, dir_name):
        """
        Get album (release) year. None if the supplied directory name contains "Various"
        :param dir_name: Name or the directory
        :return: A string containing the year or None on failure
        """
        if 'Various' in dir_name:
            return None

        y = self.get_year_from_tags(dir_name)

        if not y:
            return None

        y = re.sub(r'[()]', '', re.sub(r'[/ ]+', r'-', y))

        if len(y) > MAX_YEAR_DIGITS:
            ns = y.split('-')

            ys = []

            for n in ns:
                try:
                    val = int(n)

                    if val >= 1900:
                        ys.append(val)
                except ValueError:
                    continue

            if ys:
                return str(min(ys))
        elif int(y) < 1900:
            return None

        return y

    @staticmethod
    def transpose_cd_year(in_str):
        """
        Transpose CD[0-9]+ and a sequence of four digits  in the supplied string.
        :param in_str: String in which to transpose substrings
        :return: Modified string
        """
        if 'CD' not in in_str:
            return in_str

        if not re.findall(r'\[\d{4}]', in_str):
            return in_str

        return re.sub(r'(CD\d+)_(\[\d{4}])', '\\2_\\1', in_str)

    @staticmethod
    def fix_one_off_names(in_working):
        """
        Fix specified names so that they conform to the pattern "(Firstname_)Surname_-_".
        :param in_working: Working string expected to contain a name to fix
        :return: Corrected working string
        """

        surnames = [
            'Hiromi_',
            'Illinois_Jacquet_',
            'KlausSchulze_',
            'Kalyi_Jag_',
            'Yes_',
            'Yusef_Lateef_',
            'Souad_Massi__'
        ]

        name_replacements = {}

        for surname in surnames:
            name_replacements[surname] = surname + '_-_' if not surname.endswith('_') else surname + '-_'

        for k, v in name_replacements.items():
            if not in_working.startswith(k):
                continue

            if '_-_' in in_working:
                continue

            return re.sub(k, v, in_working)

        if in_working.startswith('L_Shankar_others') and '_-_' not in in_working:
            return in_working.replace('L_Shankar_', 'L_Shankar_-_')

        if in_working.startswith('Beethoven_-_') and '_L_v_-_' not in in_working:
            return in_working.replace('Beethoven_-_', 'Beethoven_L_v_-_')

        if in_working.startswith('Mozart_-_') and '_WA_-_' not in in_working:
            return in_working.replace('Mozart_-_', 'Mozart_WA_-_')

        return in_working

    def fix_up_name(self, working_name):
        """
        Fix a person;s name (artist).
        :param working_name: A string containing name ot fix
        :return: A string containing the corrected name
        """
        # Special cases (one-offs):
        working = self.fix_one_off_names(working_name)

        # ...a___2011, ...a___[2011], ...a___(2011) -> ...a__2011
        working = re.sub(r'([a-zA-Z\d])_[\[(]?(\d{MIN_YEAR_DIGITS,MAX_YEAR_DIGITS})[])]', '\\1__\\2', working)
        # Anything with CD|discs|Disc|disk, etc., followed by number -> __CD{number}
        working = re.sub(r' ?-?[ _]*[(\[]*(CD|Disc|disc|disk|Disk)[#_ \-]*(\d{1,2})$', '__CD\\2', working)
        # {abc} - {def} -> {abc}_-_{def}
        working = re.sub(r'([a-zA-Z]) ?- ?([a-zA-Z])', '\\1_-_\\2', working)
        # Replace comma with underscore
        working = re.sub(r'[ ,]', '_', working)
        # Get rid of EAC|FLAC|mp3|320kbps|etc. at the end of the name
        working = re.sub(r'[_\[(]+(EAC|FLAC|mp3)[_\-]*(EAC|FLAC|320kbps)*[_\])]+$', '', working)
        # If year at the end, make sure we have '__YYYY'
        working = re.sub(r'_+$', '', re.sub(r'([a-zA-Z])_[(\[]*(\d{MIN_YEAR_DIGITS,MAX_YEAR_DIGITS})[)\]]',
                                            '\\1__\\2', working))

        working = re.sub(r'(\[(a-zA-Z)+]?)+', '\\1', working)

        # Special one-off case: Beethoven should be at the beginning, followed by '_L_v_-_'
        if composer_classical[0] in working and not working.startswith(composer_classical[0]):
            working = composer_classical[0] + '_L_v_-_' + re.sub(r'[_\-]*' + composer_classical[0], '', working)

        return working

    @staticmethod
    def get_hyphen_underscore_pos(working):
        """
        Get the positions of hyphen and underscore in the received string object.
        :param working: String in which to locate hyphen and underscore
        :return: A tuple with the index of the hyphen and the index of the underscore
        """
        try:
            hyphen_pos = working.index('_-_')
        except ValueError:
            hyphen_pos = None

        try:
            underscore_pos = working.index('__')
        except ValueError:
            underscore_pos = None

        return hyphen_pos, underscore_pos

    def split_work_str(self, in_str):
        """
        Split the received string using a pre-defined pattern (held in a member var)
        :param in_str: String to split
        :return: A list of strings resulting from the split
        """
        w_str = re.sub(self.split_pattern, '', in_str)
        splitter = ''

        hyphen_pos, underscore_pos = self.get_hyphen_underscore_pos(in_str)

        if hyphen_pos and underscore_pos:
            if hyphen_pos < underscore_pos:
                splitter = '_-_'
            else:
                splitter = '__'

        if hyphen_pos and not underscore_pos:
            splitter = '_-_'

        if not hyphen_pos and underscore_pos:
            splitter = '__'

        return w_str.split(splitter) or w_str

    def fix_up_year_cd_seq(self, work_str, work_y, work_c, year):
        """
        Correct year and CD number in the received work string. We want the pattern "Artist_Name_-_[year]_CDx_Title"
        :param work_str: String to modify
        :param work_y: Year string
        :param work_c: CD string
        :param year: Year as a str
        :return: A string reflecting the changes
        """
        if not work_c + work_y or not year:
            return work_str

        work_str = re.sub(work_y + work_c, '', work_str)
        work_str = re.sub(re.compile(work_c + r'$'), '', work_str)
        work_str = re.sub(re.compile(work_y + r'[-_]*$'), '', work_str)
        work_str = re.sub(re.compile('-_' + work_c + work_y), '', work_str)
        work_str = re.sub(re.compile('-_*' + work_y + '_' + work_c), '-_', work_str)

        w_split = self.split_work_str(work_str)

        if work_y:
            work_y = re.sub(
                r'[_-]+(\d+)', '_[\\1]_' if (not year or year in work_y) else '_[' + year + ']_', work_y
            )
        elif work_c:
            work_c = work_c + '_'

        if isinstance(w_split, list) and len(w_split) > 1:
            w_split[1] = re.sub(r'^_\d{4}', '', re.sub(re.compile('^' + work_c), '', w_split[1]))
            work_str = re.sub(
                r'_+',
                '_',
                w_split[0] + '_-_' + work_c + (work_y if work_c not in w_split[1] else '')) + '__'.join(w_split[1:])
        else:
            work_str = w_split[0] + re.sub(r'_+', '_', '_-_' + work_c + work_y)

        # Remove release year from the end, then remove '_-' for and multiple underscores:
        if year:
            work_str = re.sub(re.compile('_+' + year + r'$'), '', work_str)

        work_str = re.sub(self.split_pattern, '', work_str).replace('___', '__')

        # Remove CD{number}_{year}, note {year} is not surrounded by []:
        if work_c:
            work_str = re.sub(re.compile(work_c + r'?_\d{4}' + work_c + r'?'), '', work_str)

        # Remove trailing '_' and '_':
        return re.sub(self.split_pattern, '', re.sub(r'_+-_+', '_-_', work_str))

    def collect_tags(self):
        """
        Collect tags from files in directories representing albums or collections of tracks and
        write them to db tables (Album, Song)
        :return: void
        """
        start_time = datetime.datetime.now()

        for curr_dir, sub_dirs, files in os.walk(self.base_dir):
            _ = sub_dirs
            only_files = [f for f in files if f.split('.')[-1] in USE_FILE_EXTENSIONS]
            curr_dir_name = re.sub(r'^/', '', re.sub(re.compile(self.base_dir), '', curr_dir))

            if curr_dir == self.base_dir:
                continue

            log_it("info", __name__, f"Processing: {curr_dir_name}")
            self.get_music_metadata(in_files=only_files, dir_path=curr_dir, dir_name=curr_dir_name)
            curr_dir_tags = self.tags.get(curr_dir_name)
            if not curr_dir_tags:
                continue

            if self.max_albums <= 0:
                continue

            if len(self.tags.keys()) >= self.max_albums > 0:
                break

        log_it("info", __name__, f"runtime={str(datetime.datetime.now() - start_time)}")

    def get_music_metadata(self, in_files=None, dir_path=None, dir_name=None):
        """
        Retrieve metadata from tags in .mp3, .flac, .ogg, etc. files and from a .yml if present.
        The data from tags are saved in `self.tags`, while yaml data are returned to the caller
        :param in_files: A list of files from an album/CD directory
        :param dir_path: The path to the album/CD directory
        :param dir_name: The name of the album/CD directory
        :return: A dictionary representing the contents fo the yaml file
        """

        if not self.find_this:
            log_it("info", __name__, f"No search criteria provided ({self.find_this})")
            return

        for f in in_files:
            if self.get_music_file_tags({'file': f, 'dir_path': dir_path, 'dir_name': dir_name}):
                return

    @staticmethod
    def int_type_as_str(in_int, lead="\n"):
        """
        Convert Int-type to a string with the required leading char
        :param in_int: An int to convert
        :param lead: Leading char to use
        :return: String representation of the received object
        """
        return f"{lead}{str(in_int)}"

    @staticmethod
    def none_type_as_str(in_value, lead="\n"):
        """
        Convert None-type to a string with the required leading char
        :param in_value: An object to convert
        :param lead: Leading char to use
        :return: String representation of the received object
        """
        return f"{lead}{in_value}"

    @staticmethod
    def str_type_as_str(in_str, lead="\n"):
        """
        Convert a string to a string with the required leading char
        :param in_str: A String object to convert
        :param lead: Leading char to use
        :return: String representation of the received object
        """
        return f"{lead}{str(in_str)}"

    def list_type_as_str(self, in_list, in_lead="\n"):
        """
        Convert a list to a string representation
        :param in_list: List object to convert
        :param in_lead: Leading char to use
        :return: String representation of the received list
        """
        outcome = []
        item_lead = "\n - " if "--" not in in_lead else in_lead
        for list_item in in_list:
            outcome.append(self.render_as_str(list_item, in_lead=item_lead))

        out_lead = "" if "--" in item_lead else in_lead
        return out_lead.join(outcome)

    def dict_type_as_str(self, in_dict, lead="\n"):
        """
        Convert a dictionary to a string representation
        :param in_dict: Dictionary object to convert
        :param lead: Leading char to use
        :return: String representation of the received dict
        """
        outcome = []

        for k, v in in_dict.items():
            outcome.append(f"\n - {k}:" + self.render_as_str(v, " "))

        use_lead = "  - " if '-' in lead else ""
        return use_lead.join(outcome)

    @staticmethod
    def date_type_as_str(in_date, lead=""):
        """
        Convert a date type object to a string
        :param in_date: Date object to convert
        :param lead: Leading char to use
        :return: A string representation of the date
        """
        return f"{lead}{str(in_date)}"

    def render_as_str(self, in_item, in_lead="\n"):
        """
        Convert the received item to a string, using the supplied leading char.
        :param in_item: Item to convert, can be int, str, dict, list, None or datetime date object
        :param in_lead: Leading char (str) to use
        :return: A string representation of the received item
        """
        type_select = {
            int: self.int_type_as_str,
            str: self.str_type_as_str,
            dict: self.dict_type_as_str,
            ruamel.yaml.comments.CommentedMap: self.dict_type_as_str,
            list: self.list_type_as_str,
            ruamel.yaml.comments.CommentedSeq: self.list_type_as_str,
            None: self.none_type_as_str,
            datetime.date: self.date_type_as_str
        }

        return type_select.get(type(in_item), self.str_type_as_str)(in_item, in_lead)


PROGRAM_DESCRIPTION = "This program searches tags in audio files."

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument("-d",
                        "--directory",
                        help="Full path to the parent directory containing"
                             " sub-directories with music files, for example '/home/adam/music'",
                        type=str,
                        dest='base_dir',
                        required=True)

    parser.add_argument("-l", "--limit",
                        help="If provided, determines the max number of album directories to scan.",
                        type=int,
                        dest='limit',
                        default=-1,
                        required=False)

    parser.add_argument("-f", "--find",
                        help="If provided, the program searches for this string in metadata.",
                        type=str,
                        dest='search_str',
                        default='',
                        required=False)

    parser.add_argument("-x", "--rx",
                        help="If provided, the program treats search_str as a regex pattern.",
                        type=bool,
                        dest='use_rx',
                        default=False,
                        required=False)

    args = parser.parse_args()

    rd = MusicMetaSearch(
        base_dir=args.base_dir,
        max_albums=args.limit,
        find_txt=args.search_str,
        use_regex=args.use_rx)

    rd.collect_tags()

    write_json_file(rd.tags, os.path.join(str(Path.home()), 'temp'), 'temp.json')
    sys.exit(0)
