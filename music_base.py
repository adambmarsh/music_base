import argparse
import datetime
import os
import re
import sys
from os import listdir
from os.path import isfile, join

import yaml
from addict import Dict
from anyio import create_task_group, run
# noinspection PyProtectedMember
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC, FLACNoHeaderError  # NOQA
from tinytag import TinyTag
import application_imports  # NOQA
from asgiref.sync import sync_to_async
from utils import eval_bool_str, log_it
from orm.models import Album, Song  # NOQA
# from django.db.models import Q


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
USE_FILE_EXTENSIONS = ["ape", "flac", "mp3", "ogg", "wma", "yml"]


class MusicMeta(object):
    def __init__(self, base_dir, check_only=False, update_records=False, max_albums=None):
        self._base_dir = base_dir
        self._candidate = dict()
        self._consider = dict()
        self._check_only = check_only
        self._tags = dict()
        self._max_albums = -1
        self._update = False

        self.tags = dict()
        self.CREATED = False
        self.update = eval_bool_str(update_records)
        self.max_albums = max_albums

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, in_tags):
        self._tags = dict(**self._tags, **in_tags)

    @property
    def candidate(self):
        return self._candidate

    @property
    def consider(self):
        return self._consider

    @property
    def check_only(self):
        return self._check_only

    @check_only.setter
    def check_only(self, check):
        self._check_only = check

    @property
    def update(self):
        return self._update

    @update.setter
    def update(self, in_update):
        self._update = in_update

    @property
    def base_dir(self):
        return self._base_dir

    @base_dir.setter
    def base_dir(self, in_base_dir):
        self._base_dir = in_base_dir

    @property
    def max_albums(self):
        return self._max_albums

    @max_albums.setter
    def max_albums(self, in_limit):
        self._max_albums = int(in_limit if in_limit else -1)

    @staticmethod
    async def test_get_file_tags(in_file_info):
        in_dir = in_file_info.get('dir', '')
        in_file = in_file_info.get('file', '')

        print(f"dir={in_dir} file={in_file}")

    async def get_music_file_tags(self, in_file_info):
        in_file_tags = dict()
        in_dir_path = in_file_info.get('dir_path', '')
        in_dir_name = in_file_info.get('dir_name', '')
        in_file = in_file_info.get('file', '')
        in_file_tags['directory'] = re.sub(r'^/', '', re.sub(re.compile(self.base_dir), '', in_dir_path))
        in_file_tags['file'] = in_file.split('/')[-1]
        file_path = os.path.join(in_dir_path, in_file)
        tag_dict = (TinyTag.get(file_path)).__dict__

        if in_dir_name and in_dir_name not in self.tags.keys():
            self.tags[in_dir_name] = list()

        save_dict = dict(
            **in_file_tags,
            **{k.lower(): v for k, v in tag_dict.items() if not (k.startswith('_') or k == 'extra')}
        )

        self.tags[in_dir_name].append(save_dict)

    def get_year_from_tags(self, dir_name):
        my_path = join(self.base_dir, dir_name)
        only_files = [str(join(my_path, f)) for f in listdir(my_path) if isfile(join(my_path, f))]

        only_files = [f for f in only_files if re.search(r'\.(flac|mp3|ogg|wma)$', f)]

        for f in only_files:
            try:
                print(f)
                tag_dict = dict(list(FLAC(f).tags))
                return tag_dict.get('DATE', tag_dict.get('YEAR', ''))

            except FLACNoHeaderError:
                try:
                    rel_date = EasyID3(f).get('date', '')
                    return rel_date if not isinstance(rel_date, list) else next(iter(rel_date), '')

                except Exception as ex:
                    print(repr(ex))
                    continue

        return None

    def get_year(self, dir_name):
        if 'Various' in dir_name:
            return None

        y = self.get_year_from_tags(dir_name)

        if not y:
            return None

        y = re.sub(r'[()]', '', re.sub(r'[/ ]+', r'-', y))

        if len(y) > MAX_YEAR_DIGITS:
            ns = y.split('-')

            ys = list()

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
        if 'CD' not in in_str:
            return in_str

        if not re.findall(r'\[\d{4}]', in_str):
            return in_str

        return re.sub(r'(CD\d+)_(\[\d{4}])', '\\2_\\1', in_str)

    @staticmethod
    def fix_one_off_names(in_working):

        surnames = [
            'Hiromi_', 'Illinois_Jacquet_', 'KlausSchulze_', 'Kalyi_Jag_', 'Yes_', 'Yusef_Lateef_', 'Souad_Massi__'
        ]

        name_replacements = dict()

        for surname in surnames:
            name_replacements[surname] = surname + '_-_' if not surname.endswith('_') else surname + '-_'

        for k, v in name_replacements.items():
            if not in_working.startswith(k):
                continue

            if '_-_' in in_working:
                continue

            return re.sub(k, v, in_working)

        if in_working.startswith('L_Shankar_others') and '_-_' not in in_working:
            return re.sub(r'L_Shankar_', 'L_Shankar_-_', in_working)

        if in_working.startswith('Beethoven_-_') and '_L_v_-_' not in in_working:
            return re.sub(r'Beethoven_-_', 'Beethoven_L_v_-_', in_working)

        if in_working.startswith('Mozart_-_') and '_WA_-_' not in in_working:
            return re.sub(r'Mozart_-_', 'Mozart_WA_-_', in_working)

        return in_working

    def fix_up_name(self, working_name):
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
        w_str = re.sub(r'[_-]+$', '', in_str)
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
        if not work_c + work_y or not year:
            return work_str

        work_str = re.sub(work_y + work_c, '', work_str)
        work_str = re.sub(re.compile(work_c + r'$'), '', work_str)
        work_str = re.sub(re.compile(work_y + r'[-_]*$'), '', work_str)
        work_str = re.sub(re.compile('-_' + work_c + work_y), '', work_str)
        work_str = re.sub(re.compile('-_*' + work_y + '_' + work_c), '-_', work_str)

        w_split = self.split_work_str(work_str)

        if work_y:
            work_y = re.sub(r'[_-]+(\d+)', '_[\\1]_' if (not year or year in work_y) else '_[' + year + ']_', work_y)
        elif work_c:
            work_c = work_c + '_'

        if isinstance(w_split, list) and len(w_split) > 1:
            w_split[1] = re.sub(r'^_\d{4}', '', re.sub(re.compile('^' + work_c), '', w_split[1]))
            work_str = re.sub(
                r'_+', '_', w_split[0] + '_-_' + work_c + (work_y if work_c not in w_split[1] else '')) \
                + '__'.join(w_split[1:]
                            )
        else:
            work_str = w_split[0] + re.sub(r'_+', '_', '_-_' + work_c + work_y)

        # Remove release year from the end, then remove '_-' for and multiple underscores:
        if year:
            work_str = re.sub(re.compile('_+' + year + r'$'), '', work_str)

        work_str = re.sub(r'[_-]+$', '', work_str)
        work_str = re.sub(r'___', '__', work_str)

        # Remove CD{number}_{year}, note {year} is not surrounded by []:
        if work_c:
            work_str = re.sub(re.compile(work_c + r'?_\d{4}' + work_c + r'?'), '', work_str)

        # Remove trailing '_' and '_':
        return re.sub(r'[_-]+$', '', re.sub(r'_+-_+', '_-_', work_str))

    def get_new_name(self, old_name):
        working = self.fix_up_name(working_name=old_name)
        y = self.get_year(old_name)

        if y and y not in working:
            y_str = '__' + y
            if '__CD' in working:
                working = re.sub(r'__CD', r'' + y_str + r'__CD', working)

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
        for dn in os.listdir(self.base_dir):
            if not os.path.isdir(os.path.join(self.base_dir, dn)):
                continue  # Not a directory
            newname = self.get_new_name(dn)
            # print("newname={}".format(newname))
            # print("dn={}".format(dn))
            if ('_-_' not in newname or '_-_' not in dn) and dn != newname:
                self.consider[dn] = newname

            if newname != dn:
                self.candidate[dn] = newname

    def rename(self):
        for dn in os.listdir(self.base_dir):
            if dn in self.candidate:
                new_name = self.candidate[dn]
                os.rename(os.path.join(self.base_dir, dn), os.path.join(self.base_dir, new_name))

    async def collect_tags(self):
        counter_albums = 0
        start_time = datetime.datetime.now()

        for curr_dir, sub_dirs, files in os.walk(self.base_dir):
            only_files = [f for f in files if f.split('.')[-1] in USE_FILE_EXTENSIONS]
            curr_dir_name = re.sub(r'^/', '', re.sub(re.compile(self.base_dir), '', curr_dir))

            log_it("info", __name__, f"dir={curr_dir} file_count={len(list(only_files))}")

            try:
                if curr_dir == self.base_dir:
                    continue

                res = await sync_to_async(Album.objects.get)(path=curr_dir_name)  # NOQA
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
            counter_albums += 1

            if self.max_albums < 0:
                continue

            if counter_albums >= self.max_albums:
                break

        log_it("info", __name__, f"runtime={str(datetime.datetime.now() - start_time)}")
        return

    async def get_music_metadata(self, in_files=None, dir_path=None, dir_name=None):
        """
        Retrieve metadata from tags in .mp3, .flac, .ogg, etc. files and from a .yml if present.
        The data from tags are saved in self.tags, while yaml data are eturned to the caller
        :param in_files: A list of files from an album/CD directory
        :param dir_path: The path to the album/CD directory
        :param dir_name: The name of the album/CD directory
        :return: A dictionary representing the contents fo the yaml file
        """
        yml_data = dict()

        async with create_task_group() as tg:
            for f in in_files:
                if f.endswith("yml"):
                    yml_data = self.read_yaml(os.path.join(dir_path, f))
                    continue

                tg.start_soon(self.get_music_file_tags, {
                    'file': f,
                    'dir_path': dir_path,
                    'dir_name': dir_name
                })

        return yml_data

    @staticmethod
    def map_track_ids(file_tags=None):
        if not file_tags:
            return None

        rx_pattern = re.compile(f"({'|'.join(USE_FILE_EXTENSIONS)})$")
        ids_list = [ft.get('track', '') for ft in file_tags if re.search(rx_pattern, ft.get('file', ''))]
        ids_list = [id_str for id_str in ids_list if id_str]

        if not ids_list:
            return {}

        ids_list = sorted(ids_list, key=int)

        return {f_id: ix for ix, f_id in enumerate(ids_list)}

    @staticmethod
    def determine_album_title(tags):
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
        if not tags:
            tags = dict()

        if not non_tag_info:
            non_tag_info = dict()

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
        if not non_tag_info:
            non_tag_info = dict()

        try:
            default_year = int(non_tag_info.get('year', 1900))
        except (TypeError, ValueError):
            default_year = 1900

        if not tags or 'Various' in non_tag_info.get('artist', '') or default_year > 1900:
            return default_year

        for song_tags in tags:
            if 'Various' in song_tags.get('directory', ''):
                return default_year

            year = song_tags.get('year', '') or ''

            if year:
                try:
                    return int(year.strip())
                except ValueError:
                    return default_year

        return default_year

    @staticmethod
    def determine_album_artist(tags, non_tag_info=None):
        if not non_tag_info:
            non_tag_info = dict()

        default_artist = non_tag_info.get('artist', '')

        if not tags or default_artist == 'Various':
            return default_artist

        artist = ''

        for song_tags in tags:
            if 'Various' in song_tags.get('directory', ''):
                return default_artist

            artist = song_tags.get('artist', song_tags.get('albumartist', song_tags.get('composer', '')))

            if artist:
                return artist

        return artist

    @staticmethod
    def determine_album_path(tags):
        if not tags:
            return ''

        return tags[0].get('directory', '')

    def determine_album_comment(self, tags, non_tag_info=None):
        if not tags:
            return ''

        if not non_tag_info:
            return tags[0].get('comment', None)

        description = non_tag_info.get('description', None)
        description = "" if not description else description
        # Use credits and/or notes to build a comment
        cd_credits = self.credits_as_str(non_tag_info.get('credits', None))
        notes = self.notes_as_str(non_tag_info.get('notes', None))

        comment_parts = [part for part in [description, cd_credits, notes] if part]
        return "\n".join(comment_parts) or ""

    def determine_song_comment(self, tags, non_tag_track_data=None):
        tag_comment = tags.get('comment', "")
        if not tag_comment:
            tag_comment = ""

        tag_comment = tag_comment.strip()

        if not non_tag_track_data or not isinstance(non_tag_track_data, dict):
            return tag_comment

        song_comment = song_credits = ""
        for name, value in non_tag_track_data.items():
            song_credits = value.get('credits', '')

            if song_credits:
                song_credits = self.render_as_str(song_credits, in_lead="")
            else:
                if isinstance(value, dict):
                    for nm, vl in value.items():
                        if nm == 'duration':
                            continue

                        if not isinstance(vl, dict):
                            continue

                        sub_song_credits = vl.get('credits', '')
                        if not sub_song_credits:
                            continue

                        song_credits += f"\n{nm} " + self.render_as_str(sub_song_credits, in_lead="")

            song_comment = value.get('comment', '')
            song_comment = self.render_as_str(song_comment, in_lead="")

        comment_parts = [c for c in [tag_comment, str(song_comment or ''), str(song_credits or '')] if c.strip()]

        return "\n".join(comment_parts) if comment_parts else ""

    @staticmethod
    def determine_song_year(tag_year, non_tag_year):
        try:
            return int(tag_year)
        except (TypeError, ValueError):
            try:
                return int(non_tag_year)
            except (TypeError, ValueError):
                return 1900

    def credits_as_str(self, in_credits):
        if not in_credits:
            return []

        return self.render_as_str(in_credits, in_lead="")

    @staticmethod
    def int_type_as_str(in_int, lead="\n"):
        return f"{lead}{str(in_int)}"

    @staticmethod
    def str_type_as_str(in_str, lead="\n"):
        return f"{lead}{str(in_str)}"

    def list_type_as_str(self, in_list, in_lead="\n"):
        outcome = list()
        item_lead = "\n - " if "--" not in in_lead else in_lead
        for list_item in in_list:
            outcome.append(self.render_as_str(list_item, in_lead=item_lead))

        out_lead = "" if "--" in item_lead else in_lead
        return out_lead.join(outcome)

    def dict_type_as_str(self, in_dict, lead="\n"):
        outcome = list()

        for k, v in in_dict.items():
            outcome.append(f"\n - {k}:" + self.render_as_str(v, " "))

        use_lead = "  - " if '-' in lead else ""
        return use_lead.join(outcome)

    @staticmethod
    def date_type_as_str(in_date, lead=""):
        return f"{lead}{str(in_date)}"

    def render_as_str(self, in_item, in_lead="\n"):
        # if not in_item:
        #     return ''

        type_select = {
            int: self.int_type_as_str,
            str: self.str_type_as_str,
            dict: self.dict_type_as_str,
            list: self.list_type_as_str,
            datetime.date: self.date_type_as_str
        }

        return type_select[type(in_item)](in_item, in_lead)

    def notes_as_str(self, in_notes):
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
        album_comment = self.determine_album_comment(in_tags, in_yml_data)

        album_dict = {
            'title': album_name,
            'artist': album_artist,
            'comment': album_comment,
            'label': album_label,
            'path': album_path,
            'date': datetime.datetime(album_year, 1, 1)
        }
        album_identifiers = ['title', 'artist', 'path']

        try:
            db_album = Album.objects.get(**{k: v for k, v in album_dict.items() if k in album_identifiers})  # NOQA
            use_date = db_album.date if (db_album.date and album_year == db_album.date.year) else \
                datetime.datetime(album_year or 1900, 1, 1)
            album_dict['date'] = use_date
            updates = {k: v for k, v in album_dict.items() if v != db_album.__dict__.get(k, None)}

            db_album.__dict__.update(**updates)
            db_album.save()
        except Album.DoesNotExist:  # NOQA
            db_album = Album(**album_dict)
            db_album.save()

        return db_album

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
            non_tag_data = dict()

        tag_data = Dict(in_tags)
        track = song_id_map.get(tag_data.track) if song_id_map else -1
        ext_track_data = list() if not non_tag_data else non_tag_data.get('tracks', [])
        track_data = ext_track_data[track] if (ext_track_data and 0 <= track < len(ext_track_data)) else dict()

        year = self.determine_song_year(tag_data.year, non_tag_data.get('year', 1900))
        use_date = album_inst.date if (album_inst and year == album_inst.date.year) else \
            datetime.datetime(year or 1900, 1, 1)

        return {
            'title': tag_data.title or '',
            'file': tag_data.file or '',
            'track_id': (track + 1) or -1,
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

        try:
            db_song = Song.objects.get(**{k: v for k, v in song_dict.items() if k in song_identifiers})  # NOQA
            updates = {k: v for k, v in song_dict.items() if v != db_song.__dict__.get(k, None)}

            if not updates:
                return False

            db_song.__dict__.update(**updates)
            db_song.save()
            return True
        except Song.DoesNotExist:  # NOQA
            db_song = Song(**song_dict)
            db_song.save()
            return True

    def tags_to_db(self, dir_tags, from_yaml=None, id_map=None):
        album = self.album_tags_to_db(dir_tags, from_yaml)

        for tags in dir_tags:
            self.song_tags_to_db(tags, album, from_yaml, id_map)

        return

    @staticmethod
    def read_yaml(f_path):
        f_contents = dict()

        try:
            with open(f_path) as f_yml:
                f_contents = yaml.load(f_yml, Loader=yaml.FullLoader)
        except yaml.scanner.ScannerError as e:  # NOQA
            log_it("debug", __name__, f"Bad yaml in {f_path}: {e}")
            pass
        except yaml.parser.ParserError as e:  # NOQA
            log_it("debug", __name__, f"Bad yaml in {f_path}: {e}")
            pass

        return f_contents


async def main():
    # basedir = '/home/adam/lanmount/music'# '/home/adam/Music'
    # basedir = '/home/adam/lanmount/share/music'

    parser = argparse.ArgumentParser(description="This program normalises names of music file directories to use "
                                                 "underscores instead of spaces, etc.")
    parser.add_argument("-d", "--directory", help="Full path to the parent directory containing sub-directories with "
                                                  "music files, for example '/home/adam/music'",
                        type=str,
                        dest='base_dir',
                        required=True)
    parser.add_argument("-c", "--check_only",
                        help="If provided, ensures that the program lists possible changes without making them.",
                        type=bool,
                        dest='check_only',
                        default=False,
                        required=False)

    parser.add_argument("-t", "--tags_only",
                        help="If provided, causes the program to collect tags, without making any changes.",
                        type=bool,
                        dest='tags_only',
                        default=False,
                        required=False)

    parser.add_argument("-l", "--limit",
                        help="If provided, determines the max number of album directories to scan.",
                        type=int,
                        dest='limit',
                        default=-1,
                        required=False)

    parser.add_argument("-u", "--update",
                        help="If evaluates to True, causes updates to existing records and creation of new ones,"
                             "otherwise only new records are created",
                        type=str,
                        dest='update',
                        default='',
                        required=False)

    args = parser.parse_args()

    rd = MusicMeta(
        base_dir=args.base_dir,
        check_only=args.check_only,
        max_albums=args.limit,
        update_records=args.update)

    if args.tags_only:
        await rd.collect_tags()
        exit(0)

    rd.build_rename_list()

    if len(rd.candidate) > 0:
        print('\nChanges to make: ')
        for k, v in sorted(rd.candidate.items()):
            print(k + ': ' + v)

    if len(rd.consider) > 0:
        print('\nConsider changing:')
        for k, v in sorted(rd.consider.items()):
            print(k + ': ' + v)

    if rd.check_only:
        sys.exit(0)

    from_user = input("Press 'Y' to make changes or any other key to cancel...")

    if from_user.lower() == 'y':
        rd.rename()


run(main)
# if __name__ == '__main__':
#     main()
