#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
###############################################################################
#
# Copyright (C) 2022 Adam Bukolt.
# All Rights Reserved.
#
###############################################################################
import itertools
import json
import os
import re
import time
from enum import Enum


SEC_IN_DAY = 24 * 3600


def log_it(level='info', src_name=None, text=None):
    import logging

    logging.basicConfig(level=logging.DEBUG)
    logger_name = src_name if src_name else __name__
    log_writer = logging.getLogger(logger_name)

    if level == 'info':
        log_writer.info(text)
    elif level == 'error':
        log_writer.error(text)
    elif level == 'warning':
        log_writer.warning(text)
    else:
        log_writer.debug(text)


def timed_function(func):
    def wrapped(*args, **kwargs):
        start = time.perf_counter_ns()
        result = func(*args, **kwargs)
        log_it("info", __name__, f'running_time = {int((time.perf_counter_ns() - start) / 1000000)} ms')
        return result
    return wrapped


def run_scandir(in_dir, ext):    # dir: str, ext: list
    """
    Find all the subdirectories and files in them. If ext is provided, list only files with matching extension
    :param in_dir: Input directory or which subidrectories are to be listed
    :param ext: File extension to match
    :return: A list of subdirectories and a list of files in them
    """
    sub_dirs = list()
    fn_files = list()

    for f in list(os.scandir(in_dir)):
        if f.is_dir():
            sub_dirs.append(f.path)
        if f.is_file():
            fn_ext_lower = os.path.splitext(f.name)[1].lower()
            if ext and fn_ext_lower and fn_ext_lower in ext:
                fn_files.append(f.path)
            else:
                fn_files.append(f.path)

    for directory in list(sub_dirs):
        sf, f = run_scandir(directory, ext)
        sub_dirs.extend(sf)
        fn_files.extend(f)

    sub_dirs.append(in_dir)

    return sub_dirs, fn_files


def write_json_file(page_dict, filename, sort_keys=True):
    cur_dir = os.getcwd()
    dest_dir = cur_dir + '/../out/'

    if not os.path.isdir(dest_dir):
        os.mkdir(dest_dir)

    filepath = dest_dir + filename

    with open(filepath, 'w') as out:
        out.write(json.dumps(page_dict, indent=4, sort_keys=sort_keys, ensure_ascii=False))

    return True


def write_file(filename, file_data, dest_dir=None):
    cur_dir = os.getcwd()

    if not dest_dir:
        dest_dir = cur_dir + '/../out/'

    if not os.path.isdir(dest_dir):
        os.mkdir(dest_dir)

    filepath = dest_dir + filename

    if isinstance(file_data, dict):
        with open(filepath, 'w') as out:
            out.write(json.dumps(file_data, indent=4, sort_keys=True, ensure_ascii=False))
    elif isinstance(file_data, str):
        with open(filepath, 'w') as out:
            out.write(file_data)
    else:
        with open(filepath, 'wb') as out:
            out.write(file_data)

    return True


def read_file(filename, dest_dir=None):
    cur_dir = os.getcwd()

    if not dest_dir:
        dest_dir = cur_dir + '/../out/'

    filepath = dest_dir + filename

    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Missing: {filepath}")
        return ''


def read_json_file(filename, dest_dir=None):
    cur_dir = os.getcwd()

    if not dest_dir:
        dest_dir = cur_dir + '/../out/'

    filepath = dest_dir + filename

    with open(filepath, 'r') as f:
        return json.load(f)


def eval_bool_str(in_str):
    # Test int and bool
    if isinstance(in_str, bool):
        return in_str

    if isinstance(in_str, int):
        return bool(in_str)

    # string
    if not bool(in_str):
        return False

    in_str = in_str.lower()

    if in_str != 'true':
        return False

    return True


def eval_none_value(in_str):
    if not in_str:
        return None

    # int
    if isinstance(in_str, int):
        return str(in_str) if int(in_str) != 0 else None

    # Boolean
    if eval_bool_str(in_str):
        return str(in_str)

    # string
    if in_str.lower() in ['null', 'none']:
        return None

    return in_str


class EnumResult(Enum):
    """
    Class encapsulating Jenkins build results as an enumeration.
    """
    SUCCESS = 0
    FAILURE = 1
    UNSTABLE = 2
    ABORTED = 3
    UNKNOWN = -1

    @property
    def rmembers(self):
        return self._rmembers

    @rmembers.setter
    def rmembers(self, in_members=None):
        self._rmembers = in_members

    def __init__(self, in_members=None):
        self._rmembers = in_members

    @staticmethod
    def to_str(in_val):
        """
        Convert a numeric enum value to its string representation.

        :param in_val: The value to be converted to string.
        :return: A string representation of the enum value.
        """
        for name, member in EnumResult.__members__.items():
            if in_val == member.value:
                return name

        return EnumResult.UNKNOWN.name

    @staticmethod
    def to_val(in_str):
        """
        Convert a str representation of an enum value to its numeric equivalent.
        :param in_str: A string representation of an enum value.
        :return: A numeric value corresponding to the received string.
        """
        if in_str not in EnumResult.__members__:
            return EnumResult.UNKNOWN.value

        return [member.value for name, member in EnumResult.__members__.items() if name == in_str][0]


def contains(target, test_items):
    """
    This function checks if any elements from the received list are present in the target.
    :param test_items: A list a string, list or dictionary (in which case only the keys are used); we want to know if
    all or some of its elements are in target.
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


def purge_duplicate_dict(in_list):
    if not isinstance(in_list[0], dict):
        return in_list

    w_list = list(set([json.dumps(dt) for dt in in_list]))

    return [json.loads(sd) for sd in w_list]


def list_duplicate_items(in_list, dup_key=None, dup_val=None, select=None):
    """
    List items that appear multiple times in the supplied list. If the list is a simple one, list the duplicate items
    and their indices in the list. If the list is one of dictionaries, list items that have the same key along with
    value of the specified other key.
    :param in_list: A list to check
    :param dup_key: A string indicating the key whose multiple occurrences are to be found
    :param dup_val: The key from each duplicate item whose value is to be recorded in the returned value
    :param select: The id of the key to use as a selection criterion
    :return: A list of dictionaries, each with a duplicated key as key and a list of values (corresponding to the key
    given by dup_val) if the input list is a list of dictionaries or a list of indices if the input list is a simple
    list
    """
    if not in_list or not isinstance(in_list, list):
        return []

    if isinstance(in_list[0], dict):
        # Work on items matching select, but all items if select not provided.
        work_list = [dct.get(dup_key) for dct in in_list if dct.get(select, True)]

        # multiples = list(set(['"{}"'.format(one) for one in work list if work_list.count(one) > 1]))
        multiples = list(set([one for one in work_list if work_list.count(one) > 1]))
        out_list = [{dct.get(dup_key): dct.get(dup_val)} for dct in in_list if dct.get(dup_key) in multiples]

        return [{name: [dct.get(name) for dct in out_list if name in dct.keys()]} for name in multiples]

    work_list = in_list
    multiples = list(set([one for one in work_list if work_list.count(one) > 1]))

    return [{list_item: [ix for ix, li in enumerate(in_list) if li == list_item]} for list_item in multiples]


class EasyDict(dict):
    """
    This version of EasyDict is a Python 3.6+ update of https://github.com/makinacorpus/easydict.
    """
    def __init__(self, d=None, **kwargs):
        super().__init__(self)
        self.update(**d or {}, **kwargs)

    def __setattr__(self, name, value):
        if isinstance(value, (list, tuple)):
            value = [self.__class__(x) if isinstance(x, dict) else x for x in value]
        elif isinstance(value, dict) and not isinstance(value, self.__class__):
            value = self.__class__(value)

        super(EasyDict, self).__setattr__(name, value)
        super(EasyDict, self).__setitem__(name, value)

    __setitem__ = __setattr__

    def update(self, e=None, **f):
        e = e or dict()
        e.update(f)

        for k, v in e.items():
            setattr(self, k, v)

    def pop(self, k, d=None):
        delattr(self, k)

        return super().pop(k, d)


if __name__ == "__main__":
    ed = EasyDict({"first": "I", "name": "me", "dob": "not yesterday"})
    # print(ed.fourth)
    # val = ed.fourth
    # print(val)
    ed.fourth = '4th'
    val = ed.fourth
    print(ed.dob)  # NOQA

    ss, fs = run_scandir("/home/adam/Documents", "pdf")

    print(repr(ss))
    print(repr(fs))
    # ed.first = "Zebediah"
    # ed.name = "Croc"
    # ed.dob = "11_5_1838"
    #
    # ed.address = dict()
    # ed.address.street = dict()
    # ed.address.street.number = "19"
    # ed.address.street.name = "Bochumer"
    # ed.address.town = "Berlin"
    # ed.address.postcode = "10551"
    # print(repr(ed))
    #
    # ed.address.street.pop("number", "one")
    # print(repr(ed))
