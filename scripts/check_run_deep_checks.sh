#!/bin/sh
# Checks the background glue in scripts/run_deep_checks.sh with stub checks, as CI never sees a real maths failure (#46).
. scripts/run_deep_checks.sh
failed=0
log=$(mktemp "${TMPDIR:-/tmp}/deep-glue.XXXXXX") || exit 1
trap 'rm -f "$log"' EXIT
checkFridge() { :; }
deepMaths() { echo "maths stub exits $stubStatus"; return "$stubStatus"; }
# With stubWaits=1 the explorer stub waits up to 5 s for a maths line, which only streamed output delivers before the wait.
deepExplorer() {
	[ "$stubWaits" = 1 ] || return 0
	i=0
	while [ "$i" -lt 50 ]; do
		grep -qF '[maths] maths stub' "$log" && return 0
		sleep 0.1
		i=$((i + 1))
	done
	return 1
}

# Prints the glue's output and verdict with a maths stub that exits $1.
glue() {
	(
		stubStatus=$1 fail=0
		err() { echo "FAIL: $*"; fail=1; }
		runDeepChecks
		echo "fail=$fail"
	) >"$log" 2>&1
	cat "$log"
}
# Fails when the output $2 of case $1 lacks $3.
expect() {
	case $2 in
	*"$3"*) ;;
	*) printf 'FAIL: %s: no "%s" in\n%s\n' "$1" "$3" "$2" >&2; failed=1 ;;
	esac
}

out=$(glue 1)
expect "a failing maths stub" "$out" "[maths] maths stub exits 1"
expect "a failing maths stub" "$out" "FAIL: deep nested LSH maths check failed"
expect "a failing maths stub" "$out" "fail=1"
out=$(glue 0)
expect "a passing maths stub" "$out" "fail=0"
out=$(stubWaits=1; glue 0)
expect "maths output streaming before the wait" "$out" "fail=0"
exit "$failed"
