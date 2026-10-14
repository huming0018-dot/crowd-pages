#!/bin/zsh
# This one-time guide invokes only the installed, checksum-pinned participant helper.
set -u
setopt PIPE_FAIL
umask 077

SUPPORT="$HOME/Library/Application Support/CrowdV4Updater"
HELPER="$SUPPORT/crowd-v4-updater"
EXPECTED='b3b059d7be6eaf88b4ca3dd4652eb95a7f5faf65db91e03f5793b8bc0662b212'
CONFIG="$SUPPORT/config.json"
STATE="$SUPPORT/state.json"
TARGET='4.2.65'

finish() {
  local code="$1"
  shift
  print -r -- "$@"
  print ''
  print '原身份、浏览器登录和已采记录不需要重装。不要卸载或清数据。'
  if [[ -t 0 ]]; then
    read -r '?按回车关闭这个窗口。'
  fi
  exit "$code"
}
field() {
  /usr/bin/plutil -extract "$2" raw -o - "$1" 2>/dev/null
}
owned_file() {
  [[ -f "$1" && ! -L "$1" && "${1:A}" == "$1" && "$(/usr/bin/stat -f '%u' "$1" 2>/dev/null)" == "$(/usr/bin/id -u)" ]]
}
print '完成众包插件更新（需要联网）'
print '请先保存浏览器中的工作，并亲自在菜单中退出全部 Chrome 和 Edge。只关标签页不够。'
print '此脚本不会替你关闭浏览器，不会重装、删除身份或清除采集记录。'
print ''

[[ -d "$SUPPORT" && ! -L "$SUPPORT" && "${SUPPORT:A}" == "$SUPPORT" ]] || finish 1 '没有找到可核对的原更新助手。请保留安装，联系邀请人。'
owned_file "$HELPER" && [[ -x "$HELPER" ]] || finish 1 '原更新助手缺失或路径不匹配，请联系邀请人；本次没有更新。'
CHECKSUM="$(/usr/bin/shasum -a 256 "$HELPER" 2>/dev/null)" || finish 1 '无法核验原更新助手，本次没有更新。'
[[ "${CHECKSUM%% *}" == "$EXPECTED" ]] || finish 1 '原更新助手与本次已审版本不匹配。本次没有运行，请联系邀请人。'
owned_file "$CONFIG" || finish 1 '无法安全读取原安装配置。本次没有运行，请联系邀请人。'
if [[ -e "$STATE" || -L "$STATE" ]]; then
  owned_file "$STATE" || finish 1 '原更新状态文件无法安全核对。本次没有运行，请联系邀请人。'
fi
DIRECTORY="$(field "$CONFIG" directory)" || finish 1 '原安装目录未配置，请联系邀请人；不要重新报名。'
[[ "$DIRECTORY" == /* && -d "$DIRECTORY" && ! -L "$DIRECTORY" && "${DIRECTORY:A}" == "$DIRECTORY" ]] || finish 1 '原安装目录无法核对。本次没有运行，请联系邀请人。'
MANIFEST="$DIRECTORY/manifest.json"
owned_file "$MANIFEST" || finish 1 '原插件文件无法安全核对。本次没有运行，请联系邀请人。'
"$HELPER" --check-install "$DIRECTORY" >/dev/null 2>&1 || finish 1 '原插件与标准参与者更新不兼容。本次没有更新，原安装保留。'
SCHEDULED="$(field "$CONFIG" scheduled_enabled)" || finish 1 '更新偏好无法读取，本次没有运行。'
[[ "$SCHEDULED" == 'true' ]] || finish 2 '你已关闭自动更新。此脚本会保留该选择；如需更新，请先在原插件开启“自动安装已验证的插件更新”，再退出浏览器后运行。'

/usr/bin/pgrep -u "$(/usr/bin/id -u)" -f 'Google Chrome|Microsoft Edge' >/dev/null 2>&1
BROWSER_RESULT=$?
case "$BROWSER_RESULT" in
  0) finish 2 'Chrome 或 Edge 仍在运行。本次没有调用更新。请本人在浏览器菜单选择“退出”，再双击本文件。' ;;
  1) ;;
  *) finish 1 '无法确认浏览器已经退出，本次没有调用更新。请联系邀请人。' ;;
esac

print '浏览器已退出，正在由原助手检查签名并下载更新；可能需要约两分钟……'
POLL_OUTPUT="$("$HELPER" --poll 2>&1)"
POLL_RESULT=$?
if [[ "$POLL_RESULT" -ne 0 ]]; then
  case "$POLL_OUTPUT" in
    busy) finish 2 '另一轮更新正在进行，本次未确认完成。稍等后重试，不要重新安装。' ;;
    invalid_signature|hash_mismatch|permission_change|replayed_release|wrong_extension|invalid_manifest|invalid_url)
      finish 1 '更新验证未通过，尚未确认升级。请把此提示交给邀请人；不要手动覆盖插件。' ;;
    recovery_required) finish 2 '原更新仍需核对恢复状态。请保留原安装并联系邀请人，不要重新安装。' ;;
    *) finish 1 '更新助手未能完成检查或下载；尚未确认升级。请确认网络可访问原下载地址后重试；仍失败请联系邀请人。此结果也可能来自本地文件或权限问题。' ;;
  esac
fi

owned_file "$STATE" || finish 1 '更新助手已返回，但暂时无法核验结果。请保留原安装并联系邀请人。'
VERSION="$(field "$MANIFEST" version)" || finish 1 '暂时无法读取更新后的插件版本，尚未确认升级。'
PENDING="$(field "$STATE" pending || true)"
LOADED="$(field "$STATE" loaded_version || true)"
STATUS="$(field "$STATE" status || true)"
POLL_STATUS="$(field "$STATE" poll_status || true)"
if [[ "$VERSION" == "$TARGET" && "$PENDING" == "$TARGET" && "$STATUS" == 'pending_reload' ]]; then
  finish 0 '4.2.65 插件文件已就绪。现在请重新打开原来的 Chrome，点右上角拼图 → 众包公开笔记采集，等待版本显示4.2.65。浏览器加载确认尚未完成；原两条已回传后应显示等待实验启动。'
elif [[ "$VERSION" == "$TARGET" && -z "$PENDING" && "$LOADED" == "$TARGET" && "$STATUS" == 'applied' ]]; then
  finish 0 '原助手记录4.2.65已经完成加载确认。请打开原来的Chrome继续查看；本次没有新建身份或任务。'
elif [[ "$POLL_STATUS" == 'downloaded' ]]; then
  finish 2 '更新仅已下载，还没有替换。可能有Chrome或Edge在检查期间重新打开；请完全退出后重试。'
elif [[ -n "$PENDING" ]]; then
  finish 2 '原助手还有一轮更新等待浏览器确认。请先打开原Chrome等待其加载完成，再按需要退出后运行；不要重装。'
elif [[ "$VERSION" == "$TARGET" ]]; then
  finish 2 '4.2.65 文件已经存在，但原助手尚无浏览器加载确认。请打开原Chrome查看插件版本；仍异常时联系邀请人，不要重新安装。'
elif [[ "$POLL_STATUS" == 'current' ]]; then
  finish 2 '当前通道未使原安装达到本次4.2.65，尚未确认本次更新。请联系邀请人核对发布状态。'
else
  finish 1 '更新结果尚未达到本次4.2.65的可确认状态。请保留原安装并联系邀请人。'
fi
