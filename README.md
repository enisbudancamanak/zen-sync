<p align="center">
  <h1 align="center">zen-sync</h1>
  <p align="center">Sync Zen Browser spaces, tabs & sessions across devices via SSH</p>
</p>

<p align="center">
  <a href="#install">Install</a> &bull;
  <a href="#usage">Usage</a> &bull;
  <a href="#how-it-works">How it works</a> &bull;
  <a href="#limitations">Limitations</a> &bull;
  <a href="LICENSE">License</a>
</p>

---

> **Linux only** — tested on Arch Linux with Wayland. May work on other distros but is not tested.

Zen Browser doesn't sync spaces or tabs across devices yet. **zen-sync** fills that gap — push your entire browsing session from one machine to another in seconds.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/enisbudancamanak/zen-sync/main/install.sh | bash
```

Then run the setup wizard:

```bash
zen-sync init
```

### Requirements

- Linux (tested on Arch Linux with Wayland/Hyprland)
- Zen Browser (same version on both devices)
- SSH access between devices (ideally with key-based auth via `ssh-copy-id`)
- `rsync` (only for `--full` mode)
- `python3` + `liblz4` (only for `zen-sync status`)

## Usage

```bash
# Push local session to remote device
zen-sync push

# Pull remote session to local device
zen-sync pull

# Auto-close Zen on target, sync, and reopen it
zen-sync push --restart
zen-sync pull --restart

# Compare spaces on both devices
zen-sync status

# Full profile sync (first-time setup or troubleshooting)
zen-sync push --full
zen-sync pull --full
```

### Recommended workflow

```bash
# From your main machine, push to the other:
zen-sync push --restart
```

This will close Zen on the remote device, sync the session files, and reopen Zen — all in one command. No need to manually close anything.

Without `--restart`, Zen must be closed on the target device before syncing.

## How it works

### Light sync (default)

Copies only the files that matter:

| File | What it contains |
|------|-----------------|
| `zen-sessions.jsonlz4` | Space definitions & tab-to-space assignments |
| `sessionstore-backups/recovery.jsonlz4` | Active session with all open tabs |
| `sessionstore-backups/recovery.baklz4` | Session backup |
| `sessionstore-backups/previous.jsonlz4` | Previous session |
| `prefs.js` | Active workspace & preferences |
| `containers.json` | Container tab configuration |

This takes ~10 seconds over a local network.

### Full sync (`--full`)

Uses `rsync` to transfer the entire profile directory (excluding caches). Useful for initial setup or when light sync isn't enough — for example, syncing extensions, bookmarks, or passwords that aren't covered by light sync.

## Limitations

> This tool was built for a specific setup and may need adjustments for yours.

**Tested environment:**
- Arch Linux on both devices (desktop + laptop)
- Wayland (Hyprland) — the `--restart` flag uses `WAYLAND_DISPLAY=wayland-1`
- Same username (`enisdev`) on both machines
- Local network (SSH over LAN)

**Known limitations:**
- **Linux only** — macOS and Windows store Zen profiles in different locations
- **Wayland assumption** — the `--restart` reopen uses hardcoded `WAYLAND_DISPLAY=wayland-1`. X11 or different Wayland compositors may need adjustment
- **Single remote** — only one remote device is supported per config
- **No conflict resolution** — last push/pull wins. There's no merge logic
- **No encryption** — files are transferred via SSH (encrypted in transit) but not at rest
- **Profile paths are fixed after init** — if Zen creates a new profile, re-run `zen-sync init`

**What light sync does NOT transfer:**
- Bookmarks, passwords, history (use Firefox Sync for these)
- Extensions and their data
- Cookies and site storage
- Cached data

Use `--full` for a complete profile transfer that includes everything above.

## Good to know

- Config lives in `~/.config/zen-sync/config`
- Profile paths are auto-detected during `zen-sync init`
- Both devices should run the **same Zen version** to avoid compatibility issues
- Zen stores spaces in `zen-sessions.jsonlz4` (Mozilla LZ4 compressed JSON) and tabs in the sessionstore — both need to be in sync

## Background

Zen Browser (based on Firefox) doesn't offer cross-device sync for its custom features like spaces and workspaces. Firefox Sync handles bookmarks, passwords, and history, but not Zen-specific data.

This tool works similarly to [sharing a profile folder on a dual-boot system](https://github.com/zen-browser/desktop/discussions/2400) — transferring the raw session files between machines.

## License

[MIT](LICENSE)
