# Sourced by check_site.sh and check_run_kalah_tdd_page_checks.sh. The caller defines err.
# Each study page group brings its own test file in the folder $1, so no group edits check_site.sh (#79).
runKalahTddPageChecks() {
	for t in "$1"/check_kalah_tdd_page_*.py; do
		[ -e "$t" ] || { err "no $1/check_kalah_tdd_page_*.py"; break; }
		python3 -I "$t" || err "$t failed"
	done
}
