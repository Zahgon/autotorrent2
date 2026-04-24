import hashlib
import logging
import os
import re
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import click
import toml
from libtc import (
    BTFailure,
    FailedToExecuteException,
    bdecode,
    bencode,
    parse_clients_from_toml_dict,
)
from libtc.utils import get_tracker_domain

from .__version__ import __version__
from .db import Database
from .exceptions import FailedToCreateLinkException
from .indexer import Indexer
from .matcher import Matcher
from .rw_cache import ReadWriteFileCache
from .utils import (
    FailedToParseTorrentException,
    PathRewriter,
    add_status_formatter,
    create_link_path,
    humanize_bytes,
    parse_torrent,
    filter_torrents,
)

DEFAULT_CONFIG_FILE = """[autotorrent]
database_path = "./autotorrent.db"
link_type = "soft"
always_verify_hash = [ ]
paths = [ ]
same_paths = [ ]
add_limit_size = 128_000_000
add_limit_percent = 5
cache_touched_files = false
rw_file_cache_ttl = 86400
fast_resume = false
ignore_file_patterns = [ ]
ignore_directory_patterns = [ ]
scan_hardlinks = false
"""

BASE_CONFIG_FILE = """[autotorrent]
database_path = "./autotorrent.db"
link_type = "soft"
always_verify_hash = [
    "*.nfo",
    "*.sfv",
    "*.diz",
]
paths = [ ]
same_paths = [ ]
add_limit_size = 128_000_000
add_limit_percent = 5
store_path = "/mnt/store_path/{client}/{torrent_name}"
skip_store_metadata = false
cache_touched_files = false
# rw_file_cache_chown = "1000:1000"
rw_file_cache_ttl = 86400
rw_file_cache_path = "/mnt/store_path/cache"
# WARNING: setting fast_resume to true can cause errors and problems.
fast_resume = false
ignore_file_patterns = [ ]
ignore_directory_patterns = [ ]
scan_hardlinks = false

[clients]

"""

logger = logging.getLogger(__name__)


def parse_config_file(path, utf8_compat_mode=False):
    base_config = toml.loads(DEFAULT_CONFIG_FILE)
    config = toml.load(path)
    parsed_config = base_config["autotorrent"]
    parsed_config.update(config["autotorrent"])

    clients = parsed_config["clients"] = parse_clients_from_toml_dict(config)

    database_path = path.parent / Path(parsed_config["database_path"])
    parsed_config["db"] = db = Database(
        database_path,
        utf8_compat_mode=utf8_compat_mode,
    )
    parsed_config["indexer"] = indexer = Indexer(
        db,
        ignore_file_patterns=parsed_config["ignore_file_patterns"],
        ignore_directory_patterns=parsed_config["ignore_directory_patterns"],
        include_inodes=parsed_config["scan_hardlinks"],
    )
    parsed_config["rewriter"] = rewriter = PathRewriter(parsed_config["same_paths"])
    parsed_config["matcher"] = matcher = Matcher(
        rewriter, db, include_inodes=parsed_config["scan_hardlinks"]
    )

    rw_file_cache_chown = parsed_config.get("rw_file_cache_chown")

    if parsed_config.get("cache_touched_files"):
        parsed_config["rw_cache"] = rw_cache = ReadWriteFileCache(
            parsed_config["rw_file_cache_path"],
            parsed_config["rw_file_cache_ttl"],
            rw_file_cache_chown,
        )
    else:
        parsed_config["rw_cache"] = None

    parsed_config["fast_resume"] = parsed_config["fast_resume"]
    parsed_config["always_verify_hash"] = parsed_config["always_verify_hash"]
    parsed_config["paths"] = parsed_config["paths"]

    return parsed_config


def validate_config_path(ctx, param, value):
    pass


@click.group()
@click.option(
    "-c",
    "--config",
    help="Path to config file",
    callback=validate_config_path,
    type=click.Path(exists=True, dir_okay=False),
)
@click.option("-v", "--verbose", help="Verbose logging", flag_value=True, default=False)
@click.option(
    "-u",
    "--utf8-compat-mode",
    help="Try work around utf-8 errors, not recommended",
    flag_value=True,
    default=False,
)
@click.version_option(__version__)
@click.pass_context
def cli(ctx, config, verbose, utf8_compat_mode):
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG, format="%(levelname)s:%(name)s:%(lineno)d:%(message)s"
        )
    # logger.debug(f"Using config file path: {config}")
    ctx.ensure_object(dict)
    ctx.obj.update(parse_config_file(config, utf8_compat_mode=utf8_compat_mode))


@cli.command(help="See what is seeded for a given path.")
@click.option(
    "-s",
    "--summary",
    help="End the listing with a summary",
    flag_value=True,
    default=False,
)
@click.option("-d", "--depth", type=int, default=0)
@click.option(
    "-i",
    "--include-indirect-seeded",
    help="Include indirectly seeded files, i.e. hardlinked files. Deleting these files will not make the client stop seeding.",
    flag_value=True,
    default=False,
)
@click.argument("path", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def ls(ctx, summary, depth, include_indirect_seeded, path):
    pass


@cli.command(help="Find unseeded paths.")
@click.option(
    "-e",
    "--escape-paths",
    help="Escape the output paths",
    flag_value=True,
    default=False,
)
@click.option(
    "-i",
    "--include-indirect-seeded",
    help="Include indirectly seeded files, i.e. hardlinked files. Deleting these files will not make the client stop seeding.",
    flag_value=True,
    default=False,
)
@click.argument("path", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def find_unseeded(ctx, escape_paths, include_indirect_seeded, path):
    pass


@cli.command(
    help="Find torrents not in current paths. This is useful for e.g. the torrent are seeded but not sorted into folders (with links)."
)
@click.option(
    "-s",
    "--summary",
    help="End the listing with a summary",
    flag_value=True,
    default=False,
)
@click.option(
    "-i",
    "--include-indirect-seeded",
    help="Include indirectly seeded files, i.e. hardlinked files. Deleting these files will not make the client stop seeding.",
    flag_value=True,
    default=False,
)
@click.option(
    "--remove-from-client",
    help="Remove the unmoved torrents from clients, i.e. the ones NOT found in path.",
    flag_value=True,
    default=False,
)
@click.option("-l", "--client", help="Check a specific client", type=str)
@click.option("-q", "--query", help="SQL query to match against torrents", type=str)
@click.argument("path", nargs=-1, type=click.Path(exists=True))
@click.pass_context
def find_unmoved(
    ctx, summary, include_indirect_seeded, remove_from_client, client, query, path
):
    pass


@cli.command(help="Checks if the config file exists and is loadable.")
@click.pass_context
def check_config(ctx):
    pass


@cli.command(
    help="Remove all torrents seeding data from a path. Does not delete the actual data."
)
@click.option("-l", "--client", help="Remove from a specific client", type=str)
@click.option("-q", "--query", help="SQL query to match against torrents", type=str)
@click.argument("path", nargs=-1, type=click.Path(exists=True), required=True)
@click.pass_context
def rm(ctx, client, query, path):
    pass


def validate_store_path_variable(ctx, param, value):
    pass


@cli.command(help="Add new torrents to a client.")
@click.argument("client", type=str)
@click.option(
    "-e",
    "--exact",
    help='Exact matching mode. Can also be considered a "reseed" mode. Disables all other modes.',
    flag_value=True,
    default=False,
)
@click.option(
    "-s",
    "--hash-probe",
    help="Probe matched files for full pieces to ensure the data matches.",
    flag_value=True,
    default=False,
)
@click.option(
    "-a",
    "--hash-size",
    help="Hash size matching mode, checks for files with same size but different filenames.",
    flag_value=True,
    default=False,
)
@click.option(
    "--print-summary",
    help="Print a summary of all actions when done.",
    flag_value=True,
    default=False,
)
@click.option("--chown", help="Chown the data folder when creating links.", type=str)
@click.option(
    "--dry-run",
    help="Do not actually create links and add the torrents, just check what would happen.",
    flag_value=True,
    default=False,
)
@click.option(
    "--move-torrent-on-add",
    help="Move the torrent to this path after it has been added successfully to the client.",
    type=click.Path(),
)
@click.option(
    "--stopped",
    help="Add the torrent in stopped state.",
    flag_value=True,
    default=False,
)
@click.option(
    "-t",
    "--store-path-template",
    help="Pass a custom template instead of using the one defined in the config file.",
)
@click.option(
    "-v",
    "--store-path-variable",
    help="Variable used for store path using a key=value syntax.",
    callback=validate_store_path_variable,
    multiple=True,
)
@click.argument("torrent", nargs=-1, type=click.Path(exists=True, dir_okay=False))
@click.pass_context  # TODO: allow feedback while running
def add(
    ctx,
    client,
    exact,
    hash_probe,
    hash_size,
    torrent,
    print_summary,
    chown,
    dry_run,
    move_torrent_on_add,
    stopped,
    store_path_template,
    store_path_variable,
):
    pass


@cli.command(help="Cleanup RW cache for expired items.")
@click.pass_context
def cleanup_cache(ctx):
    pass


@cli.command(help="Scan your local paths files.")
@click.option(
    "-p",
    "--path",
    help="Partial scan a given path, does not remove removed files from the database.",
    type=click.Path(exists=True),
)
@click.pass_context
def scan(ctx, path):
    pass


@cli.command(help="Scan your clients for files.")
@click.option("-l", "--client", help="Scan a specific client", type=str)
@click.option(
    "-f",
    "--full",
    help="Clear old data and do a full scan",
    flag_value=True,
    default=False,
)
@click.option(
    "-a",
    "--fast",
    help="Run a fast scan, does not detect moved torrents. Overwritten by full",
    flag_value=True,
    default=False,
)
@click.pass_context
def scan_clients(ctx, client, full, fast):
    pass


@cli.command(help="Test your connection to your clients.")
@click.option("-l", "--client", help="Check a specific client", type=str)
@click.pass_context
def test_connection(ctx, client):
    pass


# @cli.command(help="Remove unseeded folders from store paths")
# @click.argument("path", nargs=-1, type=click.Path(exists=True, file_okay=False, dir_okay=True))
# @click.option(
#     "-s",
#     "--skip-scan-clients",
#     help="Do not scan clients for seeded paths before finding unseeded paths.",
#     flag_value=True,
#     default=False,
# )
# @click.pass_context
# def cleanup_store_path(ctx, path, skip_scan_clients):
#     pass

# @cli.command(help="Reseed store paths")
# @click.argument("client", type=str)
# @click.argument("path", nargs=-1, type=click.Path(exists=True, file_okay=False, dir_okay=True))
# @click.option(
#     "-s",
#     "--skip-scan-clients",
#     help="Do not scan clients for seeded paths before finding unseeded paths.",
#     flag_value=True,
#     default=False,
# )
# @click.pass_context
# def reseed_store_path(ctx, path):
#     pass

# @cli.command(help="Build a bundle from torrents that can be distributed to find torrents to seed locally.")
# @click.pass_context
# def build_cross_seed_bundle(ctx):
#     pass


# @cli.command(help="Match a cross seed bundle with your scanned data.")
# @click.pass_context
# def compare_cross_seed_bundle(ctx):
#     pass

if __name__ == "__main__":
    cli()
