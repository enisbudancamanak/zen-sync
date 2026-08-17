#!/usr/bin/env python3
"""Merge zen-sessions and sessionstore from two Zen Browser profiles."""

import ctypes
import ctypes.util
import json
import struct
import sys
import os
import shutil
from datetime import datetime


def load_lz4():
    candidates = [
        ctypes.util.find_library("lz4"),
        "liblz4.so.1",
        "liblz4.so",
        "liblz4.dylib",
        "/opt/homebrew/lib/liblz4.dylib",
        "/usr/local/lib/liblz4.dylib",
    ]
    for name in candidates:
        if not name:
            continue
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    sys.exit("error: liblz4 not found (install lz4: brew install lz4 / sudo pacman -S lz4)")


def read_mozlz4(path):
    lib = load_lz4()
    with open(path, "rb") as f:
        data = f.read()
    size = struct.unpack("<I", data[8:12])[0]
    dst = ctypes.create_string_buffer(size + 1000000)
    result = lib.LZ4_decompress_safe(data[12:], dst, len(data) - 12, size + 1000000)
    return json.loads(dst.raw[:result])


def write_mozlz4(path, obj):
    lib = load_lz4()
    data = json.dumps(obj).encode()
    compressed = ctypes.create_string_buffer(len(data) * 2)
    result = lib.LZ4_compress_default(data, compressed, len(data), len(data) * 2)
    with open(path, "wb") as f:
        f.write(b"mozLz40\x00")
        f.write(struct.pack("<I", len(data)))
        f.write(compressed.raw[:result])


def tab_url(tab):
    """Get the last URL from a tab's entries."""
    entries = tab.get("entries", [])
    if entries:
        return entries[-1].get("url", "")
    return ""


def tab_key(tab):
    """Unique key for a tab: URL + workspace."""
    return (tab_url(tab), tab.get("zenWorkspace", ""))


def merge_sessions(local_path, remote_path):
    """Merge zen-sessions.jsonlz4 files."""
    local = read_mozlz4(local_path)
    remote = read_mozlz4(remote_path)

    # Merge spaces by UUID
    local_space_uuids = {s["uuid"] for s in local["spaces"]}
    new_spaces = 0
    for space in remote["spaces"]:
        if space["uuid"] not in local_space_uuids:
            local["spaces"].append(space)
            new_spaces += 1

    # Merge tabs by URL + workspace (deduplicate)
    local_tab_keys = {tab_key(t) for t in local["tabs"]}
    new_tabs = []
    for tab in remote["tabs"]:
        key = tab_key(tab)
        url = key[0]
        # Skip empty/new tabs
        if not url or url in ("about:blank", "about:newtab", "about:home"):
            continue
        if key not in local_tab_keys:
            new_tabs.append(tab)
            local_tab_keys.add(key)

    local["tabs"].extend(new_tabs)

    # Merge folders by id
    local_folder_ids = {f["id"] for f in local.get("folders", [])}
    new_folders = 0
    for folder in remote.get("folders", []):
        if folder["id"] not in local_folder_ids:
            local.setdefault("folders", []).append(folder)
            new_folders += 1

    # Merge groups by id
    local_group_ids = {g["id"] for g in local.get("groups", [])}
    new_groups = 0
    for group in remote.get("groups", []):
        if group["id"] not in local_group_ids:
            local.setdefault("groups", []).append(group)
            new_groups += 1

    return local, new_spaces, len(new_tabs), new_folders, new_groups


def merge_sessionstore(local_path, remote_path, new_tabs):
    """Add new tabs to the sessionstore recovery file."""
    if not os.path.exists(local_path) or not os.path.exists(remote_path):
        return None

    local = read_mozlz4(local_path)

    if not local.get("windows") or not local["windows"]:
        return None

    # Add new tabs to the first window
    window = local["windows"][0]
    existing_keys = set()
    for tab in window.get("tabs", []):
        existing_keys.add(tab_key(tab))

    added = 0
    for tab in new_tabs:
        if tab_key(tab) not in existing_keys:
            window.setdefault("tabs", []).append(tab)
            existing_keys.add(tab_key(tab))
            added += 1

    return local


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <local_profile> <remote_sessions_tmp>")
        sys.exit(1)

    local_profile = sys.argv[1]
    remote_tmp = sys.argv[2]  # directory with remote files

    local_sessions = os.path.join(local_profile, "zen-sessions.jsonlz4")
    remote_sessions = os.path.join(remote_tmp, "zen-sessions.jsonlz4")
    local_recovery = os.path.join(local_profile, "sessionstore-backups", "recovery.jsonlz4")
    remote_recovery = os.path.join(remote_tmp, "recovery.jsonlz4")

    if not os.path.exists(local_sessions):
        print("error: local zen-sessions.jsonlz4 not found")
        sys.exit(1)
    if not os.path.exists(remote_sessions):
        print("error: remote zen-sessions.jsonlz4 not found")
        sys.exit(1)

    # Backup local files
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(local_profile, f"zen-sessions.jsonlz4.merge-backup-{ts}")
    shutil.copy2(local_sessions, backup)

    # Merge zen-sessions
    merged, new_spaces, new_tabs_count, new_folders, new_groups = merge_sessions(
        local_sessions, remote_sessions
    )

    # Get the actual new tab objects for sessionstore merge
    if new_tabs_count > 0:
        remote_data = read_mozlz4(remote_sessions)
        local_data = read_mozlz4(local_sessions)
        local_keys = {tab_key(t) for t in local_data["tabs"]}
        new_tab_objects = []
        for tab in remote_data["tabs"]:
            url = tab_url(tab)
            if not url or url in ("about:blank", "about:newtab", "about:home"):
                continue
            if tab_key(tab) not in local_keys:
                new_tab_objects.append(tab)
    else:
        new_tab_objects = []

    # Write merged zen-sessions
    write_mozlz4(local_sessions, merged)

    # Merge sessionstore if possible
    session_merged = False
    if os.path.exists(local_recovery) and os.path.exists(remote_recovery) and new_tab_objects:
        merged_session = merge_sessionstore(local_recovery, remote_recovery, new_tab_objects)
        if merged_session:
            backup_recovery = os.path.join(
                local_profile, "sessionstore-backups",
                f"recovery.jsonlz4.merge-backup-{ts}"
            )
            shutil.copy2(local_recovery, backup_recovery)
            write_mozlz4(local_recovery, merged_session)
            session_merged = True

    # Output results as JSON for the bash script
    result = {
        "new_spaces": new_spaces,
        "new_tabs": new_tabs_count,
        "new_folders": new_folders,
        "new_groups": new_groups,
        "session_merged": session_merged,
        "backup": backup,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
