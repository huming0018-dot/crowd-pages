#!/bin/zsh
# Shared read-only argument selection for install and reconnect. No browser is opened.
set -eu
PACKAGE_DIR="${0:A:h}"
if (( $# != 1 )); then print 'browser_inventory_unavailable'; exit 1; fi
ORIGINAL_DIR="$1"
NATIVE_CONFIG="$HOME/Library/Application Support/CrowdV4Updater/config.json"
PRO_SETTINGS="$HOME/Library/Application Support/CrowdV4Updater/pro-install-settings.json"
if [[ -n "$ORIGINAL_DIR" && -f "$PRO_SETTINGS" && -f "$NATIVE_CONFIG" ]]; then
  exec /usr/bin/osascript -l JavaScript "$PACKAGE_DIR/browser-preflight.js" "$HOME/Library/Application Support/Google/Chrome" "$ORIGINAL_DIR" "$PRO_SETTINGS" "$NATIVE_CONFIG"
fi
exec /usr/bin/osascript -l JavaScript "$PACKAGE_DIR/browser-preflight.js" "$HOME/Library/Application Support/Google/Chrome" "$ORIGINAL_DIR"
