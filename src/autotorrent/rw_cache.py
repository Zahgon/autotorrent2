import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

from .utils import chown, create_link

logger = logging.getLogger(__name__)

RW_CACHE_DATA_PATH = "data"
CW_CACHE_CONF_NAME = "autotorrent.json"


class ReadWriteFileCache:
    def __init__(self, path, ttl, chown_str=None):
        self.path = Path(path)
        self.ttl = ttl
        self.chown_str = chown_str

    def cleanup_cache(self):
        pass

    def cache_file(self, path, target_path, link_type):
        full_folder_name = "__".join(path.parts[1:])
        folder_name = f"{full_folder_name[:25]}__{full_folder_name[-50:]}__{hashlib.sha1(str(path).encode()).hexdigest()}"
        folder_path = self.path / folder_name
        folder_data_path = folder_path / RW_CACHE_DATA_PATH
        folder_data_file = folder_data_path / path.name
        conf_path = folder_path / CW_CACHE_CONF_NAME
        if not folder_path.exists():
            logger.info(
                f"Seems like folder {folder_path!s} does not exist, copying file from {path!s}"
            )
            folder_path.mkdir()
            folder_data_path.mkdir()
            shutil.copyfile(path, folder_data_file)
            if self.chown_str is not None:
                chown(self.chown_str, folder_data_file)
            conf_path.write_text(
                json.dumps(
                    {
                        "source_path": str(path),
                        "target_paths": [],
                    }
                )
            )

        folder_path.touch()
        conf = json.loads(conf_path.read_text())
        conf["target_paths"].append(
            {
                "path": str(target_path),
                "link_type": link_type,
            }
        )
        conf_path.write_text(json.dumps(conf))
        return folder_data_file
