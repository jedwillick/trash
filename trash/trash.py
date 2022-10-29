import errno
import os
import shutil
import sys
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Union


def ask_yes_no(msg):
    return input(f"{msg} (y/N): ").lower() == "y"


@dataclass
class Trash:
    trash: Union[Path, None] = None
    verbose: bool = False
    force: bool = False
    recursive: bool = False
    interactive: bool = False

    def __post_init__(self):
        if self.trash is None:
            xdg = os.getenv("XDG_DATA_HOME", "~/.local/share")
            self.trash = Path(f"{xdg}/Trash").expanduser()

        self._FILES = (self.trash / "files").expanduser()
        self._INFO = (self.trash / "info").expanduser()
        self._FILES.mkdir(parents=True, exist_ok=True)
        self._INFO.mkdir(parents=True, exist_ok=True)
        self._COMMAND_MAP = {
            "remove": self.remove_trash,
            "list": self.list_trash,
            "empty": self.empty_trash,
            "restore": self.restore_trash,
            "cat": self.cat_trash,
        }

    def bad_command(self, *_):
        return self.perror("Unknown command")

    def run(self, cmd, files):
        return self._COMMAND_MAP.get(cmd, self.bad_command)(files)

    def relative_files(self, files, fillEmpty=False):
        if not files:
            return list(self._FILES.iterdir()) if fillEmpty else files

        # Expand globs relative to self._FILES directory
        rel = []
        for glob in files:
            globs = list(self._FILES.glob(str(glob)))
            if not globs:
                rel.append(self._FILES / glob)
                continue
            for f in globs:
                rel.append(self._FILES / f)

        return rel

    def list_trash(self, files):
        files = self.relative_files(files, fillEmpty=True)
        if not files:
            return
        files.sort()
        err = 0
        for file in files:
            if not file.exists():
                err += self.perror(f"{file} does not exist")
                continue

            new = file.name
            meta = self.read_info(file)
            if file.is_dir():
                meta["Path"] += "/"
                new += "/"

            print(
                f"{meta['DeletionDate'].replace('T', ' '):<19} {meta['Path']} ==> {new}"
            )
        return err

    def read_info(self, file):
        info = self._INFO / f"{file.name}.trashinfo"
        config = ConfigParser()
        config.read(info)
        keys = ["Path", "DeletionDate"]
        if "Trash Info" not in config:
            return {key: "missing" for key in keys}
        return {key: config["Trash Info"].get(key, "missing") for key in keys}

    def empty_trash(self, files):
        if not files and not self.force:
            if not ask_yes_no("Are you sure you want to empty all trash"):
                return 0
            files = self.relative_files(files, fillEmpty=True)

        err = 0
        for file in files:
            if self.interactive and not ask_yes_no(f"Permanently delete {file}"):
                continue
            try:
                if file.is_dir() and self.recursive:
                    shutil.rmtree(file)
                else:
                    file.unlink()
            except OSError as e:
                err += self.perror(file, e)
                continue

            self.vprint(f"Removed {file}")
            (self._INFO / f"{file.name}.trashinfo").unlink(missing_ok=True)
        return err

    def remove_trash(self, files):
        if not files:
            return self.perror("No files to remove")

        err = 0
        for file in files:
            if self.interactive and not ask_yes_no(f"Trash {file}"):
                continue
            trash, info = self.ensure_unqiue(file.name, file.suffixes)
            is_dir = file.is_dir()
            try:
                if is_dir and not self.recursive:
                    raise IsADirectoryError(errno.EISDIR, "Is a directory")
                shutil.move(file, trash)
            except OSError as e:
                err += self.perror(file, e)
                continue
            self.vprint(f"Trashed {'directory' if is_dir else 'file'}: {file}")

            info.write_text(
                "[Trash Info]\n"
                f"Path={file.absolute()}\n"
                f"DeletionDate={datetime.now():%Y-%m-%dT%H:%M:%S}\n"
            )
        return err

    def cat_trash(self, files):
        if not files:
            return self.perror("No files to cat")
        files = self.relative_files(files)

        err = 0
        for file in files:
            try:
                if file.is_dir() and self.recursive:
                    self.cat_dir(file)
                else:
                    self.cat_file(file)
            except OSError as e:
                err += self.perror(file, e)
        return err

    def cat_dir(self, dir: Path):
        self.vprint(f"Directory: {dir}")
        for file in dir.iterdir():
            if file.is_dir():
                self.cat_dir(file)
            else:
                self.cat_file(file)

    def cat_file(self, file: Path):
        text = file.read_text()
        self.vprint(f"File: {file}")
        print(text, end="")

    def restore_trash(self, files):
        if not files:
            return self.perror("No files to restore")
        files = self.relative_files(files)

        err = 0
        for file in files:
            if not file.exists():
                err += self.perror(f"{file} does not exist in trash")
                continue

            if file.is_dir() and not self.recursive:
                err += self.perror(f"{file}: Is a directory")
                continue

            dest = self.read_info(file)["Path"]
            if dest == "missing":
                err += self.perror(
                    f"{file}: Missing meta data. Must be manually restored."
                )
                continue
            dest = Path(dest)
            if dest.exists():
                if not self.force and not self.interactive:
                    err += self.perror(f"{dest} already exists")
                    continue
                if self.interactive and not ask_yes_no(f"Overwrite {dest}"):
                    continue
                if self.remove_trash([dest]):
                    continue
            shutil.move(file, dest)
            self.vprint(f"Restored {file.name} to {dest}")
            (self._INFO / f"{file.name}.trashinfo").unlink(missing_ok=True)
        return err

    def vprint(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def perror(self, s: Union[str, Path], err: Union[OSError, None] = None):
        if self.force:
            return 0
        msg = f"trash: {s}"
        if err is not None:
            msg += f": {err.strerror}"
        print(msg, file=sys.stderr)
        return 1

    def ensure_unqiue(self, name: str, suffixes: List[str], count=2):
        trash = self._FILES / f"{name}"
        info = self._INFO / f"{name}.trashinfo"
        if not trash.exists() and not info.exists():
            return (trash, info)

        return self.ensure_unqiue(
            f"{name.split('.')[0]}.{count}{''.join(suffixes)}",
            suffixes,
            count + 1,
        )
