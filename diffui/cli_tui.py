from __future__ import annotations

import sys


def main() -> None:
    if "--comments" in sys.argv:
        from diffui.cli import print_comments

        try:
            print_comments()
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    from diffui.app import DiffUI

    repo_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    try:
        DiffUI(repos=repo_args or None).run()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
