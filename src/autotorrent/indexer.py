import logging
import os
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from queue import Empty, SimpleQueue

from .db import InsertTorrentFile
from .utils import get_root_of_unsplitable, is_unsplitable

logger = logging.getLogger(__name__)

INSERT_QUEUE_MAX_SIZE = 1000

SCAN_PATH_QUEUE_TIMEOUT_SECONDS = 10


class PathTrieNode:
    __slots__ = ("children", "is_file", "is_unsplitable", "size")

    def __init__(self):
        self.children = {}
        self.is_file = False  # In a typical string-based trie, this would mark the end of the string
        self.is_unsplitable = False
        self.size = None


class PathTrie:
    def __init__(self):
        self.root = PathTrieNode()

    def insert_path(self, path, size):
        pass

    def mark_unsplitable(self, path):
        pass

    def walk(self, func):
        """Recursively walk the entire tree, applying `func` to all end
        nodes (which will always be a files)"""
        return self._walk_node(self.root, func, "", None)

    def _walk_node(self, node, func, current_path, unsplitable_root):
        """Provides the recursivity needed to actually walk the tree"""
        directories = []
        files = []
        for name, child in node.children.items():
            if child.is_file:
                files.append((name, child))
            else:
                directories.append((name, child))
        # Descend directory-first to ensure unsplittable roots are applied properly
        for name, child in directories:
            unsplitable_root_for_children = unsplitable_root
            new_path = Path(current_path, name)
            if child.is_unsplitable and unsplitable_root is None:
                unsplitable_root_for_children = new_path
            yield from self._walk_node(
                child, func, new_path, unsplitable_root_for_children
            )
        for name, child in files:
            yield func(child, Path(current_path, name), unsplitable_root)


class IndexAction(Enum):
    ADD = 1
    MARK_UNSPLITABLE = 2
    FINISHED = 3


class Indexer:
    def __init__(
        self,
        db,
        ignore_file_patterns=None,
        ignore_directory_patterns=None,
        include_inodes=False,
    ):
        self.db = db
        self.ignore_file_patterns = ignore_file_patterns or []
        self.ignore_directory_patterns = ignore_directory_patterns or []
        self.include_inodes = include_inodes

    def scan_paths(self, paths, full_scan=True):
        pass

    def _match_ignore_pattern(self, ignore_patterns, p, ignore_case=False):
        pass

    def _scan_path_thread(self, path, queue, root_thread=False):
        pass

    def scan_clients(self, clients, full_scan=False, fast_scan=False):
        pass

    def _scan_client(self, client_name, client, fast_scan):
        pass
