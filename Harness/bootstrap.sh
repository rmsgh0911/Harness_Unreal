#!/usr/bin/env sh
set -u

uv_version="0.12.18"
python_request="3.12"
uv_installer_url="https://releases.astral.sh/github/uv/releases/download/$uv_version/uv-installer.sh"
uv_installer_sha256="e62a5ea089de9c6a9b1f767166c9f33194e18d350e9f375c6355fac3ba0fb42b"
version_probe='import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 3)'
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

usage() {
    cat <<'EOF'
Harness Python Bootstrap
Usage: sh Harness/harness.sh bootstrap [--status]

Without --status, this explicitly downloads a pinned, checksum-verified uv
installer when uv is unavailable, then installs a platform-local managed
Python 3.12 runtime. It does not modify PATH or shell profiles.

Environment overrides:
  HARNESS_UV            Existing uv 0.12.18 executable for offline/mirrored setup.
  HARNESS_RUNTIME_ROOT  Platform-specific managed-runtime directory.
  HARNESS_UV_CACHE_DIR  Optional preseeded uv cache directory.

Normal Harness commands never trigger this network bootstrap implicitly.
EOF
}

fail() {
    echo "Harness bootstrap failed: $*" >&2
    exit 2
}

canonical_directory() {
    CDPATH='' cd -- "$1" 2>/dev/null && pwd -P
}

canonical_regular_file() {
    target=$1
    [ -f "$target" ] && [ ! -L "$target" ] || return 1
    target_parent=$(dirname -- "$target")
    target_name=$(basename -- "$target")
    target_parent=$(canonical_directory "$target_parent") || return 1
    printf '%s/%s\n' "$target_parent" "$target_name"
}

platform_key() {
    os=$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]') || os="unknown"
    arch=$(uname -m 2>/dev/null) || arch="unknown"
    case "$arch" in
        x86_64|amd64) arch="x86_64" ;;
        arm64|aarch64) arch="aarch64" ;;
    esac
    printf '%s-%s\n' "$os" "$arch"
}

mode="install"
for argument in "$@"; do
    case "$argument" in
        --status) mode="status" ;;
        --help|-h) usage; exit 0 ;;
        *) fail "unknown bootstrap option: $argument" ;;
    esac
done

if [ -n "${HARNESS_RUNTIME_ROOT:-}" ]; then
    case "$HARNESS_RUNTIME_ROOT" in
        /*) runtime_candidate=$HARNESS_RUNTIME_ROOT ;;
        *) runtime_candidate=$script_dir/$HARNESS_RUNTIME_ROOT ;;
    esac
else
    runtime_candidate=$script_dir/.runtime/$(platform_key)
fi
[ ! -L "$runtime_candidate" ] || fail "HARNESS_RUNTIME_ROOT cannot be a symlink"
if [ ! -d "$runtime_candidate" ]; then
    case "$runtime_candidate" in
        */../*|*/..) fail "an unresolved HARNESS_RUNTIME_ROOT cannot contain '..' path segments" ;;
    esac
fi

runtime_parent=$(dirname -- "$runtime_candidate")
runtime_name=$(basename -- "$runtime_candidate")
if [ -d "$runtime_candidate" ]; then
    runtime_root=$(canonical_directory "$runtime_candidate") || fail "cannot resolve runtime root"
else
    runtime_parent=$(canonical_directory "$runtime_parent") || runtime_parent=""
    if [ -n "$runtime_parent" ]; then
        runtime_root=$runtime_parent/$runtime_name
    else
        runtime_root=$runtime_candidate
    fi
fi
[ "$runtime_root" != "/" ] || fail "HARNESS_RUNTIME_ROOT cannot be the filesystem root"

marker_path=$runtime_root/python.path
installer_tmp=""
marker_tmp=""
cleanup() {
    [ -z "$installer_tmp" ] || rm -f -- "$installer_tmp"
    [ -z "$marker_tmp" ] || rm -f -- "$marker_tmp"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

test_python() {
    candidate=$1
    [ -x "$candidate" ] && "$candidate" -c "$version_probe" >/dev/null 2>&1
}

managed_python() {
    [ -f "$marker_path" ] || return 1
    candidate_raw=$(tr -d '\r\n' < "$marker_path")
    candidate=$(canonical_regular_file "$candidate_raw") || return 1
    case "$candidate" in
        "$runtime_root"/*) ;;
        *) return 1 ;;
    esac
    test_python "$candidate" || return 1
    printf '%s\n' "$candidate"
}

if [ "$mode" = "status" ]; then
    if python_path=$(managed_python); then
        echo "Harness managed Python is ready."
        echo "- Runtime root: $runtime_root"
        echo "- Python: $python_path"
        "$python_path" --version
        exit $?
    fi
    echo "Harness managed Python is not ready. Run: sh Harness/harness.sh bootstrap"
    exit 1
fi
if python_path=$(managed_python); then
    echo "Harness managed Python is already ready."
    echo "- Runtime root: $runtime_root"
    echo "- Python: $python_path"
    "$python_path" --version
    exit $?
fi

umask 077
mkdir -p -- "$runtime_root" || fail "cannot create the managed runtime root"
runtime_root=$(canonical_directory "$runtime_root") || fail "cannot resolve the managed runtime root"
[ "$runtime_root" != "/" ] || fail "HARNESS_RUNTIME_ROOT cannot resolve to the filesystem root"
marker_path=$runtime_root/python.path
bin_dir=$runtime_root/bin
python_dir=$runtime_root/python
if [ -n "${HARNESS_UV_CACHE_DIR:-}" ]; then
    cache_dir=$HARNESS_UV_CACHE_DIR
elif [ -n "${UV_CACHE_DIR:-}" ]; then
    cache_dir=$UV_CACHE_DIR
else
    cache_dir=$runtime_root/cache
fi
mkdir -p -- "$bin_dir" "$python_dir" "$cache_dir" || fail "cannot create managed runtime directories"

uv_supported() {
    uv_output=$("$1" --version 2>/dev/null) || return 1
    case "$uv_output" in
        "uv $uv_version"|"uv $uv_version "*) return 0 ;;
        *) return 1 ;;
    esac
}

resolve_uv() {
    if [ -x "$bin_dir/uv" ] && uv_supported "$bin_dir/uv"; then
        printf '%s\n' "$bin_dir/uv"
        return 0
    fi
    return 1
}

sha256_file() {
    target=$1
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$target" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$target" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 "$target" | awk '{print $NF}'
    else
        fail "sha256sum, shasum, or openssl is required to verify the uv installer"
    fi
}

install_uv() {
    installer_tmp=$(mktemp "$runtime_root/.uv-installer.XXXXXX") || fail "cannot create a private installer file"
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -fLsS "$uv_installer_url" -o "$installer_tmp" || fail "could not download the pinned uv installer"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$uv_installer_url" -O "$installer_tmp" || fail "could not download the pinned uv installer"
    else
        fail "curl or wget is required; provide an existing executable through HARNESS_UV for offline setup"
    fi
    actual_hash=$(sha256_file "$installer_tmp")
    [ "$actual_hash" = "$uv_installer_sha256" ] || fail "uv installer checksum mismatch; expected $uv_installer_sha256 but received $actual_hash"
    UV_UNMANAGED_INSTALL="$bin_dir" UV_NO_MODIFY_PATH=1 sh "$installer_tmp" >&2 || fail "uv installer failed"
    [ -x "$bin_dir/uv" ] || fail "uv installer completed without creating $bin_dir/uv"
    uv_supported "$bin_dir/uv" || fail "the installed uv is not the pinned $uv_version release"
}

if [ -n "${HARNESS_UV:-}" ]; then
    if [ -x "$HARNESS_UV" ]; then
        uv_path=$HARNESS_UV
    elif command -v "$HARNESS_UV" >/dev/null 2>&1; then
        uv_path=$(command -v "$HARNESS_UV")
    else
        fail "HARNESS_UV does not resolve to an executable; no network fallback was attempted"
    fi
    uv_supported "$uv_path" || fail "HARNESS_UV must provide the pinned uv $uv_version release; no network fallback was attempted"
elif uv_path=$(resolve_uv); then
    :
else
    install_uv
    uv_path=$bin_dir/uv
fi

UV_PYTHON_INSTALL_DIR="$python_dir" \
UV_CACHE_DIR="$cache_dir" \
UV_PYTHON_INSTALL_BIN=0 \
UV_PYTHON_INSTALL_REGISTRY=0 \
UV_NO_CONFIG=1 \
UV_NO_PROJECT=1 \
UV_MANAGED_PYTHON=1 \
UV_NO_PROGRESS=1 \
"$uv_path" python install "$python_request" || fail "uv could not install managed Python $python_request"

python_output=$(UV_PYTHON_INSTALL_DIR="$python_dir" \
    UV_CACHE_DIR="$cache_dir" \
    UV_PYTHON_INSTALL_BIN=0 \
    UV_PYTHON_INSTALL_REGISTRY=0 \
    UV_NO_CONFIG=1 \
    UV_NO_PROJECT=1 \
    UV_MANAGED_PYTHON=1 \
    UV_NO_PROGRESS=1 \
    "$uv_path" python find "$python_request") || fail "uv installed Python but could not locate its executable"
python_path=$(printf '%s\n' "$python_output" | tail -n 1 | tr -d '\r')
python_path=$(canonical_regular_file "$python_path") || fail "uv returned a missing or symlinked Python executable"
python_dir=$(canonical_directory "$python_dir") || fail "cannot resolve the managed Python directory"
case "$python_path" in
    "$python_dir"/*) ;;
    *) fail "uv returned a Python executable outside the managed runtime: $python_path" ;;
esac
test_python "$python_path" || fail "the managed Python executable is missing, older than 3.10, or could not start"

marker_tmp=$(mktemp "$runtime_root/.python-path.XXXXXX") || fail "cannot create a private marker file"
printf '%s\n' "$python_path" > "$marker_tmp" || fail "could not write the managed Python marker"
mv -f -- "$marker_tmp" "$marker_path" || fail "could not publish the managed Python marker"
marker_tmp=""

echo "Harness managed Python is ready."
echo "- Runtime root: $runtime_root"
echo "- Python: $python_path"
echo "- uv: $uv_path"
"$python_path" --version
