from __future__ import annotations

import json
import socket
import sys

from diffui.git_utils import (
    current_branch,
    get_changed_files,
    get_main_branch,
    get_merge_base,
    is_comment_open,
    load_comments,
    load_reviewed,
    resolve_repos,
    set_active_repo,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _setup_repo() -> tuple[list, int]:
    repo_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    repos, active_index = resolve_repos(repo_args or None)
    set_active_repo(repos[active_index])
    return repos, active_index


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


def export_json() -> None:
    branch_name = current_branch()
    main_branch = get_main_branch()
    merge_base = get_merge_base(main_branch)
    all_files = get_changed_files(merge_base)
    reviewed = load_reviewed()
    comments = load_comments()

    file_list = []
    for path in all_files:
        file_comments = comments.get(path, [])
        file_list.append(
            {
                "path": path,
                "reviewed": path in reviewed,
                "comments": file_comments,
                "open_comment_count": sum(1 for c in file_comments if is_comment_open(c)),
            }
        )

    total_files = len(all_files)
    reviewed_count = sum(1 for f in file_list if f["reviewed"])
    total_comments = sum(len(f["comments"]) for f in file_list)
    open_count = sum(f["open_comment_count"] for f in file_list)

    output = {
        "branch": branch_name,
        "main_branch": main_branch,
        "merge_base": merge_base,
        "summary": {
            "total_files": total_files,
            "reviewed_files": reviewed_count,
            "total_comments": total_comments,
            "open_comments": open_count,
            "resolved_comments": total_comments - open_count,
        },
        "files": file_list,
    }
    print(json.dumps(output, indent=2))


def main() -> None:
    if "--comments" in sys.argv:
        try:
            print_comments()
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if "--json" in sys.argv:
        try:
            _setup_repo()
            export_json()
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        repos, active_index = _setup_repo()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    from diffui.server.app import create_app

    port = _find_free_port()
    app = create_app(repos, active_index=active_index)

    import uvicorn

    url = f"http://localhost:{port}"
    print(f"diffui running at {url}", file=sys.stderr)
    if "--open" in sys.argv:
        import threading
        import webbrowser

        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
