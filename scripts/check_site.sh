#!/bin/sh
# Check a built Jekyll site for the Simulations section. Usage: check_site.sh <site dir>
site=${1:?usage: check_site.sh <site dir>}
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

[ -f "$site/simulations/index.html" ] || err "missing simulations/index.html"

for page in hnsw fridge-event-sim; do
	built="$site/simulations/$page/index.html"
	if [ ! -f "$built" ]; then
		err "missing simulations/$page/index.html"
	elif ! cmp -s "$built" "simulations/$page/index.html"; then
		err "simulations/$page/index.html differs from the repo copy"
	fi
done

# A fixed-height hover box keeps hovering from shifting the HNSW page (#13).
hnsw="$site/simulations/hnsw/index.html"
if [ -f "$hnsw" ]; then
	grep -q '^\.hover-info {.*[{;] *height: 1\.3em;.*overflow: hidden;' "$hnsw" || err "hnsw .hover-info lacks height: 1.3em with overflow: hidden"
	! grep -q '\.hover-info {[^}]*min-height' "$hnsw" || err "hnsw .hover-info uses min-height"
fi

grep -q 'href="/simulations"' "$site/index.html" 2>/dev/null || err "nav in index.html lacks the Simulations link"

if [ -f "$site/simulations/index.html" ]; then
	for href in $(grep -o 'href="/\([^/"][^"]*\)\{0,1\}"' "$site/simulations/index.html" | sed 's/^href="//; s/"$//; s/[?#].*//'); do
		target="$site$href"
		[ -f "$target" ] || [ -f "${target%/}/index.html" ] || err "broken link $href on simulations/index.html"
	done
fi

[ "$fail" -eq 0 ] && echo "site check passed"
exit "$fail"
