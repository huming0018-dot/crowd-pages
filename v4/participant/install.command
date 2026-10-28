#!/bin/zsh
set -eu
umask 077
# Explicit local operator capacity; no environment/native/remote task can set it.
PRO_INSTALL_OPTIONS=()
if (( $# )); then
  if (( $# != 2 )) || [[ "$1" != --pro-max-api-requests ]] || [[ ! "$2" =~ '^([1-9][0-9]?|100)$' ]]; then
    print '用法：开始安装.command [--pro-max-api-requests 1..100]；原设置未更改。'
    exit 2
  fi
  PRO_INSTALL_OPTIONS=(--max-api-requests "$2")
fi
PACKAGE_DIR="${0:A:h}"
PACKAGE_NATIVE_PROTOCOL='@NATIVE_PROTOCOL@'
PACKAGE_R3_BASE_MIGRATION='@R3_BASE_MIGRATION@'
PACKAGE_FIXTURE_ONLY='@FIXTURE_ONLY@'
PACKAGE_FRESH_ONLY='@FRESH_ONLY@'
if [[ "$PACKAGE_FIXTURE_ONLY" == true ]]; then
  print '此包仅供隔离验收，不能在参与者电脑上安装。'
  exit 1
fi
INSTALL_DIR="$HOME/Library/Application Support/CrowdParticipantExtension"
cd "$PACKAGE_DIR"
INSTALL_NONCE="$$-$RANDOM-$RANDOM"
INSTALL_CREATED=false
INSTALL_SUCCESS=false
CHROME_WORK_DIR=''
CHROME_MOUNT_POINT=''
CHROME_TARGET=''
CHROME_TARGET_INODE=''
CHROME_INSTALLED=false
FAILURE_PAGE="$PACKAGE_DIR/help.html"
cleanup() {
  local install_exit=$?
  if [[ "$CHROME_INSTALLED" != true && -n "$CHROME_TARGET_INODE" && ! -L "$CHROME_TARGET" && -d "$CHROME_TARGET" ]]; then
    if [[ "$(/usr/bin/stat -f '%d:%i' "$CHROME_TARGET" 2>/dev/null || true)" == "$CHROME_TARGET_INODE" ]]; then
      /bin/rm -rf -- "$CHROME_TARGET"
    fi
  fi
  if [[ -n "$CHROME_MOUNT_POINT" ]]; then
    /usr/bin/hdiutil detach -quiet "$CHROME_MOUNT_POINT" >/dev/null 2>&1 || true
  fi
  if [[ -n "$CHROME_WORK_DIR" && ! -L "$CHROME_WORK_DIR" && -d "$CHROME_WORK_DIR" ]]; then
    /bin/rm -rf -- "$CHROME_WORK_DIR"
  fi
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
  local pro_helper="$HOME/Library/Application Support/CrowdV4Updater"
  local pro_dependencies="$pro_helper/pro-dependency-settings.json"
  # Package contents select the optional enhancement, never another installation's settings.
  local pro_payload=false pro_file
  for pro_file in pro-runtime configure-pro.py bootstrap-pro-tools.command prepare-pro-dependencies.py prepare-and-configure-pro.py prepare-pro-downloader.py pro-binding-continuation.py portable_node.py PRO-LOCAL-SOURCE-PINS.json; do
    if [[ -e "$PACKAGE_DIR/$pro_file" || -L "$PACKAGE_DIR/$pro_file" ]]; then pro_payload=true; break; fi
  done
  if [[ "$pro_payload" == false ]]; then
    if (( ${#PRO_INSTALL_OPTIONS} )); then
      print '基础采集包不接受 Pro 额度设置；原配置未更改。'
      return 1
    fi
    print '基础采集包无需 Pro 组件；本机已有增强配置保持不变。'
    return 0
  fi
  if [[ ! -d "$PACKAGE_DIR/pro-runtime" || -L "$PACKAGE_DIR/pro-runtime" || ! -f "$PACKAGE_DIR/pro-runtime/PRO-RUNTIME.json" || -L "$PACKAGE_DIR/pro-runtime/PRO-RUNTIME.json" ]]; then
    print 'Pro 增强包资源不完整；本次未更改原配置，请重新取得完整安装包。'
    return 1
  fi
  if [[ -f "$pro_dependencies" && ! -L "$pro_dependencies" ]] || [[ ! -e "$pro_settings" && ! -L "$pro_settings" && -f "$PACKAGE_DIR/pro-runtime/PRO-RUNTIME.json" ]]; then
    print '正在按官方锁文件准备 Pro 和签名服务依赖；不下载私有 SDK、不启动采集。'
    local pro_install_python
    if ! pro_install_python="$(/bin/sh "$PACKAGE_DIR/bootstrap-pro-tools.command" --helper-root "$pro_helper" --python-path)"; then
      print 'Pro 安装工具尚未准备完成；原安装与账号保留，当前不能开始采集。'
      return 1
    fi
    if [[ "$pro_install_python" != /* || ! -x "$pro_install_python" ]]; then return 1; fi
    if "$pro_install_python" -B "$PACKAGE_DIR/prepare-and-configure-pro.py" --descriptor "$pro_dependencies" --settings "$pro_settings" --runtime "$PACKAGE_DIR/pro-runtime" --helper-root "$pro_helper" "${PRO_INSTALL_OPTIONS[@]}"; then
      print 'Pro 依赖准备步骤完成；本机登录和账号绑定仍须就绪后才能开始采集。'
    else
      print 'Pro 依赖/签名服务/绑定尚未就绪，原设置与采集记录保持；请保留上方固定错误。'
      return 1
    fi
    return 0
  fi
  if (( ${#PRO_INSTALL_OPTIONS} )); then
    print '明确的新额度需要原依赖描述文件与绑定接续事务；本次未更改原配置。'
    return 1
  fi
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
  CHROME_TARGET="$HOME/Applications/Google Chrome.app"
  if [[ -e "$CHROME_TARGET" || -L "$CHROME_TARGET" || -L "$HOME/Applications" || ( -e "$HOME/Applications" && ! -d "$HOME/Applications" ) ]]; then
    fail chrome 'Chrome 安装位置已被占用或不可用；没有覆盖现有文件。请检查后重新双击“开始安装.command”，仍失败可从 Google 官网安装。'
  fi
  print '未找到 Google Chrome，正在从 Google 官方下载并安装到当前用户的 Applications…'
  if ! CHROME_WORK_DIR="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/crowd-chrome.XXXXXXXX")"; then
    fail chrome '无法准备 Chrome 临时目录。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  CHROME_MOUNT_POINT="$CHROME_WORK_DIR/mount"
  /bin/mkdir "$CHROME_MOUNT_POINT"
  if ! /usr/bin/curl --fail --location --show-error --silent --retry 2 --connect-timeout 20 --proto '=https' --proto-redir '=https' --output "$CHROME_WORK_DIR/googlechrome.dmg" 'https://dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg'; then
    fail chrome 'Chrome 官方下载失败。请检查网络后重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  if ! /usr/bin/hdiutil attach -quiet -noautoopen -readonly -mountpoint "$CHROME_MOUNT_POINT" "$CHROME_WORK_DIR/googlechrome.dmg"; then
    fail chrome 'Chrome 安装镜像无法挂载。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  CHROME_SOURCE="$CHROME_MOUNT_POINT/Google Chrome.app"
  CHROME_SOURCE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$CHROME_SOURCE/Contents/Info.plist" 2>/dev/null || true)"
  CHROME_SOURCE_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$CHROME_SOURCE/Contents/Info.plist" 2>/dev/null || true)"
  CHROME_SOURCE_MAJOR="${CHROME_SOURCE_VERSION%%.*}"
  if [[ ! -d "$CHROME_SOURCE" || -L "$CHROME_SOURCE" || "$CHROME_SOURCE_ID" != com.google.Chrome || "$CHROME_SOURCE_MAJOR" != <-> ]] || (( CHROME_SOURCE_MAJOR < 120 )); then
    fail chrome '下载的镜像没有可用的 Chrome 120 或更新版本。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  if [[ ! -d "$HOME/Applications" ]] && ! /bin/mkdir -m 700 "$HOME/Applications"; then
    fail chrome '无法创建当前用户的 Applications 目录。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  if ! /bin/mkdir -m 755 "$CHROME_TARGET"; then
    fail chrome 'Chrome 安装位置已经存在；没有覆盖原文件。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  CHROME_TARGET_INODE="$(/usr/bin/stat -f '%d:%i' "$CHROME_TARGET")"
  if ! /usr/bin/ditto "$CHROME_SOURCE" "$CHROME_TARGET" || [[ ! -f "$CHROME_TARGET/Contents/Info.plist" ]]; then
    fail chrome '复制 Chrome 失败；本次创建的不完整目录会清理。请重新双击“开始安装.command”；仍失败可从 Google 官网安装。'
  fi
  CHROME_INSTALLED=true
  CHROME_APP="$CHROME_TARGET"
  print 'Google Chrome 已装入当前用户的 Applications，继续准备扩展和助手。'
fi
CHROME_VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$CHROME_APP/Contents/Info.plist" 2>/dev/null || true)"
CHROME_MAJOR="${CHROME_VERSION%%.*}"
if [[ "$CHROME_MAJOR" != <-> ]] || (( CHROME_MAJOR < 120 )); then
  fail chrome '需要 Chrome 120 或更新版本。请在 Chrome 菜单中的“关于 Google Chrome”完成更新后重试。'
fi
if [[ "$PACKAGE_FRESH_ONLY" == true && ( -e "$HOME/Library/Application Support/CrowdV4Updater" || -L "$HOME/Library/Application Support/CrowdV4Updater" || -e "$INSTALL_DIR" || -L "$INSTALL_DIR" ) ]]; then
  fail existing '此包只供全新参与者安装；检测到原更新助手或参与者目录。旧Pro/R3安装、身份和待回传记录均未覆盖，请联系邀请人接续。'
fi
ORIGINAL_DIR=''
if [[ -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  ORIGINAL_DIR="$(/usr/bin/plutil -extract directory raw -expect string -o - "$HOME/Library/Application Support/CrowdV4Updater/config.json" 2>/dev/null || true)"
fi
if [[ "$PACKAGE_R3_BASE_MIGRATION" == true && -z "$ORIGINAL_DIR" ]]; then
  fail existing '此接续包只接受已有冻结R3基础安装；没有原更新助手目录，本次不安装新身份。'
fi
# Absence of a native helper does not mean Chrome has no older same-ID extension.
BROWSER_CHECK="$("$PACKAGE_DIR/browser-preflight.command" "$ORIGINAL_DIR" 2>/dev/null || true)"
case "$BROWSER_CHECK" in
  clear|compatible_registered) ;;
  legacy_browser_extension) fail browser-legacy 'Chrome 已安装旧版众包插件，可能有正在进行的任务。原插件、身份和记录保留；本次不覆盖，请联系邀请人安全接续。' ;;
  browser_reconnect_required) fail browser-existing 'Chrome 中已有同一参与者插件，但与当前更新助手的目录不一致。为保留原身份，本次不覆盖；请联系邀请人核对。' ;;
  *) fail browser-unknown '暂时无法确认 Chrome 原插件的安装情况。为保护原身份，本次没有安装或接续；请把此提示交给邀请人。' ;;
esac
if [[ "$PACKAGE_FRESH_ONLY" == true && "$BROWSER_CHECK" != clear ]]; then
  fail browser-existing 'Chrome 已有同一参与者插件；此新装包不覆盖原插件或身份，请联系邀请人接续。'
fi
if [[ "$PACKAGE_R3_BASE_MIGRATION" == true && "$BROWSER_CHECK" != compatible_registered ]]; then
  fail browser-existing '没有核到同一Chrome资料中的原R3插件；本次未接续。'
fi
if [[ "$PACKAGE_NATIVE_PROTOCOL" != participant_pro_v2 && -n "$ORIGINAL_DIR" && ( -e "$ORIGINAL_DIR/src/participant-pro.js" || -L "$ORIGINAL_DIR/src/participant-pro.js" ) ]]; then
  fail incompatible '检测到原参与者是 Pro 客户端。基础包不会替换其 Native helper；原安装已保留，请使用对应 Pro 接续包。'
fi
if [[ -f "$HOME/Library/Application Support/CrowdV4Updater/config.json" ]]; then
  print '[2/3] 找到原标准安装，正在接续；不会重新注册或覆盖采集身份。'
  if [[ -z "$ORIGINAL_DIR" || ! -d "$ORIGINAL_DIR" ]]; then
    fail existing '原更新助手记录的安装目录不存在。已保留原资料，请联系邀请人核对；不要删除目录或重新报名。'
  fi
  if ! ./crowd-v4-participant-updater --check-install "$ORIGINAL_DIR"; then
    fail incompatible '原扩展与本参与者更新不兼容（例如旧 KOL 安装）。已保留原样，请联系邀请人使用对应版本。'
  fi
  # Prepare own Python only after exact native preflight, before this reconnect
  # starts new launchd polls which may immediately compete for update.lock.
  configure_pro_if_present
  if ! ./reconnect.command; then
    fail busy '原安装暂时无法接续，可能正在采集或更新。没有强制切换，请等原插件空闲后重试；仍失败请联系邀请人。'
  fi
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
# Fresh dependencies finish before an extension directory or Native host is registered.
configure_pro_if_present
print '[2/3] 准备标准参与者安装，保留现有浏览器资料…'
/bin/mkdir -p "$HOME/Library/Application Support"
/bin/mkdir -m 700 "$INSTALL_DIR"
INSTALL_INODE="$(/usr/bin/stat -f '%d:%i' "$INSTALL_DIR")"
print -r -- "$INSTALL_NONCE" > "$INSTALL_DIR/.crowd-install-owner"
INSTALL_CREATED=true
/usr/bin/unzip -q @EXTENSION_ARCHIVE@ -d "$INSTALL_DIR"
# The ordinary shell can prepare Chrome's native-host directory before the helper registers itself.
NATIVE_HOSTS="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
for native_path in "$HOME/Library" "$HOME/Library/Application Support" "$HOME/Library/Application Support/Google" "$HOME/Library/Application Support/Google/Chrome" "$NATIVE_HOSTS"; do
  if [[ -e "$native_path" || -L "$native_path" ]]; then
    if [[ -L "$native_path" || ! -d "$native_path" || "$(/usr/bin/stat -f '%u' "$native_path" 2>/dev/null || true)" != "$EUID" ]]; then
      fail native-host 'Chrome 助手目录含符号链接、非目录或非当前用户所有；本次没有覆盖原文件，请联系邀请人核对。'
    fi
  fi
done
if ! /bin/mkdir -m 700 -p "$NATIVE_HOSTS"; then
  fail native-host '无法准备 Chrome 助手目录；本次未注册助手。请重新双击“开始安装.command”，仍失败请联系邀请人。'
fi
if [[ -L "$NATIVE_HOSTS" || ! -d "$NATIVE_HOSTS" || "$(/usr/bin/stat -f '%u' "$NATIVE_HOSTS" 2>/dev/null || true)" != "$EUID" || -e "$NATIVE_HOSTS/com.crowd.v4.updater.json" || -L "$NATIVE_HOSTS/com.crowd.v4.updater.json" ]]; then
  fail native-host 'Chrome 助手目录中已有注册文件或目录状态已变化；本次没有覆盖，请联系邀请人核对。'
fi
if ! ./crowd-v4-participant-updater --install "$INSTALL_DIR" 'Google Chrome'; then
  fail busy '系统未能完成助手安装。请保留终端错误并联系邀请人；不要删除原扩展或关闭系统保护。'
fi
/bin/rm -- "$INSTALL_DIR/.crowd-install-owner"
INSTALL_SUCCESS=true
print '[3/3] 安装文件已准备完成。Chrome 的加载确认需要你本人完成。'
print -r -- "$INSTALL_DIR" | /usr/bin/pbcopy || true
print '安装目录已尝试复制到剪贴板，也可以在刚打开的 Finder 中手动选择。'
/usr/bin/open "$INSTALL_DIR" || true
/usr/bin/open -a 'Google Chrome' 'chrome://extensions/' || true
/usr/bin/open -a 'Google Chrome' "$PACKAGE_DIR/new.html" || /usr/bin/open "$PACKAGE_DIR/new.html" || true
print '请看图解完成 Chrome 加载，再打开邀请人给你的原邀请链接。安装成功不等于采集已开始。'
