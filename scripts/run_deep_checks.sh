# Sourced by check_site.sh and check_run_deep_checks.sh. The caller defines err, checkFridge, deepMaths and deepExplorer.
# The maths check runs in the background beside the fridge and explorer checks, so the job stays under 2 minutes (#46).
# Its lines stream with a [maths] prefix, so a timeout kill keeps them.
runDeepChecks() {
	# A POSIX sh pipeline drops the maths status, so fd 3 carries it past the prefix filter.
	(
		status=$({ { deepMaths 3>&- 2>&1; echo $? >&3; } | prefixLines '[maths] ' >&4; } 3>&1)
		exit "${status:-1}"
	) 4>&1 &
	maths=$!
	checkFridge
	deepExplorer || err "deep nested LSH explorer check failed"
	wait "$maths" || err "deep nested LSH maths check failed"
}
# Prints each input line after the prefix $1 as it arrives.
prefixLines() { while IFS= read -r line || [ -n "$line" ]; do printf '%s%s\n' "$1" "$line"; done; }
