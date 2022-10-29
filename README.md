# Trash

A CLI and implementation of the [FreeDesktop.org Trash Specification][freedesktop-spec]

## Setup

```sh
pip install git+https://github.com/jedwillick/trash
trash --help
```

## Commands

| Command         | Description                                |
| --------------- | ------------------------------------------ |
| `trash remove`  | Move files to the trash                    |
| `trash list`    | List items in the trash                    |
| `trash empty`   | Empty files from the trash                 |
| `trash restore` | Restore files from the trash               |
| `trash cat`     | Concatenate files from the trash to stdout |

[freedesktop-spec]: https://specifications.freedesktop.org/trash-spec/trashspec-1.0.html
