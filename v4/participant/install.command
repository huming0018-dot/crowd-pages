#!/bin/zsh
set -eu
umask 077
PACKAGE_DIR="${0:A:h}"
INSTALL_DIR="$HOME/Library/Application Support/CrowdParticipantExtension"
cd "$PACKAGE_DIR"
INSTALL_NONCE="$$-$RANDOM-$RANDOM"
INSTALL_CREATED=false
INSTALL_SUCCESS=false
FAILURE_PAGE="$PACKAGE_DIR/help.html"
cleanup() {
  local install_exit=$?
  if [[ "$INSTALL_CREATED" == true && "$INSTALL_SUCCESS" != true && ! -L "$INSTALL_DIR" && -d "$INSTALL_DIR" ]]; then
    if [[ "$(/usr/bin/stat -f '%d:%i' "$INSTALL_DIR")" == "$INSTALL_INODE" && -f "$INSTALL_DIR/.crowd-install-owner" && "$(/bin/cat "$INSTALL_DIR/.crowd-install-owner")" == "$INSTALL_NONCE" ]]; then
      /bin/rm -rf -- "$INSTALL_DIR"
    fi
  fi
  if (( install_exit != 0 )); then
    print '\n安装暂未完成。不要卸载、清空数据或重复报名。请把窗口最后的错误文字交给邀请人。'
    /usr/bin/open "$FAILURE_PAGE" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT
fail() {
  FAILURE_PAGE="$PACKAGE_DIR/help-$1.html"
  print -r -- "$2"
  exit 1
}
# Pro uses only an existing licensed local installation. No SDK/profile is bundled.
configure_pro_if_present() {
  local pro_settings="$HOME/Library/Application Support/CrowdV4Updater/pro-install-settings.json"
  if [[ -f "$PACKAGE_DIR/configure-pro.py" && -f "$PACKAGE_DIR/pro-runtime/PRO-RUNTIME.json" && -f "$pro_settings" && ! -L "$pro_settings" ]]; then
    local pro_python
    pro_python="$(/usr/bin/plutil -extract python raw -o - "$pro_settings" 2>/dev/null || true)"
    if [[ "$pro_python" == /* && -x "$pro_python" ]]; then
      if "$pro_python" -B "$PACKAGE_DIR/configure-pro.py" --runtime "$PACKAGE_DIR/pro-runtime" --settings "$pro_settings"; then
        print 'Pro 本地适配器已准备；原绑定和采集记录保留。插件还会核对本机依赖后显示就绪。'
        return 0
      fi
    fi
  fi
  print 'Pro 尚未就绪：需要本机已有授权 SDK、Python 环境和原账号绑定；本包不会下载私有 SDK 或替换账号。'
}
print '\n众包采集安装助手：无需输入命令，请等待自动检查。'
print '[1/3] 检查安装包…'
if ! /usr/bin/shasum -a 256 -c INSTALL-SHA256.txt; then
  fail integrity '安装包缺失或校验不一致：请保留原安装，重新下载并完整解压本包。'
fi
MAC_VERSION="$(/usr/bin/sw_vers -productVersion)"
MAC_MAJOR="${MAC_VERSION%%.*}"
if [[ "$MAC_MAJOR" != <-> ]] || (( MAC_MAJOR < 14 )); then
  fail os '本安装包需要 macOS 14 或更新系统。当前设备尚未安装，请先更新系统或联系邀请人。'
fi
CHROME_APP=''
for candidate in '/Applications/Google Chrome.app' "$HOME/Applications/Google Chrome.app"; do
  if [[ -d "$candidate" ]]; then CHROME_APP="$candidate"; break; fi
 done
if [[ -z "$CHROME_APP" ]]; then
  while IFS= read -r candidate; do
    if [[ -d "$candidate" ]]; then CHROME_APP="$candidate"; break; fi
  done < <(/usr/bin/mdfind 'kMDItemCFBundleIdentifier == "com.google.Chrome"' 2>/dev/null)
fi
if [[ -z "$CHROME_APP" ]]; then
  fail chrome '没有找到 Google Chrome。请先安装 Chrome，再双击“开始安装.command”。'
fi
CHROME_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$CHROME_APP/Contents/Info.plist" 2>/dev/null || true)"
CHROME_MAJOR="${CHROME_VERSION%%.*}"
if [[ "$CHROME_MAJOR" != <-> ]] || (( CHROME_MAJOR < 120 )); then
  fail chrome '需要 Chrome 120 或更新版本。请在 Chrome 菜单中的“关于 Google Chrome”完成更新后重试。'
fi
ORIGINAL_DIR=''
if [[ -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  ORIGINAL_DIR="$(/usr/bin/plutil -extract directory raw -expect string -o - "$HOME/Library/Application Support/CrowdV4Updater/config.json" 2>/dev/null || true)"
fi
# Absence of a native helper does not mean Chrome has no older same-ID extension.
PRO_SETTINGS="$HOME/Library/Application Support/CrowdV4Updater/pro-install-settings.json"
NATIVE_CONFIG="$HOME/Library/Application Support/CrowdV4Updater/config.json"
if [[ -n "$ORIGINAL_DIR" && -f "$PRO_SETTINGS" && -f "$NATIVE_CONFIG" ]]; then
  BROWSER_CHECK="$(/usr/bin/osascript -l JavaScript "$PACKAGE_DIR/browser-preflight.js" "$HOME/Library/Application Support/Google/Chrome" "$ORIGINAL_DIR" "$PRO_SETTINGS" "$NATIVE_CONFIG" 2>/dev/null || true)"
else
  BROWSER_CHECK="$(/usr/bin/osascript -l JavaScript "$PACKAGE_DIR/browser-preflight.js" "$HOME/Library/Application Support/Google/Chrome" "$ORIGINAL_DIR" 2>/dev/null || true)"
fi
case "$BROWSER_CHECK" in
  clear|compatible_registered) ;;
  legacy_browser_extension) fail browser-legacy 'Chrome 已安装旧版众包插件，可能有正在进行的任务。原插件、身份和记录保留；本次不覆盖，请联系邀请人安全接续。' ;;
  browser_reconnect_required) fail browser-existing 'Chrome 中已有同一参与者插件，但与当前更新助手的目录不一致。为保留原身份，本次不覆盖；请联系邀请人核对。' ;;
  *) fail browser-unknown '暂时无法确认 Chrome 原插件的安装情况。为保护原身份，本次没有安装或接续；请把此提示交给邀请人。' ;;
esac
if [[ -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  print '[2/3] 找到原标准安装，正在接续；不会重新注册或覆盖采集身份。'
  if [[ -z "$ORIGINAL_DIR" || ! -d "$ORIGINAL_DIR" ]]; then
    fail existing '原更新助手记录的安装目录不存在。已保留原资料，请联系邀请人核对；不要删除目录或重新报名。'
  fi
  if ! ./crowd-v4-participant-updater --check-install "$ORIGINAL_DIR"; then
    fail incompatible '原扩展与本参与者更新不兼容（例如旧 KOL 安装）。已保留原样，请联系邀请人使用对应版本。'
  fi
  if ! ./reconnect.command; then
    fail busy '原安装暂时无法接续，可能正在采集或更新。没有强制切换，请等原插件空闲后重试；仍失败请联系邀请人。'
  fi
  configure_pro_if_present
  INSTALL_SUCCESS=true
  print '[3/3] 原安装已接续。请看刚打开的说明页；等待原插件空闲完成更新。'
  /usr/bin/open -a 'Google Chrome' "$PACKAGE_DIR/existing.html" || /usr/bin/open "$PACKAGE_DIR/existing.html" || true
  exit 0
fi
if [[ -e "$INSTALL_DIR" ]]; then
  fail existing '发现原参与者目录，但未找到标准更新助手。为保留原身份，本次未覆盖，请联系邀请人接续。'
fi
if [[ -f "$HOME/Library/Application Support/CrowdV4LocalTestUpdater/config.json" ]]; then
  print '检测到私人测试版：保留原样。以下另装标准参与者版，不迁移私人版的身份或队列。'
fi
print '[2/3] 准备标准参与者安装，保留现有浏览器资料…'
/bin/mkdir -p "$HOME/Library/Application Support"
/bin/mkdir -m 700 "$INSTALL_DIR"
INSTALL_INODE="$(/usr/bin/stat -f '%d:%i' "$INSTALL_DIR")"
print -r -- "$INSTALL_NONCE" > "$INSTALL_DIR/.crowd-install-owner"
INSTALL_CREATED=true
/usr/bin/unzip -q @EXTENSION_ARCHIVE@ -d "$INSTALL_DIR"
if ! ./crowd-v4-participant-updater --install "$INSTALL_DIR" 'Google Chrome'; then
  fail busy '系统未能完成助手安装。请保留终端错误并联系邀请人；不要删除原扩展或关闭系统保护。'
fi
/bin/rm -- "$INSTALL_DIR/.crowd-install-owner"
configure_pro_if_present
INSTALL_SUCCESS=true
print '[3/3] 安装文件已准备完成。Chrome 的加载确认需要你本人完成。'
print -r -- "$INSTALL_DIR" | /usr/bin/pbcopy || true
print '安装目录已尝试复制到剪贴板，也可以在刚打开的 Finder 中手动选择。'
/usr/bin/open "$INSTALL_DIR" || true
/usr/bin/open -a 'Google Chrome' 'chrome://extensions/' || true
/usr/bin/open -a 'Google Chrome' "$PACKAGE_DIR/new.html" || /usr/bin/open "$PACKAGE_DIR/new.html" || true
print '请看图解完成 Chrome 加载，再打开邀请人给你的原邀请链接。安装成功不等于采集已开始。'
