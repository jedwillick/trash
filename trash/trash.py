import errno
import functools
import os
import shutil
import subprocess as sp
import sys
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Union

eprint = functools.partial(print, file=sys.stderr)


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

    def run(self, cmd, files):

        # Trash relative files
        files_ = functools.partial(self.relative_files, files)

        if cmd == "remove":
            return self.remove_trash(files)
        elif cmd == "list":
            return self.list_trash(files_(True))
        elif cmd == "empty":
            return self.empty_trash(files_(True))
        elif cmd == "restore":
            return self.restore_trash(files_(False))
        elif cmd == "cat":
            return self.cat_trash(files_(False))
        else:
            return self.perror(f"Unknown command {cmd}")

    def relative_files(self, files, fill_empty=False):
        if not files:
            return list(self._FILES.iterdir()) if fill_empty else files

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
        if not files:
            return
        files.sort()

        cmd = ["ls", *files, "-A"]
        if self.verbose:
            cmd.append("-l")
        if files:
            cmd.append("-d")

        p = sp.run(cmd, capture_output=self.verbose, text=True)

        if not self.verbose or p.returncode != 0:
            return p.returncode

        for line, file in zip(p.stdout.splitlines(), files):
            info = self._INFO / f"{file.name}.trashinfo"
            meta = "missing"
            if info.exists():
                config = ConfigParser()
                config.read(info)
                meta = config["Trash Info"].get("Path", "missing")
            print(f"{line} => {meta}")

        return 0

    def prompt(self, msg):
        return input(f"{msg} (y/N): ").lower() == "y"

    def empty_trash(self, files):
        err = 0
        for file in files:
            if self.interactive and not self.prompt(f"Delete {file}"):
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

        err = 0

        for file in files:
            info = self._INFO / f"{file.name}.trashinfo"
            if not info.exists():
                eprint(f"{info} does not exist")
                err += 1
                continue

            config = ConfigParser()
            config.read(info)
            dest = config["Trash Info"].get("Path", "missing")
            if dest == "missing":
                eprint(f"{info} is missing Path")
                err += 1
                continue
            dest = Path(dest)
            if dest.exists():
                if not self.force and not self.interactive:
                    eprint(f"{dest} already exists")
                    err += 1
                    continue
                if self.interactive and not self.prompt(f"Overwrite {dest}"):
                    continue
                if self.remove_trash([dest]):
                    continue
            shutil.move(file, dest)
            self.vprint(f"Restored {file.name} to {dest}")
            info.unlink()
        return err

    def vprint(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def perror(self, s, err=None):
        if self.force:
            return 0
        msg = f"trash: {s}"
        if err is not None:
            msg += f": {err.strerror}"
        eprint(msg)
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
