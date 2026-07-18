"""
theming.py — Accent registry so panels actually follow the active theme.

The problem this solves:
    Panels build their widgets with inline setStyleSheet() calls that
    hardcode the Default theme's green (#00e87a). Inline QSS beats the
    global stylesheet, so switching to Cyberpunk / Ember / Matrix left
    big chunks of the UI stubbornly green. set_palette() existed but
    only ever restyled one or two widgets.

How to use it:
    1. Build styles as templates with {accent} / {accent2} / {dim} /
       {text} / {card} / {bg} placeholders instead of hex literals.
    2. Register them at build time:
           themed(self, btn, "QPushButton{{background:{accent};}}")
       — this applies the style immediately AND remembers it.
    3. In the panel's set_palette(), call:
           apply_theme(self, palette)
       Every registered widget is re-styled with the new palette.

Templates use str.format(), so literal braces in QSS must be doubled:
    "QPushButton{{color:{accent};}}"
"""

# Fallbacks match the Default theme, so a missing key never crashes a build.
_FALLBACKS = {
    "accent":  "#00e87a",
    "accent2": "#38bdf8",
    "bg":      "#050810",
    "panel":   "#080d16",
    "card":    "#0d1520",
    "border":  "#172338",
    "text":    "#d4dfe9",
    "dim":     "#6b83a0",
    "hover":   "#121d2c",
    "input":   "#070c16",
    "red":     "#f87171",
    "amber":   "#fbbf24",
    "green":   "#00e87a",
    "blue":    "#38bdf8",
    "purple":  "#a78bfa",
}


def _resolve(palette: dict) -> dict:
    """Merge a (possibly partial) palette over the Default fallbacks."""
    out = dict(_FALLBACKS)
    if palette:
        out.update({k: v for k, v in palette.items() if isinstance(v, str)})
    return out


def themed(panel, widget, template: str, palette: dict = None):
    """
    Apply an accent-aware style template to `widget` and register it on
    `panel` so a later apply_theme() can recolor it.

    Returns the widget, so it chains:
        lay.addWidget(themed(self, QPushButton("Go"), TPL))
    """
    registry = getattr(panel, "_themed_widgets", None)
    if registry is None:
        registry = []
        panel._themed_widgets = registry
    registry.append((widget, template))

    # Prefer the panel's live palette if it has one, else whatever was passed.
    pal = palette or getattr(panel, "_palette", None) or {}
    _style(widget, template, pal)
    return widget


def apply_theme(panel, palette: dict):
    """
    Re-style every widget registered on `panel` with the new palette.
    Safe to call even if nothing was registered. Call this from
    the panel's set_palette().
    """
    panel._palette = palette or {}
    for widget, template in getattr(panel, "_themed_widgets", []):
        _style(widget, template, palette)


def _style(widget, template: str, palette: dict):
    """Format one template against the palette and push it onto the widget."""
    try:
        widget.setStyleSheet(template.format(**_resolve(palette)))
    except Exception:
        # A malformed template should never take a panel down — fall back
        # to the raw string so the widget is at least styled *somehow*.
        try:
            widget.setStyleSheet(template)
        except Exception:
            pass
