import logging
import os
import sqlite3
from collections import namedtuple
from pathlib import Path

from .utils import decode_str, normalize_filename

logger = logging.getLogger(__name__)

SeededFile = namedtuple(
    "SeededFile", ["name", "path", "download_path", "infohash", "client", "size"]
)

InsertTorrentFile = namedtuple(
    "InsertTorrentFile",
    ["infohash", "name", "download_path", "paths"],
)


class SearchedFile(
    namedtuple(
        "SearchedFile", ["name", "path", "size", "normalized_name", "unsplitable_root"]
    )
):
    def to_full_path(self):
        pass


class Database:
    _insert_counter = 0

    def __init__(self, path, utf8_compat_mode=False):
        self.db = sqlite3.connect(path)
        self.utf8_compat_mode = utf8_compat_mode
        self.create_tables()

    def create_tables(self):
        pass

    def commit(self):
        self.db.commit()

    def insert_file_paths(self, iterable):
        """Take an interable that generates a tuple with the three
        fields defined in `create_insert` and normalize them for
        insertion into the DB"""
        pass

    def truncate_files(self):
        pass

    def search_file(
        self,
        filename=None,
        size=None,
        path=None,
        normalized_filename=False,
        path_postfix=None,
        is_unsplitable=None,
        unsplitable_root=None,
    ):
        pass

    def get_torrent_file_info(self, client, infohash):
        pass

    def insert_torrent_files_paths(self, client, insert_torrent_files):
        pass

    def truncate_torrent_files(self, client=None):
        pass

    def remove_torrent_files(self, client, infohashes):
        pass

    def remove_non_existing_infohashes(self, client, infohashes):
        pass

    def get_seeded_paths(self, paths, inodes):
        pass

    def get_seeded_infohashes(self, client):
        pass
