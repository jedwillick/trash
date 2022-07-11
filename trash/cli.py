import argparse
from pathlib import Path

from . import Trash, __version__


def main():
    args = setup_argparse()
    trash = Trash(
        verbose=args.verbose,
        recursive=args.recursive,
        force=args.force,
        interactive=args.interactive,
    )

    return trash.run(args.cmd, args.files)


def setup_cmd(subparser, name, aliases=[], parents=[]):
    cmd = subparser.add_parser(
        name,
        parents=parents,
        help="",
        aliases=aliases,
    )
    cmd.set_defaults(cmd=name)
    return cmd


def setup_argparse():
    root = argparse.ArgumentParser(
        description=(
            "Send items to the trash instead of the void.\n"
            "The default trash location is $XDG_DATA_HOME/Trash.\n"
            "The fallback trash location is ~/.local/share/Trash.\n"
        ),
        epilog=f"%(prog)s {__version__}",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    root.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    base = argparse.ArgumentParser(add_help=False)
    base.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output",
    )
    base.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Ignore non-existent files and always overwrite",
    )
    base.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Prompt before deleting files.",
    )
    base.add_argument(
        "-r",
        "-R",
        "--recursive",
        action="store_true",
        help="Recurse through directories getting all files.",
    )
    base.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files or Directories to operate on."
        "For list, empty and restore this is relative to the trash directory.",
    )
    base.add_argument(
        "-c",
        "--color",
        action="store_true",
        help="Colorize output",
    )

    sub = root.add_subparsers(dest="cmd", metavar="CMD", required=True)
    setup_cmd(sub, "list", aliases=["ls"], parents=[base])
    setup_cmd(sub, "remove", aliases=["rm", "delete", "del"], parents=[base])
    setup_cmd(sub, "empty", aliases=["clean", "void"], parents=[base])
    setup_cmd(sub, "restore", aliases=["rest"], parents=[base])
    setup_cmd(sub, "cat", parents=[base])
    return root.parse_args()
