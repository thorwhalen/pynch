__author__ = 'thorwhalen'

import operator
from functools import reduce  # forward compatibility for Python 3

from numpy import isnan

try:
    from mongoquery import Query
except ImportError:
    import warnings
    warnings.warn("Failed import: from mongoquery import Query: dict_filt_from_mg_filt unusable")

from mungepy.utils import ascertain_list


def dict_filt_from_mg_filt(mg_filt):
    """
    The final intent is to do what a mongo query does on a collection, but with a dict iterator instead.
    dict_filt_from_mg_filt creates, based on a mg_filt (that uses the same language as mongo, a filter.
    A filter is a function that returns True iff mg_filt condition is satistfied.
    Basically, if mgc is a mongo collection and dict_iter is a dict iterator containing the same dicts,
    the following should be equivalent:
        mgc.find(mg_filt) and itertools.ifilter(dict_filt_from_mg_filt(mg_filt), dict_iter)
    In fact, you can test this directly with a (small) mongo collection by doing:
        assert list(mgc.find(mg_filt)) == filter(dict_filt_from_mg_filt(mg_filt), mgc.find())
    :param mg_filt:
    :return: a filter (a function returning True or False)

    >>> ####### A complicated one
    >>> mg_filt = {
    ...    'a': {'$in': [3, 4, 5]},
    ...    'x': {'$gte': 10, '$lt': 20},
    ...    'foo.bar': 'bit',
    ...    'this': {'is': 'that'},
    ... }
    >>> filt = dict_filt_from_mg_filt(mg_filt)
    >>> filt({'a': 3, 'x': 15, 'foo': {'bar': 'bit'}, 'this': {'is': 'that'}, 'and_something': 'else'})
    True
    >>> filt({'a': 1, 'x': 15, 'foo': {'bar': 'bit'}, 'this': {'is': 'that'}, 'and_something': 'else'})
    False
    >>> filt({'a': 3, 'x': 20, 'foo': {'bar': 'bit'}, 'this': {'is': 'that'}, 'and_something': 'else'})
    False
    >>> filt({'a': 3, 'x': 15, 'foo.bar': 'bit', 'this': {'is': 'that'}, 'and_something': 'else'})
    False
    >>> ####### testing equality
    >>> filt = dict_filt_from_mg_filt(mg_filt={'foo': 'bar'})
    >>> # True when equal
    >>> filt({'foo': 'bar'})
    True
    >>> # false when not equal
    >>> filt({'foo': 'bear'})
    False
    >>> # false if key not present
    >>> filt({'fool': 'bar'})
    False
    >>> # can also have equality of dicts
    >>> filt = dict_filt_from_mg_filt(mg_filt={'foo': {'bar': 'bit'}})
    >>> filt({'foo': {'bar': 'bit'}})
    True
    >>> ####### A single >= comparison
    >>> mg_filt = {'a': {'$gte': 10}}
    >>> filt = dict_filt_from_mg_filt(mg_filt)
    >>> filt({'a': 9})
    False
    >>> filt({'a': 10})
    True
    >>> filt({'a': 11})
    True
    >>> ####### A single > comparison
    >>> filt = dict_filt_from_mg_filt({'a': {'$gt': 10}})
    >>> filt({'a': 9})
    False
    >>> filt({'a': 10})
    False
    >>> filt({'a': 11})
    True
    >>> ####### A range query
    >>> filt = dict_filt_from_mg_filt({'a': {'$gte': 10, '$lt': 20}})
    >>> map(filt, [{'a': x} for x in [9, 10, 15, 20, 21]])
    [False, True, True, False, False]
    """
    return Query(mg_filt).match


def iter_key_path_items(d, key_path_prefix=None):
    """
    iterate through items of dict recursively, yielding (key_path, val) pairs for all nested values that are not dicts.
    That is, if a value is a dict, it won't generate a yield, but rather, will be iterated through recursively.
    :param d: input dict
    :param key_path_so_far: string to be prepended to all key paths (for use in recursion, not meant for direct use)
    :return: a (key_path, val) iterator
    >>> input_dict = {
    ...     'a': {
    ...         'a': 'a.a',
    ...         'b': 'a.b',
    ...         'c': {
    ...             'a': 'a.c.a'
    ...         }
    ...     },
    ...     'b': 'b',
    ...     'c': 3
    ... }
    >>> list(iter_key_path_items(input_dict))
    [('a.a', 'a.a'), ('a.c.a', 'a.c.a'), ('a.b', 'a.b'), ('c', 3), ('b', 'b')]
    """
    if key_path_prefix is None:
        for k, v in d.items():
            if not isinstance(v, dict):
                yield k, v
            else:
                for kk, vv in iter_key_path_items(v, k):
                    yield kk, vv
    else:
        for k, v in d.items():
            if not isinstance(v, dict):
                yield key_path_prefix + '.' + k, v
            else:
                for kk, vv in iter_key_path_items(v, k):
                    yield key_path_prefix + '.' + kk, vv


def extract_key_paths(d, key_paths, field_naming='full', use_default=False, default_val=None):
    """
    getting with a key list or "."-separated string
    :param d: dict
    :param key_path: list or "."-separated string of keys
    :param field_naming: 'full' (default) will use key_path strings as is, leaf will only use the last dot item
        (i.e. this.is.a.key.path will result in "path" being used)
    :return:
    """
    dd = dict()
    if isinstance(key_paths, dict):
        key_paths = [k for k, v in key_paths.items() if v]

    for key_path in key_paths:

        if isinstance(key_path, str):
            field = key_path
            key_path = key_path.split('.')
        else:
            field = '.'.join(key_path)

        if field_naming == 'leaf':
            field = key_path[-1]
        else:
            field = field

        try:
            dd.update({field: reduce(operator.getitem, key_path, d)})
        except (TypeError, KeyError):
            if use_default:
                dd.update({field: default_val})

    return dd


def key_paths(d):
    key_path_list = list()
    for k, v in d.items():
        if not isinstance(v, dict):
            key_path_list.append(k)
        else:
            key_path_list.extend([k + '.' + x for x in key_paths(v)])
    return key_path_list


def get_value_in_key_path(d, key_path, default_val=None):
    """
    getting with a key list or "."-separated string
    :param d: dict
    :param key_path: list or "."-separated string of keys
    :return:
    """
    if isinstance(key_path, str):
        key_path = key_path.split('.')
    try:
        return reduce(operator.getitem, key_path, d)
    except (TypeError, KeyError):
        return default_val


def set_value_in_key_path(d, key_path, val):
    """
    setting with a key list or "."-separated string
    :param d: dict
    :param key_path: list or "."-separated string of keys
    :param val: value to assign
    :return:
    """
    if isinstance(key_path, str):
        key_path = key_path.split('.')
    get_value_in_key_path(d, key_path[:-1])[key_path[-1]] = val


def set_value_in_nested_key_path(d, key_path, val):
    """

    :param d:
    :param key_path:
    :param val:
    :return:
    >>> input_dict = {
    ...   "a": {
    ...     "c": "val of a.c",
    ...     "b": 1,
    ...   },
    ...   "10": 10,
    ...   "b": {
    ...     "B": {
    ...       "AA": 3
    ...     }
    ...   }
    ... }
    >>>
    >>> set_value_in_nested_key_path(input_dict, 'new.key.path', 7)
    >>> input_dict
    {'a': {'c': 'val of a.c', 'b': 1}, '10': 10, 'b': {'B': {'AA': 3}}, 'new': {'key': {'path': 7}}}
    >>> set_value_in_nested_key_path(input_dict, 'new.key.old.path', 8)
    >>> input_dict
    {'a': {'c': 'val of a.c', 'b': 1}, '10': 10, 'b': {'B': {'AA': 3}}, 'new': {'key': {'path': 7, 'old': {'path': 8}}}}
    >>> set_value_in_nested_key_path(input_dict, 'new.key', 'new val')
    >>> input_dict
    {'a': {'c': 'val of a.c', 'b': 1}, '10': 10, 'b': {'B': {'AA': 3}}, 'new': {'key': 'new val'}}
    """
    from dol import path_set
    return path_set(d, key_path, val)



def mk_fixed_coordinates_value_getter(get_key_list):
    return \
        lambda the_dict: \
            reduce(lambda x, y: x.get(y, {}), get_key_list, the_dict) or None


def key_if_exists_else_return_none(d, key):
    DeprecationWarning('You should really call this one liner directly!!')
    return d.get(key, None)


def head(d, num_of_elements=5, start_at=0):
    """
    get the "first" few (num) elements of a dict
    """
    return {k: d[k] for k in list(d.keys())[start_at:min(len(d), start_at + num_of_elements)]}


def tail(d, num_of_elements=5):
    """
    get the "first" few (num) elements of a dict
    """
    return {k: d[k] for k in list(d.keys())[-min(len(d), num_of_elements):]}


def left_union(d, defaults):
    """
    :param d: dict
    :param defaults: dict
    :return: dict d, enhanced with key:value pairs of defaults dict whose keys weren't found in d
    """
    return dict(defaults, **d)


def get_subset_of_defaults(d, defaults, subset_of_default_keys):
    """
    :param d: dict
    :param defaults: dict
    :param subset_of_default_keys: list of keys
    :return: adds key:value pairs to d if key is not in d, but is in defaults and subset_of_default_keys
    """
    return left_union(d, get_subdict(defaults, subset_of_default_keys))


def get_subdict(d, list_of_keys):
    """
    :param d: dict
    :param subset_of_keys: list of keys
    :return: the subset of key:value pairs of d where key is in list_of_keys
    """
    return dict([(i, d[i]) for i in list_of_keys if i in d])


def get_subdict_and_remainder(d, list_of_keys):
    """
    :param d: dict
    :param subset_of_keys: list of keys
    :return: the subset of key:value pairs of d where key is in list_of_keys
    """
    keys_in = set(d.keys()).intersection(list_of_keys)
    keys_not_in = set(d.keys()).difference(list_of_keys)
    return (dict([(i, d[i]) for i in keys_in]), dict([(i, d[i]) for i in keys_not_in]))


def all_but(d, exclude_keys):
    return get_subdict(d, set(d.keys()).difference(ascertain_list(exclude_keys)))


def all_non_null(d):
    return {k: v for k, v in d.items() if v is not None and not isnan(v)}
