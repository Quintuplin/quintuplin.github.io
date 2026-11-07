#!/bin/sh
# Checks the Kalah TDD page test loop in scripts/run_kalah_tdd_page_checks.sh against stub test folders (#79).
. scripts/run_kalah_tdd_page_checks.sh
failed=0
dir=$(mktemp -d "${TMPDIR:-/tmp}/page-loop.XXXXXX") || exit 1
trap 'rm -rf "$dir"' EXIT

# Prints the loop's output and verdict over the folder $dir.
loop() {
	(
		fail=0
		err() { echo "FAIL: $*"; fail=1; }
		runKalahTddPageChecks "$dir"
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

out=$(loop)
expect "no page test files" "$out" "FAIL: no $dir/check_kalah_tdd_page_*.py"
expect "no page test files" "$out" "fail=1"
echo 'pass' >"$dir/check_kalah_tdd_page_a.py"
out=$(loop)
expect "a passing page test" "$out" "fail=0"
echo 'raise SystemExit(1)' >"$dir/check_kalah_tdd_page_b.py"
out=$(loop)
expect "a failing page test" "$out" "FAIL: $dir/check_kalah_tdd_page_b.py failed"
expect "a failing page test" "$out" "fail=1"
exit "$failed"
