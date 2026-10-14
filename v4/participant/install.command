#!/bin/zsh
set -eu
PACKAGE_DIR="${0:A:h}"
INSTALL_DIR="$HOME/Library/Application Support/CrowdParticipantExtension"
cd "$PACKAGE_DIR"
/usr/bin/shasum -a 256 -c INSTALL-SHA256.txt
if [[ -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  ./reconnect.command
  exit 0
fi
if [[ -e "$INSTALL_DIR" ]]; then
  print '已存在参与者安装。请使用已接通的 OTA 或联系 Owner；本安装器不会覆盖旧目录。'
  exit 1
fi
INSTALL_NONCE="$$-$RANDOM-$RANDOM"
INSTALL_CREATED=false
INSTALL_SUCCESS=false
cleanup() {
  if [[ "$INSTALL_CREATED" == true && "$INSTALL_SUCCESS" != true && ! -L "$INSTALL_DIR" && -d "$INSTALL_DIR" ]]; then
    if [[ "$(/usr/bin/stat -f '%d:%i' "$INSTALL_DIR")" == "$INSTALL_INODE" && -f "$INSTALL_DIR/.crowd-install-owner" && "$(/bin/cat "$INSTALL_DIR/.crowd-install-owner")" == "$INSTALL_NONCE" ]]; then
      /bin/rm -rf -- "$INSTALL_DIR"
    fi
  fi
}
trap cleanup EXIT
/bin/mkdir -m 700 "$INSTALL_DIR"
INSTALL_INODE="$(/usr/bin/stat -f '%d:%i' "$INSTALL_DIR")"
print -r -- "$INSTALL_NONCE" > "$INSTALL_DIR/.crowd-install-owner"
INSTALL_CREATED=true
/usr/bin/unzip -q @EXTENSION_ARCHIVE@ -d "$INSTALL_DIR"
./crowd-v4-participant-updater --install "$INSTALL_DIR" 'Google Chrome'
/bin/rm -- "$INSTALL_DIR/.crowd-install-owner"
INSTALL_SUCCESS=true
print '请在 Chrome 扩展页开启开发者模式，点击加载已解压扩展，选择刚打开的安装目录。之后从 Owner 邀请链接加入并确认采集；任务自动领取。'
/usr/bin/open "$INSTALL_DIR"
/usr/bin/open -a 'Google Chrome' 'chrome://extensions/'
