#!/bin/bash
set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
mkdir -p "$BIN_DIR"

curl -fsSL https://raw.githubusercontent.com/enisbudancamanak/zen-sync/main/zen-sync -o "$BIN_DIR/zen-sync"
chmod +x "$BIN_DIR/zen-sync"

echo "Installed zen-sync to $BIN_DIR/zen-sync"

# Check if bin dir is in PATH
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo "Add this to your shell config: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo "Run 'zen-sync init' to get started."
