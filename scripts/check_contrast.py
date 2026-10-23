#!/usr/bin/env python3
"""Check text and graphic contrast on the glass sheets over the photo backdrop (#23).

Each colour is composited the way the browser stacks it: --glass over the worst blurred
backdrop pixel, then --surface over that sheet. Usage: check_contrast.py [repo root]
"""
import hashlib
import re
import sys
from pathlib import Path

# Darkest and brightest pixel of bg.jpg at 480x360 after a Gaussian blur of sigma 3.3,
# which matches the CSS blur(10px) at a 1440 px wide cover. Dark mode is checked
# against the undimmed photo, which is brighter than the dimmed one and so stricter.
BG_SHA256 = "7301e0bca93180f7068e3684d44ff03cdeb505b9153ccc6b31b435b934ee6ec4"
WORST_PIXELS = ((9, 10, 11), (250, 244, 194))
TEXT, GRAPHIC = 4.5, 3.0

# Tokens drawn on the bare sheet (glass) and on inner cards (card). Graphics cover
# strokes, focus rings and large text, and are checked on both. Card graphics, such as
# legend swatches, appear only on cards.
PAGES = {
    "css/main.css": {"glass": ["ink", "muted", "accent"]},
    "studies/subagent-crew-study/index.html": {
        "glass": ["ink", "muted", "accent"],
        "card": ["ink", "muted", "accent", "main", "haiku", "sonnet", "opus"],
        "graphic": ["crew", "ultra", "fail"],
    },
    "simulations/hnsw/index.html": {
        "glass": ["text", "muted", "accent"],
        "card": ["text", "muted", "prune"],
        "graphic": ["focus", "lsh", "disk"],
        "card-graphic": ["node", "edge", "connector", "trace", "found", "prune", "lsh"],
    },
    "simulations/fridge-event-sim/index.html": {
        "glass": ["text", "muted", "accent"],
        "card": ["text", "muted"],
        "graphic": ["focus", "event"],
    },
}
LIGHT = re.compile(r"(?m)^:root\s*\{")
DARK = re.compile(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{")
FORCED_DARK = re.compile(r'(?m)^:root\[data-theme="dark"\]\s*\{')
PROP = re.compile(r"--([\w-]+)\s*:\s*([^;}]+)")


def block(text, pattern):
    """Return the custom properties of the first block pattern opens that defines --glass.

    Pages also open token-free blocks with the same selector, such as a dark .backdrop filter,
    so the first match is not always the token block. Falls back to the first block, or None.
    """
    found = []
    for m in pattern.finditer(text):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        found.append({k: v.strip() for k, v in PROP.findall(text[m.end():i])})
    return next((b for b in found if "glass" in b), found[0] if found else None)


def colour(value):
    """Parse #rgb, #rrggbb or rgb()/rgba() into (rgb, alpha)."""
    value = value.strip()
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            raise ValueError(f"unsupported colour {value}: use #rrggbb or rgba() so alpha is checked")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)), 1.0
    m = re.fullmatch(r"rgba?\(([^)]*)\)", value)
    if not m:
        raise ValueError(f"not a colour: {value}")
    parts = [float(p) for p in re.split(r"[\s,/]+", m.group(1).strip())]
    return tuple(parts[:3]), parts[3] if len(parts) > 3 else 1.0


def over(top, bottom):
    rgb, a = top
    return tuple(t * a + b * (1 - a) for t, b in zip(rgb, bottom))


def luminance(rgb):
    lin = [(c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def check_mode(page, mode, tokens, roles):
    errors = []
    if "glass" not in tokens:
        return [f"{page} {mode}: no --glass token"]
    missing = sorted({name for names in roles.values() for name in names} - tokens.keys())
    errors += [f"{page} {mode}: token --{name} missing" for name in missing]
    for px in WORST_PIXELS:
        layers = {"glass": over(colour(tokens["glass"]), px)}
        if "surface" in tokens:
            layers["card"] = over(colour(tokens["surface"]), layers["glass"])
        checks = [(role, name, TEXT) for role in ("glass", "card") for name in roles.get(role, [])]
        checks += [(role, name, GRAPHIC) for role in layers for name in roles.get("graphic", [])]
        checks += [("card", name, GRAPHIC) for name in roles.get("card-graphic", [])]
        for role, name, need in checks:
            if role not in layers:
                errors.append(f"{page} {mode}: no --surface for card tokens")
                continue
            if name in missing:
                continue
            got = ratio(over(colour(tokens[name]), layers[role]), layers[role])
            if got < need:
                errors.append(f"{page} {mode}: --{name} {tokens[name]} on {role} over {px} is {got:.2f}:1, needs {need}:1")
    return errors


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    errors = []
    if hashlib.sha256((root / "assets/bg.jpg").read_bytes()).hexdigest() != BG_SHA256:
        errors.append("assets/bg.jpg changed: re-pin worst pixels and BG_SHA256")
    for page, roles in PAGES.items():
        text = (root / page).read_text(encoding="utf-8")
        light, dark = block(text, LIGHT), block(text, DARK)
        if light is None or dark is None:
            errors.append(f"{page}: missing the light :root block or the dark media block")
            continue
        forced = block(text, FORCED_DARK)
        if forced is not None and forced != dark:
            errors.append(f"{page}: [data-theme=\"dark\"] tokens differ from the dark media block")
        try:
            errors += check_mode(page, "light", light, roles)
            # Merged with light tokens, a dark block without --glass would be checked on light glass.
            if "glass" not in dark:
                errors.append(f"{page}: no dark media block defines --glass")
            else:
                errors += check_mode(page, "dark", {**light, **dark}, roles)
        except ValueError as e:
            errors.append(f"{page}: {e}")
    for e in errors:
        print("FAIL:", e, file=sys.stderr)
    if not errors:
        print("contrast check passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
