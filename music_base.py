"""
Top-level module for managing music meta data and saving it to DB.
"""
import argparse
import sys

# from mutagen.flac import FLAC, FLACNoHeaderError  # NOQA
import application_imports  # NOQA # pylint: disable=unused-import, disable=import-error
from anyio import run
from music_meta import MusicMeta  # pylint: disable=import-error
from orm.models import Album, Song  # NOQA  # pylint: disable=unused-import, disable=import-error

__version__ = '0.2.2'

PROGRAM_DESCRIPTION = "This program normalises names of music file directories to use" + \
                      " underscores instead of spaces, etc."


async def main():
    """
    Main function
    :return: void
    """
    parser = argparse.ArgumentParser(description=PROGRAM_DESCRIPTION)
    parser.add_argument("-d",
                        "--directory",
                        help="Full path to the parent directory containing"
                             " sub-directories with music files, for example '/home/adam/music'",
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
        sys.exit(0)

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
