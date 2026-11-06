"""Page bodies. A page whose module is in this package is built by its body(page, snap, idx), which returns the
page's fragments in order; any other is a stub."""

import importlib
import importlib.util


def built(page):
    """The page's module, or None while the page is a stub."""
    name = f"{__name__}.{page.module}"
    return importlib.import_module(name) if importlib.util.find_spec(name) else None


def stub():
    """The header above already shows the title and blurb."""
    return ('<div class="callout">\n<p class="eyebrow">In progress</p>\n<p>This part is being written. '
            'Use the contents to reach the parts already published.</p>\n</div>')


def body(page, snap, idx):
    """(main body fragments, is a stub). Each fragment keeps its own id references when unique_ids renames."""
    module = built(page)
    return (module.body(page, snap, idx), False) if module else ([stub()], True)
