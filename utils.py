# !/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module contains utility functions
"""

###############################################################################
#
# Copyright (C) 2022-2024 Adam Bukolt.
# All Rights Reserved.
#
###############################################################################
import itertools
import logging
import json
import os
import re
from enum import Enum
from ruamel.yaml import YAML
from ruamel.yaml.parser import ParserError
from ruamel.yaml.scanner import ScannerError

SEC_IN_DAY = 24 * 3600

OUT_RELATIVE_PATH = '/../out/'

USE_FILE_EXTENSIONS = ["ape", "flac", "mp3", "ogg", "wma", "yml"]


def log_it(level='info', src_name=None, text=None):
    """
    Logger function
    :param level: String specifying the log level
    :param src_name: String containing the name of the logging module
    :param text: A string containing the log message
    :return: void
    """
    logging.basicConfig(level=logging.DEBUG)
    logger_name = src_name if src_name else __name__
    log_writer = logging.getLogger(logger_name)

    do_log = {
        "info": log_writer.info,
        "error": log_writer.error,
        "warning": log_writer.warning,
    }

    do_log.get(level, log_writer.debug)(text)


def run_scandir(in_dir, ext):  # dir: str, ext: list
    """
    Find all the subdirectories and files in them. If ext is provided, list only files with matching extension
    :param in_dir: Input directory or which subdirectories are to be listed
    :param ext: File extension to match
    :return: A list of subdirectories and a list of files in them
    """
    sub_dirs = []
    fn_files = []

    for f in list(os.scandir(in_dir)):
        if f.is_dir():
            sub_dirs.append(f.path)
        if f.is_file():
            fn_ext_lower = os.path.splitext(f.name)[1].lower()
            if not ext or (ext and fn_ext_lower and fn_ext_lower in ext):
                fn_files.append(f.path)

    for directory in list(sub_dirs):
        sf, f = run_scandir(directory, ext)
        sub_dirs.extend(sf)
        fn_files.extend(f)

    sub_dirs.append(in_dir)

    return sub_dirs, fn_files


def read_file(filename, dest_dir=None):
    """
    Read specified file
    :param filename: The name of the file to read
    :param dest_dir: The directory where the file is
    :return: The contents of the file as a String
    """
    cur_dir = os.getcwd()

    if not dest_dir:
        dest_dir = cur_dir + OUT_RELATIVE_PATH

    filepath = os.path.join(dest_dir, filename)

    try:
        with open(filepath, 'r', encoding="UTF-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Missing: {filepath}")
        return ''


def read_yaml(f_path):
    """
    Read YAML file and return contents as a dict
    :param f_path: Path to file to read
    :return: File content as a dict
    """
    f_contents = {}
    yaml = YAML()

    try:
        with open(f_path, encoding="UTF-8") as f_yml:
            f_contents = yaml.load(f_yml)
    except ScannerError as e:  # NOQA
        log_it("debug", __name__, f"Bad yaml in {f_path}: {e}")
    except ParserError as e:  # NOQA
        log_it("debug", __name__, f"Bad yaml in {f_path}: {e}")

    return f_contents


def write_json_file(page_dict, dest_dir=None, filename='temp', sort_keys=True):
    """
    Write a JSON file.
    :param page_dict: A dictionary containing the data to write to file
    :param dest_dir:Destination directory
    :param filename: The name of the file as a string
    :param sort_keys: A flag indicating whether to sort the keys in the output file
    :return: Always True
    """
    cur_dir = os.getcwd()

    if not os.path.isdir(dest_dir):
        dest_dir = cur_dir

    filepath = os.path.join(dest_dir, filename)

    with open(filepath, 'w', encoding="UTF-8") as out:
        out.write(json.dumps(page_dict, indent=4, sort_keys=sort_keys, ensure_ascii=False))

    return True


def write_yaml_file(file_data, out_dir=None):
    """
    Write dict to a YAML file.
    :param file_data: Data to write as a string
    :param out_dir: directory where to write the output file
    :return: Always True
    """
    cur_dir = os.getcwd()
    dest_dir = out_dir

    if not dest_dir:
        dest_dir = cur_dir

    if not os.path.isdir(dest_dir):
        os.mkdir(dest_dir)

    filepath = os.path.join(dest_dir, last_dir_in_path(dest_dir) + ".yml")

    with open(filepath, 'wb') as out:
        yml = YAML()
        yml.explicit_start = True
        yml.indent(sequence=4, offset=2)
        yml.dump(file_data, out)

    return True


def last_dir_in_path(in_path: str):
    """
    Retrieve the last directory from the supplied path.
    :param in_path: File/dir path from which to retrieve the last directory
    :return: A string containing the retrieved directory name
    """
    if in_path.endswith("/"):
        in_path = in_path[:-1]

    return in_path.split("/")[-1]


def eval_bool(in_value):
    """
    Evaluate the received value as a Boolean
    :param in_value: String or int or bool to evaluate
    :return: True or False
    """

    if isinstance(in_value, (list, dict, tuple)):
        return False

    # Test int and bool
    if isinstance(in_value, bool):
        return in_value

    if isinstance(in_value, (int, float)):
        return bool(in_value)

    # string
    if not bool(in_value):
        return False

    in_value = in_value.lower()

    if in_value != 'true':
        return False

    return True


class BuildResult(Enum):
    """
    Class encapsulating possible Jenkins build result values as an enumeration.
    If initialised with a numeric value, it automatically converts the value into a
    member of the enumeration, thus interpreting the value as one of the allowed Jenkins build results.
    """
    SUCCESS = 0
    FAILURE = 1
    UNSTABLE = 2
    ABORTED = 3
    UNKNOWN = -1

    @property
    def enum_members(self):  # pylint: disable=missing-function-docstring
        return self._enum_members

    @enum_members.setter
    def enum_members(self, in_members=None):
        self._enum_members = in_members

    def __init__(self, in_members=None):
        self._enum_members = in_members

    def to_str(self, in_val=None):
        """
        Convert a numeric enum value to its string representation.

        :param in_val: The value to be converted to string
        :return: A string representation of the enum value
        """
        if not in_val:
            in_val = self.value

        for name, member in BuildResult.__members__.items():
            if in_val == member.value:
                return name

        return BuildResult.UNKNOWN.name

    def to_val(self, in_str=None):
        """
        Convert a str representation of an enum value to its numeric equivalent.
        :param in_str: A string representation of an enum value.
        :return: A numeric value corresponding to the received string.
        """
        if not in_str:
            in_str = self.name

        if in_str not in BuildResult.__members__:
            return BuildResult.UNKNOWN.value

        return next(iter(
            [member.value for name, member in BuildResult.__members__.items() if name == in_str]),
            None
        )


def contains(target, test_items):
    """
    This function checks if any elements from the received list are present in the target.
    :param test_items: A list a string, list or dictionary (in which case only the keys
    are used); we want to know if all or some of its elements are in target.
    :param target: Object (string, list, dictionary) to check for the presence of elements of test_items
    :return: True if at least one element from test_items is in target, otherwise False
    """
    if not test_items or not target:
        return False

    # Convert input to set to enable subtraction to find out about inclusion/overlapping:
    test_set = set(test_items)

    t_list = list(itertools.chain(*(list(i.keys()) if isinstance(i, dict) else i
                                    for i in target if isinstance(target, list))))

    target_set = set(list(t_list) if t_list else re.split(r'[.:-](?=[a-zA-Z\d]+)', target))

    # If the length of the set difference list is smaller than the length of the test list,
    # the test list is either wholly or partially in the test target.
    return len(list(test_set - target_set)) < len(test_items)


def list_duplicate_items(in_list, dup_key=None, dup_val=None, select=None):
    """
    List items that appear multiple times in the supplied list. If the list is a simple one, list the
    duplicate items and their indices in the list. If the list is one of dictionaries, list items that
    have the same key along with value of the specified other key.
    :param in_list: A list to check
    :param dup_key: A string indicating the key whose multiple occurrences are to be found
    :param dup_val: The key from each duplicate item whose value is to be recorded in the returned value
    :param select: The id of the key to use as a selection criterion
    :return: A list of dictionaries, each with a duplicated key as key and a list of values (corresponding to
    the key given by dup_val) if the input list is a list of dictionaries or a list of indices if the input
    list is a simple list
    """
    if not in_list or not isinstance(in_list, list):
        return []

    if isinstance(in_list[0], dict):
        # Work on items matching select, but all items if select not provided.
        work_list = [dct.get(dup_key) for dct in in_list if dct.get(select, True)]

        # multiples = list(set(['"{}"'.format(one) for one in work list if work_list.count(one) > 1]))
        multiples = list({one for one in work_list if work_list.count(one) > 1})
        out_list = [{dct.get(dup_key): dct.get(dup_val)} for dct in in_list if dct.get(dup_key) in multiples]

        return [{name: [dct.get(name) for dct in out_list if name in dct.keys()]} for name in multiples]

    work_list = in_list
    multiples = list({one for one in work_list if work_list.count(one) > 1})

    return [{list_item: [ix for ix, li in enumerate(in_list) if li == list_item]} for list_item in multiples]


if __name__ == "__main__":
    result_instance = BuildResult(1)

    print(f"{result_instance.to_str()}")
    print(f"{result_instance.to_val(result_instance.to_str())}")

    for res in BuildResult:
        print(repr(res))
