#!/bin/sh
# Public, fixed Astral resources only. No Git, Python prerequisite, CLT or profiles.
set -eu
umask 077
fail() { printf '%s\n' "$1" >&2; exit 2; }
HELPER=''; CHECK=false; OUTPUT=record; CACHE=''; FRESH=false; RETRY=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --help) printf '%s\n' 'bootstrap-pro-tools.command --helper-root ABS [--check] [--python-path]' 'Only private official uv/Python tools; no SDK, login, browser or collection.'; exit 0 ;;
    --helper-root) [ "$#" -ge 2 ] || fail bootstrap_arguments_invalid; HELPER=$2; shift ;;
    --bootstrap-cache) [ "$#" -ge 2 ] || fail bootstrap_arguments_invalid; CACHE=$2; shift ;;
    --check) CHECK=true ;;
    --python-path) OUTPUT=python ;;
    *) fail bootstrap_arguments_invalid ;;
  esac
  shift
done
case "$HELPER" in /*) ;; *) fail bootstrap_helper_invalid ;; esac
case "$HELPER" in *'
'*|*''*) fail bootstrap_helper_invalid ;; esac
[ ! -L "$HELPER" ] || fail bootstrap_helper_invalid
if [ -e "$HELPER" ]; then
  [ -d "$HELPER" ] && [ "$(/usr/bin/stat -f '%u:%Lp' "$HELPER")" = "$(/usr/bin/id -u):700" ] || fail bootstrap_helper_invalid
  [ "$(CDPATH= cd -- "$HELPER" && /bin/pwd -P)" = "$HELPER" ] || fail bootstrap_helper_invalid
fi
BOOT="$HELPER/bootstrap-tools"; RECORD="$BOOT/TOOLS.json"
retryable_download() {
  [ -f "$BOOT/DOWNLOAD-FAILED.json" ] && [ ! -L "$BOOT/DOWNLOAD-FAILED.json" ] &&
  [ "$(/usr/bin/stat -f '%u:%Lp:%l' "$BOOT/DOWNLOAD-FAILED.json")" = "$(/usr/bin/id -u):600:1" ] &&
  [ "$(/bin/cat "$BOOT/DOWNLOAD-FAILED.json")" = '{"state":"public_download_failed"}' ] &&
  [ ! -e "$BOOT/python" ] && [ ! -L "$BOOT/python" ]
}
[ ! -L "$BOOT" ] || fail bootstrap_directory_invalid
if [ -e "$BOOT" ]; then
  [ -d "$BOOT" ] && [ "$(/usr/bin/stat -f '%u:%Lp' "$BOOT")" = "$(/usr/bin/id -u):700" ] || fail bootstrap_directory_invalid
  if [ ! -e "$RECORD" ] && [ ! -e "$BOOT/INTENT.json" ]; then fail bootstrap_attempt_unknown; fi
  if [ ! -e "$RECORD" ] && [ -e "$BOOT/INTENT.json" ]; then
    if retryable_download; then RETRY=true; else fail bootstrap_attempt_unknown; fi
  fi
fi
if [ "$CHECK" = true ] && [ ! -f "$RECORD" ]; then fail bootstrap_tools_missing; fi
[ "$(/usr/bin/uname -s)" = Darwin ] || fail bootstrap_macos_required
case "$(/usr/bin/uname -m)" in
  arm64) ARCH=arm64; PYARCH=aarch64; TARGET=aarch64-apple-darwin
    UVPIN=127ebdda7ad953cdf198e964b570ea5771b85467ea93eb7cb6d6f8e6f55408f3
    PROPIN=a84adc050a29e0c7387c885ff13e6ac4b0027f9e841359e200d647313dbb5b03
    SIGNPIN=8b0f1fa71eab7ca644e482c631807a1116fa848491051cd1c8d9429491de63a6 ;;
  x86_64) ARCH=x64; PYARCH=x86_64; TARGET=x86_64-apple-darwin
    UVPIN=06b8ae1da8c2661c5434507a66f8c2b0b835933bf955b5958a9ac357a37d1959
    PROPIN=77bfa2b959edc0d653830f14f08ab8260156d4b5930368886d4e1c6a76f1d2d4
    SIGNPIN=bd486eadd20259ad1fece28c800205baac0113c3b9cc663ddae495c19ba9db38 ;;
  *) fail bootstrap_architecture_unsupported ;;
esac
UVARCH="$BOOT/archives/uv-$TARGET.tar.gz"
PROARCH="$BOOT/archives/20260825/cpython-3.11.16+20260825-$PYARCH-apple-darwin-install_only_stripped.tar.gz"
SIGNARCH="$BOOT/archives/20260825/cpython-3.12.14+20260825-$PYARCH-apple-darwin-install_only_stripped.tar.gz"
UV="$BOOT/uv-0.12.7-$TARGET"
PRO="$BOOT/python/cpython-3.11.16-macos-$PYARCH-none/bin/python3.11"
SIGN="$BOOT/python/cpython-3.12.14-macos-$PYARCH-none/bin/python3.12"
regular() {
  [ -f "$1" ] && [ ! -L "$1" ] && [ "$(/usr/bin/stat -f '%u:%l' "$1")" = "$(/usr/bin/id -u):1" ] || fail bootstrap_resource_invalid
  permissions=$(/usr/bin/stat -f '%Lp' "$1")
  [ "$((0$permissions & 022))" -eq 0 ] || fail bootstrap_resource_permissions
}
hashcheck() {
  regular "$1"
  [ "$(/usr/bin/shasum -a 256 "$1" | /usr/bin/awk '{print $1}')" = "$2" ] || fail bootstrap_archive_changed
}
LOCKED=false; SCRATCH=''; TIMER=''; WORKER=''
cleanup() {
  [ -z "$WORKER" ] || /bin/kill -TERM "$WORKER" 2>/dev/null || true
  [ -z "$TIMER" ] || /bin/kill "$TIMER" 2>/dev/null || true
  [ -z "$SCRATCH" ] || /bin/rm -rf -- "$SCRATCH"
  if [ "$LOCKED" = true ]; then /bin/rmdir "$BOOT/.lock" 2>/dev/null || true; fi
}
trap cleanup EXIT
trap 'exit 2' HUP INT TERM
fetch() {
  dest=$1; pin=$2; url=$3
  if [ -e "$dest" ] || [ -L "$dest" ]; then hashcheck "$dest" "$pin"; return; fi
  if [ -n "$CACHE" ]; then
    case "$CACHE" in /*) ;; *) fail bootstrap_cache_invalid ;; esac
    relative=${dest#"$BOOT/archives/"}
    hashcheck "$CACHE/$relative" "$pin"
    /bin/cp "$CACHE/$relative" "$dest"; /bin/chmod 600 "$dest"; hashcheck "$dest" "$pin"; return
  fi
  tmp=$(/usr/bin/mktemp "$BOOT/.download-XXXXXX")
  # curl limits actual transfer bytes, redirects, connection and total duration.
  /usr/bin/curl --fail --silent --show-error --proto '=https' --proto-redir '=https' --location --max-redirs 5 --connect-timeout 15 --max-time 180 --max-filesize 104857600 "$url" -o "$tmp" 2>/dev/null & WORKER=$!
  if ! wait "$WORKER"; then
    WORKER=''
    /bin/rm -f "$tmp"
    (set -C; printf '%s\n' '{"state":"public_download_failed"}' > "$BOOT/DOWNLOAD-FAILED.json") || fail bootstrap_attempt_unknown
    /bin/sync; fail bootstrap_public_download_failed
  fi
  WORKER=''
  [ "$(/usr/bin/stat -f '%z' "$tmp")" -le 104857600 ] || fail bootstrap_archive_too_large
  hashcheck "$tmp" "$pin"; /bin/mv "$tmp" "$dest"
}
if [ ! -f "$RECORD" ]; then
  [ "$CHECK" = false ] || fail bootstrap_tools_missing
  [ ! -e "$RECORD" ] && [ ! -L "$RECORD" ] || fail bootstrap_record_invalid
  /bin/mkdir -p "$HELPER"
  [ "$(CDPATH= cd -- "$HELPER" && /bin/pwd -P)" = "$HELPER" ] || fail bootstrap_helper_invalid
  [ "$(/usr/bin/stat -f '%u:%Lp' "$HELPER")" = "$(/usr/bin/id -u):700" ] || fail bootstrap_helper_invalid
  if [ ! -d "$BOOT" ]; then /bin/mkdir "$BOOT"; fi
  /bin/mkdir "$BOOT/.lock" 2>/dev/null || fail bootstrap_busy
  LOCKED=true
  # Recheck after acquiring lock. Incomplete original intents are never replayed.
  if [ "$RETRY" = true ]; then
    retryable_download || fail bootstrap_attempt_unknown
    /bin/mv "$BOOT/DOWNLOAD-FAILED.json" "$BOOT/DOWNLOAD-FAILED-$$.json"
    (set -C; printf '{"schema":"crowd-pro-bootstrap-retry-v1","arch":"%s"}\n' "$ARCH" > "$BOOT/RETRY-$$.json") || fail bootstrap_attempt_unknown
  else
    [ ! -e "$BOOT/INTENT.json" ] && [ ! -L "$BOOT/INTENT.json" ] || fail bootstrap_attempt_unknown
    (set -C; printf '{"schema":"crowd-pro-bootstrap-intent-v1","arch":"%s"}\n' "$ARCH" > "$BOOT/INTENT.json") || fail bootstrap_attempt_unknown
  fi
  /bin/sync
  [ ! -e "$BOOT/python" ] && [ ! -L "$BOOT/python" ] || fail bootstrap_attempt_unknown
  for dir in "$BOOT/archives" "$BOOT/archives/20260825"; do
    if [ ! -e "$dir" ] && [ ! -L "$dir" ]; then /bin/mkdir "$dir"; fi
    [ -d "$dir" ] && [ ! -L "$dir" ] && [ "$(/usr/bin/stat -f '%u:%Lp' "$dir")" = "$(/usr/bin/id -u):700" ] || fail bootstrap_directory_invalid
  done
  fetch "$UVARCH" "$UVPIN" "https://releases.astral.sh/github/uv/releases/download/0.12.7/uv-$TARGET.tar.gz"
  fetch "$PROARCH" "$PROPIN" "https://releases.astral.sh/github/python-build-standalone/releases/download/20260825/$(/usr/bin/basename "$PROARCH")"
  fetch "$SIGNARCH" "$SIGNPIN" "https://releases.astral.sh/github/python-build-standalone/releases/download/20260825/$(/usr/bin/basename "$SIGNARCH")"
  /usr/bin/tar -xOzf "$UVARCH" "uv-$TARGET/uv" > "$UV"
  /bin/chmod 700 "$UV"
  /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin UV_KEYRING_PROVIDER=disabled UV_PYTHON_DOWNLOADS=automatic UV_PYTHON_INSTALL_DIR="$BOOT/python" UV_PYTHON_INSTALL_MIRROR="file://$BOOT/archives" "$UV" --no-config python install --no-bin 3.11.16 3.12.14 >/dev/null 2>&1 &
  WORKER=$!
  (remaining=180; while [ "$remaining" -gt 0 ]; do /bin/sleep 1; remaining=$((remaining-1)); done; /bin/kill -TERM "$WORKER" 2>/dev/null) & TIMER=$!
  if ! wait "$WORKER"; then fail bootstrap_python_prepare_failed; fi
  WORKER=''
  /bin/kill "$TIMER" 2>/dev/null || true; wait "$TIMER" 2>/dev/null || true; TIMER=''
  FRESH=true
fi
# Revalidate fixed official archives, not a caller supplied executable/hash pair.
hashcheck "$UVARCH" "$UVPIN"; hashcheck "$PROARCH" "$PROPIN"; hashcheck "$SIGNARCH" "$SIGNPIN"
regular "$UV"; regular "$PRO"; regular "$SIGN"
SCRATCH=$(/usr/bin/mktemp -d "$BOOT/.verify-XXXXXX")
/usr/bin/tar -xOzf "$UVARCH" "uv-$TARGET/uv" > "$SCRATCH/uv"
/usr/bin/cmp -s "$SCRATCH/uv" "$UV" || fail bootstrap_uv_changed
# Match interpreter bytes; uv legitimately relocates dylib/sysconfig library files.
# Official 0.12.7: crates/uv-python/src/managed.rs ensure_{sysconfig,dylib}_patched.
for role in pro signer; do
  if [ "$role" = pro ]; then archive=$PROARCH; python=$PRO; minor=3.11; else archive=$SIGNARCH; python=$SIGN; minor=3.12; fi
  /bin/mkdir "$SCRATCH/$role"
  /usr/bin/tar -xzf "$archive" -C "$SCRATCH/$role"
  trusted="$SCRATCH/$role/python"; installed="${python%/bin/*}"
  [ "$(CDPATH= cd -- "$installed" && /bin/pwd -P)" = "$installed" ] || fail bootstrap_python_path_changed
  /usr/bin/cmp -s "$trusted/bin/python$minor" "$python" || fail bootstrap_python_changed
done
# Use the pristine fixed archive interpreter to verify all installed bytes first.
# Receipts are local trust state created only after native uv completes in an empty
# private target. They are not an external tool/hash input or remote RPC capability.
"$SCRATCH/signer/python/bin/python3.12" -I -B - "$RECORD" "$ARCH" "$UV" "$PRO" "$SIGN" "$CHECK" "$OUTPUT" "$FRESH" "$UVPIN" "$PROPIN" "$SIGNPIN" <<'PY'
import hashlib,json,os,pathlib,stat,subprocess,sys,tempfile
record=pathlib.Path(sys.argv[1]); arch=sys.argv[2]
def secure(path):
 s=path.lstat()
 if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1:raise ValueError('bootstrap_receipt_invalid')
 return path.read_bytes()
def once(path,raw):
 fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
def tree(root):
 s=root.lstat()
 if not stat.S_ISDIR(s.st_mode) or root.resolve()!=root or s.st_uid!=os.getuid() or s.st_mode&0o077:raise ValueError('bootstrap_python_root_invalid')
 rows={}
 for p in sorted(root.rglob('*')):
  s=p.lstat(); name=p.relative_to(root).as_posix()
  if s.st_uid!=os.getuid():raise ValueError('bootstrap_tree_owner_changed')
  if p.is_symlink():
   p.resolve(strict=True).relative_to(root)
   rows[name]={'symlink':os.readlink(p)}
  elif stat.S_ISDIR(s.st_mode):
   if s.st_mode&0o022:raise ValueError('bootstrap_tree_permissions_changed')
   rows[name]={'directory':True,'mode':stat.S_IMODE(s.st_mode)}
  elif stat.S_ISREG(s.st_mode) and s.st_nlink==1 and not s.st_mode&0o022:
   rows[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(s.st_mode)}
  else:raise ValueError('bootstrap_tree_invalid')
 return {'path':str(root),'files':rows}
proof={'schema':'crowd-pro-bootstrap-proof-v1','arch':arch,'archives':dict(zip(('uv','pro','signer'),sys.argv[9:12])),
       'trees':{role:tree(pathlib.Path(path).parent.parent) for role,path in [('pro',sys.argv[4]),('signer',sys.argv[5])]}}
proof_raw=(json.dumps(proof,sort_keys=True,separators=(',',':'))+'\n').encode()
proof_path=record.parent/'PROOF.json'
if sys.argv[8]=='true':once(proof_path,proof_raw)
elif secure(proof_path)!=proof_raw:raise ValueError('bootstrap_python_tree_changed')
def tool(path,version):
 p=pathlib.Path(path).resolve(strict=True)
 if '\n' in str(p) or '\r' in str(p):raise ValueError('bootstrap_path_invalid')
 return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'version':version}
value={'schema':'crowd-pro-bootstrap-tools-v1','arch':arch,'uv':tool(sys.argv[3],'0.12.7'),'pro_python':tool(sys.argv[4],'3.11.16'),'signer_python':tool(sys.argv[5],'3.12.14')}
for key,version in [('uv','uv 0.12.7'),('pro_python','Python 3.11.16'),('signer_python','Python 3.12.14')]:
 argv=[value[key]['path'],'--version']
 actual=subprocess.run(argv,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15).stdout.decode().strip()
 if actual!=version and not (key=='uv' and actual.startswith(version+' (') and actual.endswith(')')):raise ValueError('bootstrap_version_changed')
raw=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
if record.exists() or record.is_symlink():
 if secure(record)!=raw:raise ValueError('bootstrap_record_changed')
else:
 if sys.argv[6]=='true':raise ValueError('bootstrap_tools_missing')
 once(record,raw)
print(value['signer_python']['path'] if sys.argv[7]=='python' else record)
PY
