import errno
import logging
import os
from collections import namedtuple
from math import ceil
from pathlib import Path

from .utils import (
    can_potentially_miss_in_unsplitable,
    get_root_of_unsplitable,
    is_unsplitable,
    parse_torrent,
)

MatchedFile = namedtuple("MatchedFile", ["torrent_file", "searched_files"])
MatchResult = namedtuple("MatchResult", ["root_path", "matched_files", "size"])
MappedFile = namedtuple("MappedFile", ["size", "clients", "indirect_clients"])
MapResult = namedtuple(
    "MapResult", ["total_size", "seeded_size", "indirect_seeded_size", "files"]
)
DynamicMatchResult = namedtuple(
    "DynamicMatchResult", ["success", "missing_size", "matched_files", "touched_files"]
)

logger = logging.getLogger(__name__)

EXACT_MATCH_FACTOR = 0.05


def is_relative_to(path, *other):
    """Return True if the path is relative to another path or False."""
    pass


class Matcher:
    def __init__(self, rewriter, db, include_inodes=False):
        self.rewriter = rewriter
        self.db = db
        self.include_inodes = include_inodes

    def _match_filelist_exact(
        self,
        filelist,
        skip_prefix_path=None,
        match_normalized_filename=False,
    ):
        pass

    def _match_filelist_unsplitable(
        self,
        filelist,
        skip_prefix_path=None,
        match_normalized_filename=False,
    ):
        pass

    def _match_best_file(
        self,
        torrent,
        torrent_file,
        searched_files,
        hash_probe=False,
        match_hash_size=False,
    ):
        pass

    def _select_best_candidate(
        self, torrent, candidates, hash_probe=False, match_hash_size=False
    ):
        pass

    def match_files_exact(self, torrent):
        pass

    def match_files_dynamic(
        self,
        torrent,
        match_hash_size=False,
        add_limit_size=0,
        add_limit_percent=0,
        hash_probe=False,
    ):
        pass

    def map_path_to_clients(self, path):
        """
        Map a path and all its files to clients.
        """
        pass
