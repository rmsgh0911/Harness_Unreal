#!/usr/bin/env sh
set -u

script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

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

if [ "${1:-}" = "bootstrap" ]; then
    shift
    exec sh "$script_dir/bootstrap.sh" "$@"
fi

cli_path="$script_dir/scripts/tools/harness_cli.py"
version_probe='import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 3)'

if [ -n "${HARNESS_PYTHON:-}" ]; then
    if ! command -v "$HARNESS_PYTHON" >/dev/null 2>&1 && [ ! -x "$HARNESS_PYTHON" ]; then
        echo "HARNESS_PYTHON does not resolve to an executable. Set it to Python 3.10+." >&2
        exit 2
    fi
    if ! "$HARNESS_PYTHON" -c "$version_probe" >/dev/null 2>&1; then
        echo "HARNESS_PYTHON is not Python 3.10+ or could not be started. No fallback was attempted." >&2
        exit 2
    fi
    exec "$HARNESS_PYTHON" -X utf8 -B "$cli_path" "$@"
fi

if [ -n "${HARNESS_RUNTIME_ROOT:-}" ]; then
    case "$HARNESS_RUNTIME_ROOT" in
        /*) runtime_root=$HARNESS_RUNTIME_ROOT ;;
        *) runtime_root=$script_dir/$HARNESS_RUNTIME_ROOT ;;
    esac
else
    runtime_os=$(uname -s 2>/dev/null | tr '[:upper:]' '[:lower:]') || runtime_os="unknown"
    runtime_arch=$(uname -m 2>/dev/null) || runtime_arch="unknown"
    case "$runtime_arch" in
        x86_64|amd64) runtime_arch="x86_64" ;;
        arm64|aarch64) runtime_arch="aarch64" ;;
    esac
    runtime_root=$script_dir/.runtime/$runtime_os-$runtime_arch
fi
if [ -L "$runtime_root" ]; then
    echo "HARNESS_RUNTIME_ROOT cannot be a symlink." >&2
    exit 2
fi
if [ -d "$runtime_root" ]; then
    runtime_root=$(canonical_directory "$runtime_root") || {
        echo "HARNESS_RUNTIME_ROOT could not be resolved." >&2
        exit 2
    }
fi
if [ "$runtime_root" = "/" ]; then
    echo "HARNESS_RUNTIME_ROOT cannot be the filesystem root." >&2
    exit 2
fi
managed_marker=$runtime_root/python.path
failed=""
if [ -f "$managed_marker" ]; then
    managed_python_raw=$(tr -d '\r\n' < "$managed_marker")
    if managed_python=$(canonical_regular_file "$managed_python_raw"); then
        case "$managed_python" in
            "$runtime_root"/*)
                if [ -x "$managed_python" ] && "$managed_python" -c "$version_probe" >/dev/null 2>&1; then
                    exec "$managed_python" -X utf8 -B "$cli_path" "$@"
                fi
                failed="$failed managed-runtime"
                ;;
        esac
    else
        failed="$failed managed-runtime"
    fi
fi

for candidate in python3 python; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
        continue
    fi
    if "$candidate" -c "$version_probe" >/dev/null 2>&1; then
        exec "$candidate" -X utf8 -B "$cli_path" "$@"
    fi
    failed="$failed $candidate"
done

echo "Python 3.10+ was not found. Run 'sh Harness/harness.sh bootstrap', install Python, or set HARNESS_PYTHON to its executable path.${failed:+ Failed candidates:$failed.}" >&2
exit 2
