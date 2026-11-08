#!/bin/sh
# Bootstrap the Python policy handlers without depending on a python3 alias.
fail() {
    printf '%s\n' "AGENTIC POSIX hook: $*" >&2
    exit 2
}

[ "$#" -gt 0 ] || fail 'Missing policy handler; reinstall the project-local kit.'
handler=$1
shift
case "$handler" in
    */lifecycle.py|*/shell_guard.py|*/review_native.py|*/autonomy_hook.py) ;;
    *) fail 'Unknown policy handler; reinstall the project-local kit.' ;;
esac
[ -f "$handler" ] || fail "Missing $handler; reinstall the project-local kit."

try_python() {
    candidate=$1
    shift
    if [ -f "$candidate" ] && [ -x "$candidate" ] &&
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 9))' </dev/null >/dev/null 2>&1; then
        exec "$candidate" "$handler" "$@"
        # Some shells return from a failed exec. Never retry handler dispatch.
        exit 2
    fi
}

for name in python3 python; do
    remaining=${PATH-}
    while :; do
        directory=${remaining%%:*}
        # Empty PATH entries denote the current working directory.
        try_python "${directory:-.}/$name" "$@"
        case "$remaining" in
            *:*) remaining=${remaining#*:} ;;
            *) break ;;
        esac
    done
done

try_python /usr/local/bin/python3 "$@"
try_python /usr/bin/python3 "$@"
if [ -n "${HOME-}" ]; then
    try_python "$HOME/.local/bin/python3" "$@"
fi
fail 'Python 3.9+ is required. Install it, add its directory to PATH, and restart your agent application.'
