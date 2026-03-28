<p align="center">
  <h1 align="center">zen-sync</h1>
  <p align="center">Sync Zen Browser spaces, tabs & sessions across devices via SSH</p>
</p>

<p align="center">
  <a href="#install">Install</a> &bull;
  <a href="#usage">Usage</a> &bull;
  <a href="#how-it-works">How it works</a> &bull;
  <a href="LICENSE">License</a>
</p>

---

Zen Browser doesn't sync spaces or tabs across devices yet. **zen-sync** fills that gap — push your entire browsing session from one machine to another in seconds.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/enisbudancamanak/zen-sync/main/zen-sync -o ~/.local/bin/zen-sync && chmod +x ~/.local/bin/zen-sync
```

Then run the setup wizard:

```bash
zen-sync init
```

### Requirements

- Zen Browser (same version on both devices)
- SSH access between devices
- `rsync` (only for `--full` mode)

## Usage

> **Always close Zen Browser on the target device before syncing.**

```bash
# Push local session to remote device
zen-sync push

# Pull remote session to local device
zen-sync pull

# Compare spaces on both devices
zen-sync status

# Full profile sync (first-time setup or troubleshooting)
zen-sync push --full
zen-sync pull --full
```

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
