#!/bin/sh
# Check a built Jekyll site for the Projects section. Usage: check_site.sh <site dir>
site=${1:?usage: check_site.sh <site dir>}
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

[ -f "$site/projects/index.html" ] || err "missing projects/index.html"
# The old Simulations index URL stays live as a redirect to Projects.
grep -q 'http-equiv="refresh" content="0; *url=\(https://quintuplin\.github\.io\)\{0,1\}/projects/\{0,1\}"' "$site/simulations/index.html" 2>/dev/null || err "simulations/index.html does not redirect to /projects"

# Standalone pages are served verbatim.
for page in simulations/*/index.html studies/*/index.html; do
	[ -f "$page" ] || continue
	if [ ! -f "$site/$page" ]; then
		err "missing $page"
	elif ! cmp -s "$site/$page" "$page"; then
		err "$page differs from the repo copy"
	fi
done

# Standalone pages carry a site bar with every main nav link (#21).
navHrefs=$(sed -n '/<nav>/,/<\/nav>/p' _layouts/default.html | grep -o 'href="/[^"]*"')
for page in simulations/*/index.html studies/*/index.html; do
	[ -f "$page" ] || continue
	grep -q 'class="site-bar"' "$page" || err "$page lacks the site bar"
	for href in $navHrefs; do
		grep -qF "$href" "$page" || err "$page site bar lacks $href"
	done
done

# A fixed-height hover box keeps hovering from shifting the HNSW page (#13).
hnsw="$site/simulations/hnsw/index.html"
if [ -f "$hnsw" ]; then
	grep -q '^\.hover-info {.*[{;] *height: 1\.3em;.*overflow: hidden;' "$hnsw" || err "hnsw .hover-info lacks height: 1.3em with overflow: hidden"
	! grep -q '\.hover-info {[^}]*min-height' "$hnsw" || err "hnsw .hover-info uses min-height"
fi

grep -q 'href="/projects"' "$site/index.html" 2>/dev/null || err "nav in index.html lacks the Projects link"
! grep -Eq 'href="/(simulations|studies)/?"' "$site/index.html" 2>/dev/null || err "nav in index.html still links the old Simulations or Studies index"

# The about page shows the I Made This comic credited to Nedroid (#17).
[ -f "$site/assets/i-made-this-ai.webp" ] || err "missing assets/i-made-this-ai.webp"
grep -q 'src="/assets/i-made-this-ai.webp"' "$site/about/index.html" 2>/dev/null || err "about/index.html lacks the I Made This comic"
grep -q 'href="https://nedroidcomics.tumblr.com/post/41879001445/the-internet"' "$site/about/index.html" 2>/dev/null || err "about/index.html lacks the Nedroid credit link"

# The sitemap is generated with real URLs and no raw Liquid (#25).
grep -q '<loc>' "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml missing or lists no <loc>"
! grep -Eq '\{%|\{\{' "$site/sitemap.xml" 2>/dev/null || err "sitemap.xml contains raw Liquid"

for index in projects/index.html; do
	[ -f "$site/$index" ] || continue
	for href in $(grep -o 'href="/\([^/"][^"]*\)\{0,1\}"' "$site/$index" | sed 's/^href="//; s/"$//; s/[?#].*//'); do
		target="$site$href"
		[ -f "$target" ] || [ -f "${target%/}/index.html" ] || err "broken link $href on $index"
	done
done

[ "$fail" -eq 0 ] && echo "site check passed"
exit "$fail"
