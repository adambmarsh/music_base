import argparse
import os
import re
import string

import music_tag
from music_meta import MusicMeta, USE_FILE_EXTENSIONS


script_description = """Set metadata tags on audio files, e.g. mp3 or flac from a yaml file.
Make sure the audio files have names composed of track numbers and titles as in the YAML file.

See example_yml dir in https://github.com/adambmarsh/music_base
"""


class TagSetter(object):

    def __init__(self, in_dir='', in_yml=''):
        self._dir = ''
        self._yml_file = ''
        self._song_tags = dict()

        self.dir = in_dir
        self.yml_file = in_yml
        self.yml = MusicMeta(base_dir=self.dir).read_yaml(os.path.join(self.dir, self.yml_file))
        self.song_tags = dict()

    @property
    def dir(self):
        return self._dir

    @dir.setter
    def dir(self, in_dir):
        self._dir = in_dir

    @property
    def yml_file(self):
        return self._yml_file

    @yml_file.setter
    def yml_file(self, in_yml):
        self._yml_file = in_yml

    def get_audio_file_list(self):
        out_files = list()

        for curr_dir, sub_dirs, files in os.walk(self.dir):
            out_files += [f for f in files if f.split('.')[-1] in USE_FILE_EXTENSIONS[:-1]]

        return out_files

    def get_track_info_from_yml(self, in_key, in_number):
        for track in self.yml.get('tracks'):
            work_key = list(track.keys())[0] if isinstance(track, dict) else track
            track_num = re.sub(r'(^\d+).+', '\\1', work_key)

            if in_number != track_num:
                continue

            alnum_key = work_key.translate(str.maketrans('', '', string.punctuation + string.whitespace + "–"))
            track_key = alnum_key.replace(track_num, '').strip()

            lkey = in_key
            rkey = track_key

            if len(in_key) > len(track_key):
                lkey = track_key
                rkey = in_key

            if lkey in rkey or lkey.lower() in rkey.lower():
                return track

        return dict()

    def track_tags_from_yml(self, file_name) -> dict:
        rx_pattern = re.compile('.' + '|'.join(USE_FILE_EXTENSIONS) + '$')
        file_base = re.sub(rx_pattern, '', file_name)
        alnum_name = file_base.translate(str.maketrans('', '', string.punctuation + string.whitespace + "–"))
        alpha_name = re.sub(r'^\d+', '', alnum_name)

        tags = dict()
        genre = self.yml.get('genre', '')

        if genre:
            tags['genre'] = genre

        tags['album'] = self.yml.get('title', '')
        tags['year'] = self.yml.get('year', '')
        tags['tracknumber'] = alnum_name.replace(alpha_name, '')
        tags['artist'] = self.yml.get('artist', '')

        if genre.lower() == 'classical':
            artist = self.yml.get('artist', '')
            if artist:
                artist_parts = artist.split(" ")
                tags['composer'] = " ".join([f"{artist_parts[-1]},"] + artist_parts[:-1])

            tags['albumartist'] = self.yml.get('performer', '')
            tags['artist'] = ", ".join([tags['artist'], tags['albumartist']])

        track_info = self.get_track_info_from_yml(alpha_name, tags['tracknumber'])
        tags['title'] = re.sub(r'^\d+ *', '', next(iter(track_info.keys()), '')
                               if isinstance(track_info, dict) else track_info)

        return tags

    def set_tags(self):
        file_names = self.get_audio_file_list()

        for f_name in file_names:
            f = music_tag.load_file(os.path.join(self.dir, f_name))
            track_tags = self.track_tags_from_yml(f_name)
            track_tags['totaltracks'] = len(file_names)

            for track_tag, tag_value in track_tags.items():
                if track_tag in ['tracknumber', 'year']:
                    f[track_tag] = int(tag_value)
                    continue

                f[track_tag] = str(tag_value)

            f.save()

        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=script_description)
    parser.add_argument("-d", "--directory", help="Full path to the directory containing audio files to which to "
                                                  "apply tags",
                        type=str,
                        dest='audio_dir',
                        required=True)
    parser.add_argument("-y", "--yaml",
                        help="Name of the yaml file from which to read tag content",
                        type=str,
                        dest='yaml_file',
                        required=True)

    args = parser.parse_args()

    ts = TagSetter(in_dir=args.audio_dir, in_yml=args.yaml_file)

    if ts.set_tags():
        exit(0)

    exit(1)
