#!/bin/bash
set -euo pipefail

PREFIX="${PREFIX:-/usr/local/bin}"

if [[ -w "$PREFIX" ]]; then
    cp zen-sync "$PREFIX/zen-sync"
else
    sudo cp zen-sync "$PREFIX/zen-sync"
fi

chmod +x "$PREFIX/zen-sync"
echo "Installed zen-sync to $PREFIX/zen-sync"
echo "Run 'zen-sync init' to get started."
