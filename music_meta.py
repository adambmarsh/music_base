"""
This module hosts the class MusicMeta
"""
###############################################################################
#
# Copyright (C) 2022-2024 Adam Bukolt.
# All Rights Reserved.
#
###############################################################################
import datetime
import os
import re
import sys
from os import listdir
from os.path import isfile, join

import ruamel
from addict import Dict
from anyio import create_task_group
from asgiref.sync import sync_to_async
from mutagen.easyid3 import EasyID3

from mutagen.flac import FLAC, FLACNoHeaderError  # NOQA # pylint: disable=unused-import

# noinspection PyProtectedMember
from ruamel.yaml.comments import CommentedMap, CommentedSeq  # NOQA  # pylint: disable=unused-import
from tinytag import TinyTag
from orm.models import Album, Song  # NOQA # pylint: disable=unused-import, disable=import-error
import application_imports  # NOQA # pylint: disable=unused-import, disable=import-error
from utils import eval_bool_str, log_it, read_yaml, USE_FILE_EXTENSIONS  # pylint: disable=import-error

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


class MusicMeta:
    """
    This class encapsulates music metadata.
    """

    def __init__(self, base_dir, check_only=False, update_records=False, max_albums=None):
        self.split_pattern = r'[_-]+$'
        self._base_dir = base_dir
        self._candidate = {}
        self._consider = {}
        self._check_only = check_only
        self._tags = {}
        self._max_albums = -1
        self._update = False
        self.albums_existing = 0
        self.albums_new_mod = 0
        self.tags = {}
        self.created = False
        self.update = eval_bool_str(update_records)
        self.max_albums = max_albums

    @property
    def tags(self):  # pylint: disable=missing-function-docstring
        return self._tags

    @tags.setter
    def tags(self, in_tags):
        self._tags = {**self._tags, **in_tags}

    @property
    def candidate(self):  # pylint: disable=missing-function-docstring
        return self._candidate

    @property
    def consider(self):  # pylint: disable=missing-function-docstring
        return self._consider

    @property
    def check_only(self):  # pylint: disable=missing-function-docstring
        return self._check_only

    @check_only.setter
    def check_only(self, check):
        self._check_only = check

    @property
    def update(self):  # pylint: disable=missing-function-docstring
        return self._update

    @update.setter
    def update(self, in_update):
        self._update = in_update

    @property
    def base_dir(self):  # pylint: disable=missing-function-docstring
        return self._base_dir

    @base_dir.setter
    def base_dir(self, in_base_dir):
        self._base_dir = in_base_dir

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
        try:
            tag_dict = {k.lower(): v for k, v in dict(list(FLAC(f_path).tags)).items()}
            return self.map_tags(tag_dict)

        except FLACNoHeaderError:
            try:
                tag_dict = (TinyTag.get(f_path)).__dict__

            except Exception as ex:  # pylint: disable=broad-exception-caught
                log_it("debug", __name__, repr(ex))

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

    async def get_music_file_tags(self, in_file_info):
        """
        Get metadata tags from a music file
        :param in_file_info: A dictionary containing file information (path, name)
        :return: void (the result is saved in data member tags)
        """
        in_file_tags = {}
        in_dir_path = in_file_info.get('dir_path', '')
        in_dir_name = in_file_info.get('dir_name', '')
        in_file = in_file_info.get('file', '')
        in_file_tags['directory'] = re.sub(r'^/', '', re.sub(re.compile(self.base_dir), '', in_dir_path))
        in_file_tags['file'] = in_file.split('/')[-1]
        tag_dict = self.get_tags_from_file(in_file_info)

        if in_dir_name and in_dir_name not in self.tags:
            self.tags[in_dir_name] = []

        save_dict = {
            **in_file_tags,
            **{k.lower(): v for k, v in tag_dict.items() if not (k.startswith('_') or k == 'extra')}
        }

        save_dict['comment'] = self.fix_comment(save_dict.get('comment', ''))

        self.tags[in_dir_name].append(save_dict)

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
                    log_it("debug", repr(ex))
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

    def get_new_name(self, old_name):
        """
        Produce a new name for the received string containing a name of a directory.
        :param old_name: Name for which to get a rename candidate
        :return: A string containing a new name
        """
        working = self.fix_up_name(working_name=old_name)
        y = self.get_year(old_name)

        if y and y not in working:
            y_str = '__' + y
            if '__CD' in working:
                working = working.replace('__CD', y_str + '__CD')

        fy = re.findall(re.compile('[-_]+' + y), working) if (y and y in working) else \
            re.findall(r'[-_]+\d{4}', working)

        fy = re.sub(r'^_?-?', '', fy[0]) if fy else ''
        fy = '_' + y if y and not fy else fy
        fy = '_' + fy if not fy.startswith('_') else fy

        fc = re.findall(r'_+CD\d+', working)
        fc = re.sub(r'^_', '', fc[0]) if fc else ''

        working = self.fix_up_year_cd_seq(working, fy, fc, y)

        new_name = self.transpose_cd_year(working)

        return new_name

    def build_rename_list(self):
        """
        Build a list of directory names to be renamed
        :return: void (the result is stored in a member variable candidate (dict)
        """
        for dn in os.listdir(self.base_dir):
            if not os.path.isdir(os.path.join(self.base_dir, dn)):
                continue  # Not a directory
            newname = self.get_new_name(dn)
            if ('_-_' not in newname or '_-_' not in dn) and dn != newname:
                self.consider[dn] = newname

            if newname != dn:
                self.candidate[dn] = newname

    def rename(self):
        """
        Rename directories
        :return:
        """
        for dn in os.listdir(self.base_dir):
            if dn in self.candidate:
                new_name = self.candidate[dn]
                os.rename(os.path.join(self.base_dir, dn), os.path.join(self.base_dir, new_name))

    async def collect_tags(self):
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

            try:
                if curr_dir == self.base_dir:
                    continue
                # log_it("info", __name__, f"Processing: {curr_dir_name}")
                res = await sync_to_async(Album.objects.get)(path=curr_dir_name)  # NOQA

                if res:
                    self.albums_existing += 1

                if res and not self.update:
                    continue

            except Album.DoesNotExist:  # NOQA
                pass

            yml_info = await self.get_music_metadata(in_files=only_files, dir_path=curr_dir, dir_name=curr_dir_name)
            curr_dir_tags = self.tags.get(curr_dir_name)
            if not curr_dir_tags:
                continue

            track_id_map = self.map_track_ids(file_tags=curr_dir_tags)
            await sync_to_async(self.tags_to_db)(curr_dir_tags, yml_info, track_id_map)

            log_it(
                "info",
                __name__,
                f"[{self.albums_new_mod}+{self.albums_existing}] dir={curr_dir} files={len(list(only_files))}"
            )

            if self.albums_new_mod >= self.max_albums > 0:
                break

        log_it("info", __name__, f"runtime={str(datetime.datetime.now() - start_time)}")

    async def get_music_metadata(self, in_files=None, dir_path=None, dir_name=None):
        """
        Retrieve metadata from tags in .mp3, .flac, .ogg, etc. files and from a .yml if present.
        The data from tags are saved in `self.tags`, while yaml data are returned to the caller
        :param in_files: A list of files from an album/CD directory
        :param dir_path: The path to the album/CD directory
        :param dir_name: The name of the album/CD directory
        :return: A dictionary representing the contents fo the yaml file
        """
        yml_data = {}

        async with create_task_group() as tg:
            for f in in_files:
                if f.endswith("yml"):
                    yml_data = read_yaml(os.path.join(dir_path, f))
                    continue

                tg.start_soon(self.get_music_file_tags, {
                    'file': f,
                    'dir_path': dir_path,
                    'dir_name': dir_name
                })

        return yml_data

    @staticmethod
    def natural_keys(text):
        """
        list.sort(key=natural_keys) sorts in human order
        http://nedbatchelder.com/blog/200712/human_sorting.html
        :param text: A string from which to create a list of natural keys
        """
        return [int(c) if c.isdigit() else c for c in re.split(r'([:;!\-,/ ]+)', text) if c]

    def map_track_ids(self, file_tags=None):
        """
        Create a mapping of album track IDs
        :param file_tags: A list of file (song) tag dictionaries
        :return: A dictionary mapping actual track numbers to 0-based list of files
        """
        if not file_tags:
            return None

        rx_pattern = re.compile(f"({'|'.join(USE_FILE_EXTENSIONS)})$")
        ids_list = [ft.get('track', None) for ft in file_tags if re.search(rx_pattern, ft.get('file', None))]
        ids_list = [id_obj for id_obj in ids_list if id_obj]

        if not ids_list:
            return {}

        try:
            ids_list.sort(key=self.natural_keys if isinstance(ids_list[0], str) else None)
        except TypeError as te:
            log_it("debug", __name__, repr(te))

        return {f_id: ix for ix, f_id in enumerate(ids_list)}

    @staticmethod
    def determine_album_title(tags):
        """
        Determine the album title
        :param tags: Album metadata tags
        :return: A string with the album title on success, an empty string on failure
        """
        if not tags:
            return None

        for song_tags in tags:
            album_title = song_tags.get('album', None)

            if 'Various' in song_tags.get('directory', '') or not album_title:
                return song_tags.get('directory', '')

            return album_title

        return ''

    @staticmethod
    def determine_album_label(tags=None, non_tag_info=None):
        """
        Determine the album label
        :param tags: Album metadata tags
        :param non_tag_info: Metadata from a YAML file for the album
        :return: A string with the album label on success, an empty string on failure
        """
        if not tags:
            tags = {}

        if not non_tag_info:
            non_tag_info = {}

        label = ''

        for song_tags in tags:
            if 'Various' in song_tags.get('directory', ''):
                return label

            label = song_tags.get('label', None)

            if label:
                return label

        label = non_tag_info.get('label', '')

        return label

    @staticmethod
    def determine_album_year(tags, non_tag_info=None):
        """
        Determine the album release year.
        :param tags: Album metadata tags
        :param non_tag_info: Metadata from an album YAML file
        :return: Album release year as an int on success, 1900 on failure
        """
        if not non_tag_info:
            non_tag_info = {}

        try:
            default_year = int(non_tag_info.get('year', 1900))
        except (TypeError, ValueError):
            default_year = 1900

        if not tags or 'Various' in non_tag_info.get('artist', '') or default_year > 1900:
            return default_year

        for song_tags in tags:
            if 'Various' in song_tags.get('directory', ''):
                return default_year

            year = song_tags.get('year', song_tags.get('date', '')) or ''

            if year:
                try:
                    return int(year.strip())
                except ValueError:
                    return default_year

        return default_year

    @staticmethod
    def determine_album_artist(tags, non_tag_info=None):
        """
        Get the name of the album artist
        :param tags: Album metadata tags
        :param non_tag_info: Metadata from a YAML file for the album
        :return: A string containing the name of the album artist on success, an empty string on failure
        """
        if not non_tag_info:
            non_tag_info = {}

        default_artist = non_tag_info.get('artist', '')

        if not tags or default_artist == 'Various':
            return default_artist

        artist = ''

        for song_tags in tags:
            if 'Various' in next(iter(re.split(r'(_-_|[0-9]{4})', song_tags.get('directory', ''))), ""):
                return default_artist

            artist = song_tags.get('artist', song_tags.get('albumartist', song_tags.get('composer', '')))

            if artist:
                return artist

        return artist

    @staticmethod
    def determine_album_composer(tags, non_tag_info=None):
        """
        Get the name of the album composer.
        :param tags: Album metadata tags
        :param non_tag_info: Metadata from a YAML file for the album
        :return: A string containing the name of the composer on success, an empty string on failure
        """
        if not non_tag_info:
            non_tag_info = {}

        default_composer = non_tag_info.get('composer', '')

        if not tags or default_composer == 'Various':
            return default_composer

        composer = ''

        for song_tags in tags:
            if 'Various' in song_tags.get('directory', ''):
                return default_composer

            composer = song_tags.get('composer', default_composer)

            if not composer:
                composer = song_tags.get('albumartist', song_tags.get('artist', ''))

            if composer:
                return composer

        return composer

    @staticmethod
    def determine_album_path(tags):
        """
        Get the album path from the received tags.
        :param tags: Dictionary of tags from which to get the path
        :return: A string containing the album path
        """
        if not tags:
            return ''

        return tags[0].get('directory', '')

    def credits_add_composer(self, in_credits=None, in_composer=""):
        """
        Add composer to album credits.
        :param in_credits: Credits (list) to which to add composer
        :param in_composer: A string containing the name of the composer
        :return: Credits extended with the composer's name
        """
        if not in_composer:
            return in_credits or []

        if not in_credits:
            in_credits = []

        if isinstance(in_credits, str):
            in_credits = list([in_credits])

        work_credits = []

        for credit in in_credits:
            if isinstance(credit, str):
                work_credits.append(credit)
                continue

            if isinstance(credit, dict):
                credit_as_str = self.render_as_str(credit)
                work_credits.append(re.sub(r'[\[\]\']+', '', credit_as_str))

                continue

            continue

        if not [cred for cred in work_credits if "composer" in cred.lower() or "composed by" in cred.lower()]:
            in_credits.append(f"Composed by - {in_composer}")

        return work_credits

    def determine_album_comment(self, tags, non_tag_info=None):
        """
        Get the comment for an album, using metadata tags and/or info from a YAML file. The comment is
        one string combining any credits, description and notes
        :param tags: Metadata tags
        :param non_tag_info: Tag data from the YAML file
        :return: A string containing the comment
        """
        if not tags:
            return ''

        if not non_tag_info:
            return tags[0].get('comment', None)

        description = non_tag_info.get('description', None)
        description = "" if not description else description
        # Use credits and/or notes to build a comment
        composer = self.determine_album_composer(tags, non_tag_info)
        working_credits = list(non_tag_info.get('credits', []))
        working_credits = self.credits_add_composer(in_credits=working_credits, in_composer=composer)

        cd_credits = self.credits_as_str(working_credits)
        notes = self.notes_as_str(non_tag_info.get('notes', None))

        comment_parts = [part for part in [description, cd_credits, notes] if part]
        return "\n".join(comment_parts) or ""

    def determine_song_comment(self, tags, non_tag_track_data=None):
        """
        Get the comment for a song, using metadata tags and/or info from a YAML file. The comment is
        one string combining any credits and the comment field (metadata)
        :param tags: Metadata tags
        :param non_tag_track_data: Tag data from the YAML file
        :return: A string containing the comment
        """
        tag_comment = tags.get('comment', "")
        if not tag_comment:
            tag_comment = ""

        # Remove junk content from comment:
        tag_comment = re.sub(r'X{3,}DURATION[0-9:.]+', '', tag_comment.strip())

        if not non_tag_track_data or not isinstance(non_tag_track_data, dict):
            return tag_comment

        song_comment = song_credits = ""
        for value in non_tag_track_data.values():
            try:
                song_credits = value.get('credits', '')
                song_credits = self.render_as_str(song_credits, in_lead="") if song_credits else \
                    self.get_song_credits_from_dict(song_credits, value)
            except AttributeError:
                song_credits = ''

            try:
                song_comment = value.get('comment', '')
                song_comment = self.render_as_str(song_comment, in_lead="")
            except AttributeError:
                song_comment = ''

        comment_parts = [c for c in [tag_comment, str(song_comment or ''), str(song_credits or '')] if c.strip()]

        return "\n".join(comment_parts) if comment_parts else ""

    def get_song_credits_from_dict(self, in_credits, in_dict):
        """
        Get song credits from received dict
        :param in_credits: Existing credits
        :param in_dict: Dictionary from which to retrieve credits
        :return:  A string containing song credits
        """
        if not isinstance(in_dict, dict):
            return in_credits

        for nm, vl in in_dict.items():
            if nm == 'duration':
                continue

            if not isinstance(vl, dict):
                continue

            sub_song_credits = vl.get('credits', '')
            if not sub_song_credits:
                continue

            in_credits += f"\n{nm} " + self.render_as_str(sub_song_credits, in_lead="")

        return in_credits

    @staticmethod
    def determine_song_year(tag_year, non_tag_year):
        """
        Determine the release year for a song
        :param tag_year: A year value from a metadata tag
        :param non_tag_year: A year value from YAML
        :return: Integer representing the year
        """
        try:
            return int(tag_year)
        except (TypeError, ValueError):
            try:
                return int(non_tag_year)
            except (TypeError, ValueError):
                return 1900

    def credits_as_str(self, in_credits):
        """
        Convert a list of credits to a string
        :param in_credits: An int to convert
        :return: String representation of the received object
        """
        if not in_credits:
            return ""

        return self.render_as_str(in_credits, in_lead="")

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

    def notes_as_str(self, in_notes):
        """
        Convert notes (typically a list) to a string.
        :param in_notes: Notes to convert
        :return: A string containing the notes
        """
        if not in_notes:
            return ""

        return self.render_as_str(in_notes, in_lead="")

    def album_tags_to_db(self, in_tags, in_yml_data=None):
        """
        Save Album tags to db -- create a row if necessary or update
        :param in_tags: a set of tags from which to extract values
        :param in_yml_data: a dictionary containing information extraction from a yml file
        :return: an Album instance (new or updated, or existing)
        """
        album_name = self.determine_album_title(in_tags)
        album_label = self.determine_album_label(in_tags, in_yml_data)
        album_year = self.determine_album_year(in_tags, in_yml_data) or 1900
        album_path = self.determine_album_path(in_tags)
        album_artist = self.determine_album_artist(in_tags, in_yml_data)
        album_comment = self.fix_comment(self.determine_album_comment(in_tags, in_yml_data))

        album_dict = {
            'title': album_name,
            'artist': album_artist,
            'comment': album_comment,
            'label': album_label,
            'path': album_path,
            'date': datetime.datetime(album_year, 1, 1)
        }
        album_identifiers = ['title', 'artist', 'path']

        new_mod = 0
        try:
            db_album = Album.objects.get(**{k: v for k, v in album_dict.items() if k in album_identifiers})  # NOQA
            use_date = db_album.date if (db_album.date and album_year == db_album.date.year) else \
                datetime.datetime(album_year or 1900, 1, 1)
            album_dict['date'] = use_date
            updates = {k: v for k, v in album_dict.items() if v != db_album.__dict__.get(k, None)}

            if not updates:
                return db_album, new_mod

            new_mod = 1
            db_album.__dict__.update(**updates)
            db_album.save()
        except Album.DoesNotExist:  # NOQA
            new_mod = 1
            db_album = Album(**album_dict)
            db_album.save()
        except ValueError:
            log_it('error', __name__, f"\n{repr(album_dict)}")
            sys.exit(111)

        return db_album, new_mod

    def song_field_dict(self, in_tags, album_inst, non_tag_data=None, song_id_map=None):
        """
        Build a dictionary of all the fields in Song from tags and non-tag data
        :param in_tags: A set of tags from which to extract values
        :param album_inst: Instance of Album (from DB)
        :param non_tag_data: Metadata retrieved from the album yaml file (if any)
        :param song_id_map: A dict mapping string song id's in an album/collection to numeric indexes
        :return: True if a new Song row has been created, otherwise False
        """
        if not non_tag_data:
            non_tag_data = {}

        tag_data = Dict(in_tags)

        if 'track' not in tag_data.keys():
            tag_data.track = -1

        try:
            track = song_id_map.get(tag_data.track, -1) if song_id_map else -1
        except TypeError:
            log_it('error', __name__, f"\n{repr(tag_data)}")
            track = -1

        ext_track_data = [] if not non_tag_data else non_tag_data.get('tracks', [])
        track_data = ext_track_data[track] if (ext_track_data and 0 <= track < len(ext_track_data)) else {}

        year = self.determine_song_year(tag_data.year, non_tag_data.get('year', 1900))
        use_date = album_inst.date if (album_inst and year == album_inst.date.year) else \
            datetime.datetime(year or 1900, 1, 1)

        return {
            'title': tag_data.title or '',
            'file': tag_data.file or '',
            'track_id': (track + 1) if track > 0 else -1,
            'comment': self.determine_song_comment(in_tags, track_data),
            'genre': tag_data.genre or non_tag_data.get('genre', ''),
            'artist': tag_data.artist or non_tag_data.get('artist', ''),
            'performer': tag_data.albumartist or '',
            'composer': tag_data.composer or '',
            'date': use_date,
            'album_id': album_inst.id
        }

    def song_tags_to_db(self, music_tags, album_obj, meta_data=None, id_map=None):
        """
        Save Song tags to db -- create a row if necessary or update
        :param music_tags: A set of tags from which to extract values
        :param album_obj: Instance of Album
        :param meta_data: Metadata retrieved from the album yaml file (if any)
        :param id_map: A dict mapping string song id's in an album/collection to numeric indexes
        :return: True on creation or update, otherwise False
        """
        song_dict = self.song_field_dict(music_tags, album_obj, meta_data, id_map)
        song_identifiers = ['title', 'file', 'artist']
        new_mod = 0

        try:
            db_song = Song.objects.get(**{k: v for k, v in song_dict.items() if k in song_identifiers})  # NOQA
            updates = {k: v for k, v in song_dict.items() if v != db_song.__dict__.get(k, None)}

            if not updates:
                return new_mod

            new_mod = 1
            db_song.__dict__.update(**updates)
            db_song.save()

        except Song.DoesNotExist:  # NOQA
            new_mod = 1
            db_song = Song(**song_dict)
            db_song.save()

        return new_mod

    def tags_to_db(self, dir_tags, from_yaml=None, id_map=None):
        """
        Write album and song tags to db (top level).
        :param dir_tags: Tags read from files in a directory (music files)
        :param from_yaml: Tags read from a YAML file
        :param id_map: A mapping of track ID's
        :return: void
        """
        album, new_or_mod = self.album_tags_to_db(dir_tags, from_yaml)

        for tags in dir_tags:
            new_or_mod += self.song_tags_to_db(tags, album, from_yaml, id_map)

        if new_or_mod > 0:
            self.albums_new_mod += 1
