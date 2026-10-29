# Sourced by check_site.sh and check_run_deep_checks.sh. The caller defines err, checkFridge, deepMaths, deepTidy and deepExplorer.
# The maths and tidy checks run in the background beside the fridge and explorer checks, so the job stays under 2 minutes (#46, #48).
# Their lines stream with a [maths] or [tidy] prefix, so a timeout kill keeps them.
runDeepChecks() {
	inBackground '[maths] ' deepMaths
	maths=$!
	inBackground '[tidy] ' deepTidy
	tidy=$!
	checkFridge
	deepExplorer || err "deep nested LSH explorer check failed"
	wait "$maths" || err "deep nested LSH maths check failed"
	wait "$tidy" || err "deep nested LSH tidy check failed"
}
# Starts the check $2 in the background with each of its lines after the prefix $1. $! then names it.
inBackground() {
	# A POSIX sh pipeline drops the check's status, so fd 3 carries it past the prefix filter.
	(
		status=$({ { "$2" 3>&- 2>&1; echo $? >&3; } | prefixLines "$1" >&4; } 3>&1)
		exit "${status:-1}"
	) 4>&1 &
}
# Prints each input line after the prefix $1 as it arrives.
prefixLines() { while IFS= read -r line || [ -n "$line" ]; do printf '%s%s\n' "$1" "$line"; done; }
