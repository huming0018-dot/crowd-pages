#!/bin/zsh
set -eu
PACKAGE_DIR="${0:A:h}"
if [[ ! -f "$PACKAGE_DIR/.crowd-support/install.command" ]]; then
  print '安装包不完整，或“开始安装.command”被单独移走。请重新完整解压，不要单独移动文件。'
  /usr/bin/osascript -e 'display alert "安装包不完整" message "请重新解压整个安装包，再双击里面的“开始安装.command”。不要单独移动这个文件。" as critical' || true
  exit 1
fi
exec "$PACKAGE_DIR/.crowd-support/install.command"
