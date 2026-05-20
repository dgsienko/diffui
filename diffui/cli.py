from __future__ import annotations

import sys

from diffui.git_utils import load_comments


def print_comments() -> None:
    comments = load_comments()
    if not comments:
        print("No comments.")
        return
    for file_path, file_comments in comments.items():
        for c in file_comments:
            line_num = c.get("file_line_num", c.get("line_index", "?"))
            line_text = c.get("line_text", "").strip()
            comment = c.get("comment", "")
            print(f"{file_path}:{line_num}")
            if line_text:
                print(f"  > {line_text}")
            print(f"  {comment}")
            print()


def main() -> None:
    if "--comments" in sys.argv:
        try:
            print_comments()
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    from diffui.app import DiffUI

    try:
        DiffUI().run()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
