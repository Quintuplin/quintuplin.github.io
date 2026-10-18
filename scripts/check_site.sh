#!/bin/sh
# Check a built Jekyll site for the Simulations section. Usage: check_site.sh <site dir>
site=${1:?usage: check_site.sh <site dir>}
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }

[ -f "$site/simulations/index.html" ] || err "missing simulations/index.html"

for page in hnsw fridge-visibility; do
	built="$site/simulations/$page/index.html"
	if [ ! -f "$built" ]; then
		err "missing simulations/$page/index.html"
	elif ! cmp -s "$built" "simulations/$page/index.html"; then
		err "simulations/$page/index.html differs from the repo copy"
	fi
done

grep -q 'href="/simulations"' "$site/index.html" 2>/dev/null || err "nav in index.html lacks the Simulations link"

if [ -f "$site/simulations/index.html" ]; then
	for href in $(grep -o 'href="/[^"]*"' "$site/simulations/index.html" | sed 's/^href="//; s/"$//; s/[?#].*//'); do
		target="$site$href"
		[ -f "$target" ] || [ -f "${target%/}/index.html" ] || err "broken link $href on simulations/index.html"
	done
fi

[ "$fail" -eq 0 ] && echo "site check passed"
exit "$fail"
