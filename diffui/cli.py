from __future__ import annotations

import socket
import sys
import threading
import webbrowser
from pathlib import Path

from diffui.git_utils import (
    discover_sibling_repos,
    load_comments,
    resolve_repo_root,
    set_active_repo,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


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

    repo_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    try:
        if repo_args:
            seen: set[Path] = set()
            repos: list[Path] = []
            for p in repo_args:
                root = resolve_repo_root(Path(p).expanduser().resolve())
                if root not in seen:
                    seen.add(root)
                    repos.append(root)
            active_index = 0
        else:
            current = resolve_repo_root(Path.cwd())
            siblings = discover_sibling_repos(current)
            repos = siblings if len(siblings) > 1 else [current]
            active_index = repos.index(current)

        set_active_repo(repos[active_index])
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from diffui.server.app import create_app

    port = _find_free_port()
    app = create_app(repos)

    import uvicorn

    url = f"http://localhost:{port}"
    print(f"diffui running at {url}", file=sys.stderr)
    if "--open" in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
