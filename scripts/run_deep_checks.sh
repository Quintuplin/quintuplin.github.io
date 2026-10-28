# Sourced by check_site.sh and check_run_deep_checks.sh. The caller defines err, checkFridge, deepMaths and deepExplorer.
# The maths check runs in the background beside the fridge and explorer checks, so the job stays under 2 minutes (#46).
# Its output waits until it ends so the logs do not interleave.
runDeepChecks() {
	mathsLog=$(mktemp "${TMPDIR:-/tmp}/deep-maths.XXXXXX")
	deepMaths >"$mathsLog" 2>&1 &
	maths=$!
	checkFridge
	deepExplorer || err "deep nested LSH explorer check failed"
	wait "$maths"
	mathsStatus=$?
	cat "$mathsLog"
	rm -f "$mathsLog"
	[ "$mathsStatus" -eq 0 ] || err "deep nested LSH maths check failed"
}
