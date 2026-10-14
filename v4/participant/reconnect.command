#!/bin/zsh
set -eu
PACKAGE_DIR="${0:A:h}"
cd "$PACKAGE_DIR"
/usr/bin/shasum -a 256 -c MIGRATE-SHA256.txt
if [[ ! -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  print '没有找到原标准更新助手。首次安装请运行 install.command；本人私人测试通道与旧KOL安装不自动迁移。'
  exit 1
fi
# Native helper reads only its fixed config.directory, validates the exact approved
# standard manifest, backs up helper/config/state, and keeps the original directory.
./crowd-v4-participant-updater --reconnect 'Google Chrome'
print '原标准更新助手已重新接通参与者通道，插件目录、身份和待回传记录保留。等待原插件空闲时正常OTA，不关闭浏览器或强制重载。'
