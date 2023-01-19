# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Replacements for parts of the toolz library.
"""
from __future__ import annotations

import itertools
import collections


def groupby_to_dict(keyfunc, sequence):
    """
    toolz-style groupby, returns a dictionary of { key: [group] } instead of
    iterators.
    """
    result = collections.defaultdict(list)
    for key, group in itertools.groupby(sequence, keyfunc):
        result[key].extend(group)
    return dict(result)


T = TypeVar("T")


def unique(sequence: Sequence[T]) -> Generator[T, None, None]:
    """
    toolz inspired unique, returns a generator of unique elements in the sequence
    """
    seen: set[T] = set()
    yield from (
        # seen.add always returns None so we will always return element
        seen.add(element) or element
        for element in sequence
        # only pass along novel elements
        if element not in seen
    )
