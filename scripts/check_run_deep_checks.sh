#!/bin/sh
# Checks the background glue in scripts/run_deep_checks.sh with stub checks, as CI never sees a real maths failure (#46).
. scripts/run_deep_checks.sh
failed=0
checkFridge() { :; }
deepExplorer() { :; }
deepMaths() { echo "maths stub exits $stubStatus"; return "$stubStatus"; }

# Prints the glue's output and verdict with a maths stub that exits $1.
glue() {
	(
		stubStatus=$1 fail=0
		err() { echo "FAIL: $*"; fail=1; }
		runDeepChecks
		echo "fail=$fail"
	) 2>&1
}
# Fails when the output $2 of case $1 lacks $3.
expect() {
	case $2 in
	*"$3"*) ;;
	*) printf 'FAIL: %s: no "%s" in\n%s\n' "$1" "$3" "$2" >&2; failed=1 ;;
	esac
}

out=$(glue 1)
expect "a failing maths stub" "$out" "maths stub exits 1"
expect "a failing maths stub" "$out" "FAIL: deep nested LSH maths check failed"
expect "a failing maths stub" "$out" "fail=1"
out=$(glue 0)
expect "a passing maths stub" "$out" "fail=0"
exit "$failed"
