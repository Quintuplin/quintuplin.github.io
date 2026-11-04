# quintuplin.github.io

Personal site of Jack Fraser: home, about, and resume (PDF served from Google Drive). Built with Jekyll on GitHub Pages, originally following http://jmcglone.com/guides/github-pages/ for CSCI 362 at the College of Charleston.

The Projects section links standalone pages under `simulations/` and `studies/` that are copied or ported from their source projects. The old `/simulations` index redirects to it. Each standalone page adds a static site bar linking back to the main sections, so a copied page differs from its source by that bar.

The site has no CI. Run the checks locally before each PR. Build `_site` with the GitHub Pages image in Docker, then check it with node and python3 on the path.

    docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" -e GITHUB_WORKSPACE=/github/workspace -e INPUT_SOURCE=. -e INPUT_DESTINATION=_site ghcr.io/actions/jekyll-build-pages:v1.0.13
    sh scripts/check_site.sh _site

To update the resume, replace the file in Google Drive via **Manage versions → Upload new version** so the file ID stays the same; no commit needed.
