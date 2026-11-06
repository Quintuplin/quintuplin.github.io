#!/bin/sh
# Check a built Jekyll site for the Projects section. Usage: check_site.sh <site dir>
site=${1:?usage: check_site.sh <site dir>}
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

[ -f "$site/projects/index.html" ] || err "missing projects/index.html"
# The old Simulations index URL stays live as a redirect to Projects.
grep -q 'http-equiv="refresh" content="0; *url=\(https://quintuplin\.github\.io\)\{0,1\}/projects/\{0,1\}"' "$site/simulations/index.html" 2>/dev/null || err "simulations/index.html does not redirect to /projects"

# Standalone pages are served verbatim, nested study pages and their stylesheets too (#60).
studyPages=$(find studies -name '*.html' | sort)
for page in simulations/*/index.html $studyPages $(find studies -name '*.css'); do
	[ -f "$page" ] || continue
	if [ ! -f "$site/$page" ]; then
		err "missing $page"
	elif ! cmp -s "$site/$page" "$page"; then
		err "$page differs from the repo copy"
	fi
done

# Standalone pages carry a site bar with every main nav link (#21) and the glass theme in both modes (#23).
navHrefs=$(sed -n '/<nav>/,/<\/nav>/p' _layouts/default.html | grep -o 'href="/[^"]*"')
for page in simulations/*/index.html $studyPages; do
	[ -f "$page" ] || continue
	grep -q 'class="site-bar"' "$page" || err "$page lacks the site bar"
	for href in $navHrefs; do
		grep -qF "$href" "$page" || err "$page site bar lacks $href"
	done
	# The theme may come from a site stylesheet the page links, as the Kalah TDD study pages do (#59).
	theme="$page $(sed -n 's|.*<link rel="stylesheet" href="/\([^"]*\.css\)">.*|\1|p' "$page")"
	grep -q 'prefers-color-scheme: *dark' $theme || err "$page lacks a dark mode block"
	grep -q 'class="backdrop"' "$page" || err "$page lacks the photo backdrop"
	grep -qF 'url("/assets/bg.jpg")' $theme || err "$page does not load the backdrop photo"
	grep -q 'backdrop-filter' $theme || err "$page lacks the glass backdrop-filter"
	# The bar lists LinkedIn before GitHub, as the main nav does.
	[ "$(sed -n '/class="site-bar"/,/<\/nav>/p' "$page" | grep -o 'LinkedIn\|GitHub' | head -1)" = LinkedIn ] || err "$page site bar does not list LinkedIn before GitHub"
done

# The main site follows the browser dark mode setting (#23).
checkMainDark() {
	grep -q 'prefers-color-scheme: *dark' "$site/css/main.css" 2>/dev/null || err "css/main.css lacks a prefers-color-scheme: dark block"
}
checkMainDark
python3 scripts/check_contrast.py . || err "glass contrast check failed"
python3 -I scripts/check_study_css.py . || err "Kalah TDD study stylesheet check failed"
# Its touch target check catches missing and overridden sidebar row heights (#60).
python3 -I scripts/check_check_study_css.py || err "study stylesheet touch target check failed"
# Post figures up to 1057 px wide scaled down to the sheet instead of widening phone pages (#23).
grep -q '^\.post img {[^}]*max-width: *100%' "$site/css/main.css" 2>/dev/null || err "css/main.css lets post images overflow the sheet"

# A fixed-height hover box keeps hovering from shifting the HNSW page (#13).
hnsw="$site/simulations/hnsw/index.html"
if [ -f "$hnsw" ]; then
	grep -q '^\.hover-info {.*[{;] *height: 1\.3em;.*overflow: hidden;' "$hnsw" || err "hnsw .hover-info lacks height: 1.3em with overflow: hidden"
	! grep -q '\.hover-info {[^}]*min-height' "$hnsw" || err "hnsw .hover-info uses min-height"
	# A wrapping flex row keeps the alpha select at its full option width; a squeezed grid cell cut it to "1, H" (#23).
	grep -B2 'id="param-alpha"' "$hnsw" | grep -q '<div class="select-row">' || err "hnsw alpha select is not in a select-row"
	grep -q '^\.select-row {[^}]*display: flex;[^}]*flex-wrap: wrap' "$hnsw" || err "hnsw .select-row does not wrap the select below its label"
	! grep -q '\.select-row select {[^}]*min-width: *0' "$hnsw" || err "hnsw .select-row select can shrink below its option text"
	grep -q 'id="code-title">The code<' "$hnsw" || err "hnsw code heading is not \"The code\""
	# Above 860 px the header scrolls off and the workspace fills a screen, so the graph is not squashed (#23).
	sed -n '/^@media not all and (max-width: 860px) {/,/^}/p' "$hnsw" | grep -q '^ *\.layout {[^}]*height: max([^;]*100dvh' || err "hnsw desktop .layout is not one screen tall"
	grep -q '^\.legend {[^}]*font-size: 0\.75rem' "$hnsw" || err "hnsw legend is not at the reduced 0.75rem size"
fi

# The fridge view fits its canvas, leaves the wheel to the page, opens on a multi-camera config and starts as not started (#26).
fridge=simulations/fridge-event-sim/index.html
checkFridge() { node scripts/check_fridge.mjs "$site/$fridge" || err "fridge behaviour check failed"; }

# The Deep Nested LSH maths matches the study reference and its explorer behaves (#31).
# The tidy rule parity takes about half as long as the rest of the maths, so it runs as its own process (#48).
deep="$site/simulations/deep-nested-lsh/index.html"
deepMaths() { node --test-skip-pattern='^tidy' scripts/check_deep_nested_lsh.mjs "$deep"; }
deepTidy() { node --test-name-pattern='^tidy' scripts/check_deep_nested_lsh.mjs "$deep"; }
deepExplorer() { node scripts/check_deep_nested_lsh_explorer.mjs "$deep"; }
. scripts/run_deep_checks.sh
sh scripts/check_run_deep_checks.sh || err "the background glue of runDeepChecks is broken"
if command -v node >/dev/null 2>&1; then
	runDeepChecks
else
	err "node is missing: scripts/check_fridge.mjs cannot run"
	err "node is missing: the deep nested LSH checks cannot run"
fi
grep -q '^#lay {[^}]*max-width: *100%' "$fridge" || err "fridge #lay select caps the config name below its full width"
# Its data generator refuses a dirty study tree or a --sha other than HEAD (#33) and reads the study's depth cap (#41).
python3 -I scripts/check_build_deep_nested_lsh_data.py || err "deep nested LSH generator check failed"
# The Kalah TDD snapshot comes from one clean tdd-experiment commit, drops host paths and matches its manifest (#56).
python3 -I scripts/check_fetch_kalah_tdd_snapshot.py || err "Kalah TDD snapshot fetcher check failed"
# Study flowcharts list every node, edge and loop in their text version, escape text and take colours from study.css (#57).
python3 -I scripts/check_kalah_tdd_flow.py || err "Kalah TDD flowchart check failed"
# The study pages match a fresh build, rewrite every old report link, keep ids unique and leak no host path (#59).
python3 -I scripts/check_build_kalah_tdd_study.py || err "Kalah TDD study page build check failed"
# Study sidebar and cross-page links reach a real page and id, and ids are unique per page (#60).
python3 -I scripts/check_check_study_nav.py || err "study navigation check failed"
# Built Kalah TDD study pages keep every snapshot figure, row, tile and term, and define their labels on measures (#61).
# --final fails a stub page, as every page is built (#113).
python3 -I scripts/check_kalah_tdd_study.py --final || err "Kalah TDD study completeness check failed"
python3 -I scripts/check_check_kalah_tdd_study.py || err "Kalah TDD study completeness check self-test failed"
# Each study page group brings its own test file, so no group edits this line (#79).
. scripts/run_kalah_tdd_page_checks.sh
runKalahTddPageChecks scripts
sh scripts/check_run_kalah_tdd_page_checks.sh || err "the Kalah TDD page test loop is broken"
# Jekyll skips underscore folders, so the snapshot stays off the site and its sitemap (#56).
[ ! -e "$site/_snapshots" ] || err "_snapshots is published"
! grep -q '_snapshots' "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml lists _snapshots"
# The outcome chip may shrink and wrap, so the FN chip stays inside the narrow root rung on phones (#31).
grep -q '^\.outcome {[^}]*min-width: *0' simulations/deep-nested-lsh/index.html || err "deep nested LSH .outcome chip cannot shrink inside a narrow rung"
! grep -q '^\.outcome {[^}]*nowrap' simulations/deep-nested-lsh/index.html || err "deep nested LSH .outcome chip cannot wrap inside a narrow rung"

grep -q 'href="/projects"' "$site/index.html" 2>/dev/null || err "nav in index.html lacks the Projects link"
! grep -Eq 'href="/(simulations|studies)/?"' "$site/index.html" 2>/dev/null || err "nav in index.html still links the old Simulations or Studies index"

# The about page shows the I Made This comic credited to Nedroid (#17).
[ -f "$site/assets/i-made-this-ai.webp" ] || err "missing assets/i-made-this-ai.webp"
grep -q 'src="/assets/i-made-this-ai.webp"' "$site/about/index.html" 2>/dev/null || err "about/index.html lacks the I Made This comic"
grep -q 'href="https://nedroidcomics.tumblr.com/post/41879001445/the-internet"' "$site/about/index.html" 2>/dev/null || err "about/index.html lacks the Nedroid credit link"

# The sitemap is generated with real URLs and no raw Liquid (#25).
grep -q '<loc>' "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml missing or lists no <loc>"
! grep -Eq '\{%|\{\{' "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml contains raw Liquid"
for page in $studyPages; do
	grep -qF "/${page%index.html}</loc>" "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml lacks $page"
done

for index in projects/index.html; do
	[ -f "$site/$index" ] || continue
	for href in $(grep -o 'href="/\([^/"][^"]*\)\{0,1\}"' "$site/$index" | sed 's/^href="//; s/"$//; s/[?#].*//'); do
		target="$site$href"
		[ -f "$target" ] || [ -f "${target%/}/index.html" ] || err "broken link $href on $index"
	done
done

# Every post must reach the blog index. Jekyll skips future-dated posts and broken front matter without failing (#29).
for post in _posts/*.md; do
	title=$(sed -n '1,/^---$/s/^title: *//p' "$post" | head -1 | sed "s/^\"\(.*\)\"\$/\1/; s/^'\(.*\)'\$/\1/")
	if [ -z "$title" ]; then
		err "$post has no title"
	else
		grep -qF -e "$title" "$site/blog/index.html" 2>/dev/null || err "$post is missing from blog/index.html"
	fi
done

[ "$fail" -eq 0 ] && echo "site check passed"
exit "$fail"
