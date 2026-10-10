"""Generate the README overview figure (SVG) for IDS2Eval.

Usage: python docs/img/make_overview.py docs/img
"""

import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

THEMES = {
    "light": {
        "bg": "#ffffff",
        "card": "#f6f8fa",
        "line": "#d0d7de",
        "fg": "#1f2328",
        "muted": "#59636e",
        "diag": "#0969da",
        "ctrl": "#8250df",
        "intv": "#1b7c83",
        "look": "#9a6700",
        "arrow": "#8c959f",
        "ok": ("#1a7f37", "#dafbe1"),
        "warn": ("#9a6700", "#fff8c5"),
        "flag": ("#cf222e", "#ffebe9"),
    },
}

W, H = 1280, 640
TOP, BOT = 168, 540  # shared top and bottom edge of the three columns
PAD = 22  # inner padding of every card

# the four kinds of check: key, name, question, examples, number of checks
KINDS = [
    (
        "diag",
        "Diagnose",
        "Spot problems in the data",
        "duplicate rows · conflicting labels · one column that reveals the label",
        18,
    ),
    (
        "ctrl",
        "Control",
        "Is the repetition normal for this data?",
        "compares test rows copying training rows with copies inside training",
        1,
    ),
    (
        "intv",
        "Intervene",
        "Change the setup and retrain: does the score move?",
        "split by connection, not at random · drop IP addresses or duplicates",
        8,
    ),
    (
        "look",
        "Look up",
        "What is already known about this dataset?",
        "published labeling errors, extraction bugs and caveats",
        1,
    ),
]

# example scorecard rows: label, verdict before deduplication, verdict after
ROWS = [
    ("Duplicate rows", "flag", "ok"),
    ("IP address shortcut", "flag", "flag"),
    ("Repetition control", "warn", "ok"),
    ("Split by connection", "ok", "ok"),
    ("Class balance", "warn", "warn"),
]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, fill, weight=400, family=FONT, anchor="start", spacing=None):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}"{ls}>{esc(s)}</text>'
    )


def card(x, y, w, h, t, fill=None):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill or t["card"]}" stroke="{t["line"]}"/>'


def arrow(d, t, dashed=False):
    dash = ' stroke-dasharray="6 6"' if dashed else ""
    return f'<path d="{d}" stroke="{t["arrow"]}" stroke-width="2"{dash} fill="none" marker-end="url(#ah)"/>'


def figure(t):
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        'aria-label="IDS2Eval overview: a NIDS dataset and a YAML config go through four kinds of check '
        "(diagnose, control, intervene, look up), run before and after deduplication, and every verdict "
        'lands in one scorecard.">',
        f'<defs><marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{t["arrow"]}"/></marker></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="{t["bg"]}"/>',
        # headline
        text(48, 62, "IDS²EVAL", 13, t["diag"], 700, spacing="1.5"),
        text(48, 98, "Does a problem in the dataset change the result?", 30, t["fg"], 700),
        text(
            48,
            128,
            "28 automated checks, run on the raw data and again after removing duplicates. "
            "Every verdict lands in one citable scorecard.",
            16,
            t["muted"],
        ),
    ]

    # input column
    x0, w0 = 48, 232
    o.append(card(x0, TOP, w0, BOT - TOP, t))
    o.append(text(x0 + PAD, TOP + 36, "INPUT", 12, t["muted"], 700, spacing="1.2"))
    o.append(text(x0 + PAD, TOP + 74, "NIDS dataset", 20, t["fg"], 700))
    o.append(text(x0 + PAD, TOP + 100, "official train/test pair,", 14, t["muted"]))
    o.append(text(x0 + PAD, TOP + 120, "or raw flow files", 14, t["muted"]))
    o.append(f'<line x1="{x0 + PAD}" y1="{TOP + 150}" x2="{x0 + w0 - PAD}" y2="{TOP + 150}" stroke="{t["line"]}"/>')
    o.append(text(x0 + PAD, TOP + 190, "YAML config", 20, t["fg"], 700))
    o.append(text(x0 + PAD, TOP + 216, "columns, split and", 14, t["muted"]))
    o.append(text(x0 + PAD, TOP + 236, "which checks to run", 14, t["muted"]))
    cmd_y = BOT - PAD - 54
    o.append(card(x0 + PAD, cmd_y, w0 - 2 * PAD, 54, t, fill=t["bg"]))
    o.append(text(x0 + PAD + 14, cmd_y + 22, "ids2eval run", 13, t["fg"], 500, MONO))
    o.append(text(x0 + PAD + 28, cmd_y + 42, "--config cfg.yaml", 13, t["fg"], 500, MONO))

    # four kinds of check, stacked to fill the column height exactly
    lx, lw, gap = 336, 548, 12
    lh = (BOT - TOP - gap * (len(KINDS) - 1)) / len(KINDS)
    for i, (key, name, question, examples, n) in enumerate(KINDS):
        y = TOP + i * (lh + gap)
        c = t[key]
        o.append(card(lx, y, lw, lh, t))
        o.append(f'<rect x="{lx}" y="{y}" width="6" height="{lh}" rx="3" fill="{c}"/>')
        o.append(text(lx + 28, y + 29, name, 18, c, 700))
        o.append(text(lx + 28, y + 52, question, 15, t["fg"], 600))
        o.append(text(lx + 28, y + 71, examples, 13, t["muted"]))
        count = f"{n} check" if n == 1 else f"{n} checks"
        o.append(text(lx + lw - 24, y + 29, count, 15, c, 700, anchor="end"))

    # scorecard column
    sx, sw = 940, 292
    mid = (TOP + BOT) / 2
    o.append(arrow(f"M{x0 + w0 + 6},{mid} L{lx - 10},{mid}", t))
    o.append(arrow(f"M{lx + lw + 6},{mid} L{sx - 10},{mid}", t))
    o.append(card(sx, TOP, sw, BOT - TOP, t))
    o.append(text(sx + PAD, TOP + 36, "SCORECARD", 12, t["muted"], 700, spacing="1.2"))
    o.append(text(sx + sw - PAD, TOP + 36, "example", 12, t["muted"], 400, anchor="end"))
    cb, ca = sx + 186, sx + 242
    o.append(text(cb, TOP + 74, "before", 12, t["muted"], 600, anchor="middle"))
    o.append(text(ca, TOP + 74, "after", 12, t["muted"], 600, anchor="middle"))
    o.append(text((cb + ca) / 2, TOP + 90, "removing duplicates", 11, t["muted"], 400, anchor="middle"))
    for i, (label, before, after) in enumerate(ROWS):
        y = TOP + 126 + i * 40
        o.append(f'<line x1="{sx + PAD}" y1="{y - 26}" x2="{sx + sw - PAD}" y2="{y - 26}" stroke="{t["line"]}"/>')
        o.append(text(sx + PAD, y, label, 14, t["fg"]))
        for cx, verdict in ((cb, before), (ca, after)):
            fg, bg = t[verdict]
            o.append(
                f'<rect x="{cx - 23}" y="{y - 15}" width="46" height="21" rx="10.5" fill="{bg}" '
                f'stroke="{fg}" stroke-opacity="0.35"/>'
            )
            o.append(text(cx, y, verdict, 12, fg, 700, anchor="middle"))
    foot = BOT - PAD - 4
    o.append(f'<line x1="{sx + PAD}" y1="{foot - 24}" x2="{sx + sw - PAD}" y2="{foot - 24}" stroke="{t["line"]}"/>')
    o.append(text(sx + PAD, foot, "scorecard.json · .md · .html", 13, t["fg"], 500, MONO))

    # recommend loop back to the config
    ly = BOT + 52
    loop = f"M{sx + sw / 2},{BOT + 6} L{sx + sw / 2},{ly} L{x0 + w0 / 2},{ly} L{x0 + w0 / 2},{BOT + 10}"
    o.append(arrow(loop, t, True))
    o.append(
        f'<rect x="{W / 2 - 300}" y="{ly - 17}" width="600" height="34" rx="17" fill="{t["bg"]}" stroke="{t["line"]}"/>'
    )
    o.append(
        text(
            W / 2,
            ly + 5,
            "ids2eval recommend  ·  suggests config fixes for flagged checks, then re-run",
            14,
            t["fg"],
            500,
            anchor="middle",
        )
    )
    o.append("</svg>")
    return "\n".join(o)


(OUT / "ids2eval-overview.svg").write_text(figure(THEMES["light"]))
print("ok")
