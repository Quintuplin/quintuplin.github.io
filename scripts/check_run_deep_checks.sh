#!/bin/sh
# Checks the background glue in scripts/run_deep_checks.sh with stub checks, as CI never sees a real maths failure (#46).
. scripts/run_deep_checks.sh
failed=0
log=$(mktemp "${TMPDIR:-/tmp}/deep-glue.XXXXXX") || exit 1
seen="$log.seen"
trap 'rm -f "$log" "$seen"' EXIT
checkFridge() { :; }
# Runs the command $@ every 0.1 s until it succeeds, for up to 2 s.
waitFor() {
	i=0
	until "$@"; do
		[ "$i" -lt 20 ] || return 1
		sleep 0.1
		i=$((i + 1))
	done
}
# With stubWaits=1 the maths stub stays running after its line until the explorer stub has seen that line in the log.
# So a glue that holds back maths output until the maths check ends fails.
deepMaths() {
	echo "maths stub exits $stubStatus"
	if [ "$stubWaits" = 1 ]; then waitFor test -e "$seen" || return 1; fi
	return "$stubStatus"
}
deepExplorer() {
	[ "$stubWaits" = 1 ] || return 0
	waitFor grep -qF '[maths] maths stub' "$log" && : >"$seen"
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
expect "maths output streaming while the maths check runs" "$out" "fail=0"
# Guard: a missing temp directory once failed the run as a maths failure. The glue needs no temp file.
out=$(export TMPDIR="$log.missing"; glue 0)
expect "a missing temp directory" "$out" "fail=0"
exit "$failed"
