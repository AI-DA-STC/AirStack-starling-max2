#!/usr/bin/env python3
"""Build the training-pipeline proposal deck with native PowerPoint flowchart shapes.

Every box is an editable flowchart AutoShape; arrows are connectors glued to the
shapes' connection sites, so they follow a box when it is moved in PowerPoint.

Usage: python3 build_deck.py <output.pptx>
"""
import sys

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR as TC
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

FONT = "Calibri"
W, H = 13.333, 7.5

# Theme palette (written into the deck's theme so it can be restyled in one place).
THEME = {
    "dk1": "1B1F2A", "lt1": "FFFFFF", "dk2": "14213D", "lt2": "EEF1F5",
    "accent1": "0F7B6C",  # teal: the new training pipeline
    "accent2": "1F5FBF",  # Guard team
    "accent3": "C8102E",  # Strike team
    "accent4": "B7791F",  # amber: decisions
    "accent5": "5B6472",  # grey: existing systems, unchanged
    "accent6": "2E7D32",  # green: pass / evidence
    "hlink": "1F5FBF", "folHlink": "5B6472",
}
PIPE, GUARD, STRIKE, DECIDE, EXIST, PASS = (
    TC.ACCENT_1, TC.ACCENT_2, TC.ACCENT_3, TC.ACCENT_4, TC.ACCENT_5, TC.ACCENT_6)
DARK, LIGHT, INK, PAPER = TC.TEXT_2, TC.BACKGROUND_2, TC.TEXT_1, TC.BACKGROUND_1

TOP, LEFT, BOTTOM, RIGHT = 0, 1, 2, 3  # connection sites on four-site shapes


def apply_theme(prs):
    part = prs.slide_master.part.part_related_by(RT.THEME)
    root = etree.fromstring(part.blob)
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    scheme = root.find(".//a:clrScheme", ns)
    scheme.set("name", "Training pipeline")
    for name, hexv in THEME.items():
        el = scheme.find(f"a:{name}", ns)
        for child in list(el):
            el.remove(child)
        etree.SubElement(el, qn("a:srgbClr")).set("val", hexv)
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def style_layouts(prs):
    """Resize the template's 4:3 placeholders for the 16:9 slide."""
    title_only = prs.slide_layouts[5]
    for ph in title_only.placeholders:
        if ph.placeholder_format.type is not None and ph.placeholder_format.idx == 0:
            ph.left, ph.top, ph.width, ph.height = Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.8)
            p = ph.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            ph.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    title = prs.slide_layouts[0]
    for ph in title.placeholders:
        if ph.placeholder_format.idx == 0:
            ph.left, ph.top, ph.width, ph.height = Inches(0.8), Inches(2.3), Inches(11.7), Inches(1.6)
        elif ph.placeholder_format.idx == 1:
            ph.left, ph.top, ph.width, ph.height = Inches(0.8), Inches(4.1), Inches(11.7), Inches(1.2)


def set_run(run, size, bold=False, color=INK, italic=False):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.theme_color = color


def write(tf, lines, size, color=INK, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
          margin=0.06, space_after=0):
    """lines: str or list of str / (str, {size, bold, color, italic}) tuples, one paragraph each."""
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    if isinstance(lines, (str, tuple)):
        lines = [lines]
    for i, line in enumerate(lines):
        text, opt = (line, {}) if isinstance(line, str) else line
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(space_after)
        r = p.add_run()
        r.text = text
        set_run(r, opt.get("size", size), opt.get("bold", bold), opt.get("color", color), opt.get("italic", False))


def title(slide, text):
    slide.shapes.title.text = text
    p = slide.shapes.title.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    for r in p.runs:
        set_run(r, 30, True, DARK)


def node(slide, kind, x, y, w, h, lines, fill=PIPE, size=13, text_color=PAPER, name=None, outline=None,
         bold=False, align=PP_ALIGN.CENTER):
    """A flowchart shape; x, y are its top-left corner in inches."""
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    flat(shp)
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.theme_color = fill
    if outline is None:
        shp.line.fill.background()
    else:
        shp.line.color.theme_color = outline
        shp.line.width = Pt(1.25)
    write(shp.text_frame, lines, size, text_color, bold=bold, align=align)
    if name:
        shp.name = name
    return shp


def note(slide, x, y, w, h, lines, size=12, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, bold=False,
         space_after=4):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    write(tb.text_frame, lines, size, color, bold=bold, align=align, anchor=anchor, margin=0, space_after=space_after)
    return tb


def band(slide, x, y, w, h, label, color=LIGHT, label_color=EXIST, label_bottom=False):
    """A lane: light background rectangle with a small label in its top-left corner."""
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    flat(shp)
    shp.fill.solid()
    shp.fill.fore_color.theme_color = color
    shp.line.fill.background()
    shp.name = f"Lane: {label}"
    ly = y + h - 0.36 if label_bottom else y + 0.06
    note(slide, x + 0.12, ly, w - 0.24, 0.3, (label, {"bold": True}), size=12, color=label_color)
    return shp


def flat(shp):
    """Drop the theme's inherited shadow and bevel so shapes render flat."""
    shp.shadow.inherit = False
    style = shp._element.find(qn("p:style"))
    if style is not None:
        style.find(qn("a:effectRef")).set("idx", "0")
        style.find(qn("a:fillRef")).set("idx", "1")


def _site_xy(shp, site):
    x, y, w, h = shp.left, shp.top, shp.width, shp.height
    return {TOP: (x + w // 2, y), LEFT: (x, y + h // 2), BOTTOM: (x + w // 2, y + h), RIGHT: (x + w, y + h // 2)}[site]


def link(slide, a, a_site, b, b_site, kind="straight", color=INK, label=None, label_dx=0.0, label_dy=0.0,
         dashed=False, arrow="end", width=1.75, label_w=1.2, label_at=None):
    """Glue a connector from shape a (site) to shape b (site).

    kind: 'straight' | 'elbow3' (horizontal, vertical, horizontal) |
          'elbow2' (one bend: leaves a horizontally, arrives at b vertically).
    arrow: 'end' | 'start' | 'none' | 'both'
    """
    ctype = MSO_CONNECTOR.STRAIGHT if kind == "straight" else MSO_CONNECTOR.ELBOW
    ax, ay = _site_xy(a, a_site)
    bx, by = _site_xy(b, b_site)
    c = slide.shapes.add_connector(ctype, ax, ay, bx, by)
    c.begin_connect(a, a_site)
    c.end_connect(b, b_site)
    if kind == "elbow2":
        c._element.spPr.find(qn("a:prstGeom")).set("prst", "bentConnector2")
    c.line.color.theme_color = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    if dashed:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    if arrow in ("start", "both"):
        etree.SubElement(ln, qn("a:headEnd")).attrib.update({"type": "triangle", "w": "med", "len": "med"})
    if arrow in ("end", "both"):
        etree.SubElement(ln, qn("a:tailEnd")).attrib.update({"type": "triangle", "w": "med", "len": "med"})
    if label:
        mx = (Emu(ax).inches + Emu(bx).inches) / 2 + label_dx
        my = (Emu(ay).inches + Emu(by).inches) / 2 + label_dy
        if label_at:
            mx, my = label_at
        note(slide, mx - label_w / 2, my - 0.14, label_w, 0.28, label, size=11, color=color, align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE, bold=True)
    return c


def new_slide(prs, heading):
    s = prs.slides.add_slide(prs.slide_layouts[5])
    title(s, heading)
    return s


P, D, T, DOC, ALT, PRE, DISK = (
    MSO_SHAPE.FLOWCHART_PROCESS, MSO_SHAPE.FLOWCHART_DECISION, MSO_SHAPE.FLOWCHART_TERMINATOR,
    MSO_SHAPE.FLOWCHART_DOCUMENT, MSO_SHAPE.FLOWCHART_ALTERNATE_PROCESS,
    MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS, MSO_SHAPE.FLOWCHART_MAGNETIC_DISK)


# --------------------------------------------------------------------------- slides
def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[0])
    bg = s.background.fill
    bg.solid()
    bg.fore_color.theme_color = DARK
    s.shapes.title.text = "Training drone teams in parallel"
    for r in s.shapes.title.text_frame.paragraphs[0].runs:
        set_run(r, 44, True, PAPER)
    s.shapes.title.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    sub = s.placeholders[1]
    sub.text = "A proposed Isaac Lab training pipeline for the Strike vs Guard game"
    sub.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for r in sub.text_frame.paragraphs[0].runs:
        set_run(r, 22, False, LIGHT)
    note(s, 0.8, 6.3, 11.7, 0.5,
         "Approach agreed with the owner on 14 November 2026 · nothing in this deck has been built or measured yet",
         size=14, color=LIGHT)


def slide_interface(prs):
    s = new_slide(prs, "The trainer copies the flight stack's interface")
    xs = [0.6, 3.1, 5.6, 8.1, 10.6]
    w, h = 2.1, 0.95
    band(s, 0.35, 1.45, 12.63, 1.75, "Flight stack today (AirStack, unchanged)")
    band(s, 0.35, 3.75, 12.63, 1.75, "Training environment (new, thousands of games at once)", label_color=PIPE,
         label_bottom=True)
    top_txt = ["Team strategy", "Ground controller\n20 commands a second", "Safety filter\nkeeps drones apart",
               "PX4 flight controller\nand Starling", "Position source\n(motion capture today)"]
    bot_txt = ["Policy being trained", "Environment step\n20 steps a second", "Same safety filter,\nwithin each team",
               "Drone response model\nfitted from flight logs", "Simulated position\nwith noise and delay"]
    top = [node(s, P, x, 1.95, w, h, t, fill=EXIST) for x, t in zip(xs, top_txt)]
    bot = [node(s, P, x, 4.0, w, h, t, fill=PIPE) for x, t in zip(xs, bot_txt)]
    for row in (top, bot):
        for a, b in zip(row, row[1:]):
            link(s, a, RIGHT, b, LEFT)
    for a, b in zip(top, bot):
        link(s, a, BOTTOM, b, TOP, dashed=True, color=EXIST, arrow="both", width=1.25)
    note(s, 0.6, 5.8, 12.1, 1.3,
         [("Each training block stands in for the flight block above it.", {"bold": True, "color": DARK}),
          "Both rows carry the same signal from strategy to controller: a velocity (x, y, z) and a yaw rate, in the world frame.",
          "Why: a policy trained against this interface plugs into AirStack without changing what it sends or what it reads."],
         size=14, space_after=5)


def slide_uses(prs):
    s = new_slide(prs, "Four uses, in priority order")
    heads = ["Use", "Trains on", "The policy sends", "When"]
    xs, ws = [0.6, 4.3, 7.35, 10.4], [3.4, 2.75, 2.75, 2.35]
    for x, w, t in zip(xs, ws, heads):
        note(s, x, 1.45, w, 0.35, (t, {"bold": True}), size=14, color=EXIST, align=PP_ALIGN.CENTER)
    rows = [
        ("1  Team strategy", "Guard and Strike teams learn where to go",
         "Tier 1: response model", "Velocity + yaw rate,\n20 a second", "Now (S0 to S5)", PIPE, PIPE),
        ("2  Partner strategies", "NUS or UPenn policies retrained or stress-tested",
         "Tier 1: response model", "Same velocity\ninterface", "After S5", PIPE, PIPE),
        ("3  Flight control", "A policy that replaces PX4's own control loops",
         "Tier 2: rigid body\nwith rotors", "Thrust + body rates", "Set by the S2 result", PIPE, EXIST),
        ("4  Camera-based behaviour", "Policies that read depth images",
         "Tier 2 + depth\nray-casting", "Velocity + yaw rate", "Future, low priority", EXIST, EXIST),
    ]
    y = 1.9
    for head, sub, tier, out, when, fill, fill2 in rows:
        a = node(s, P, xs[0], y, ws[0], 0.95, [(head, {"bold": True, "size": 14}), (sub, {"size": 11})], fill=fill)
        b = node(s, P, xs[1], y, ws[1], 0.95, tier, fill=None, outline=fill, text_color=INK)
        c = node(s, P, xs[2], y, ws[2], 0.95, out, fill=None, outline=fill, text_color=INK)
        d = node(s, T, xs[3], y + 0.12, ws[3], 0.71, when, fill=fill2, size=12)
        link(s, a, RIGHT, b, LEFT)
        link(s, b, RIGHT, c, LEFT)
        link(s, c, RIGHT, d, LEFT)
        y += 1.15
    note(s, 0.6, 6.55, 12.1, 0.5,
         "One game, one safety filter and one set of gates serve all four. Uses 3 and 4 are why tier 2 exists beyond the cross-check.",
         size=13, color=DARK, bold=True)


def slide_overview(prs):
    s = new_slide(prs, "Seven stages, from flight logs to a real flight")
    band(s, 0.35, 1.5, 9.05, 3.3, "Training pipeline: the new svg_training folder", label_color=PIPE)
    band(s, 9.5, 1.5, 1.72, 3.3, "AirStack simulator")
    band(s, 11.32, 1.5, 1.66, 3.3, "Flight lab")
    w, h, gap = 1.5, 1.2, 0.3
    x0 = 0.5
    stages = [
        ("1  Identify", "Fit the drone's response to a velocity command", PIPE),
        ("2  Train", "Play thousands of games at once on the GPU", PIPE),
        ("3  Evaluate", "Score against fixed opponents and gates", PIPE),
        ("4  Cross-check", "Replay on a full rigid-body Starling", PIPE),
        ("5  Export", "Policy file plus interface file", PIPE),
        ("6  Simulated flight", "Real PX4 software, up to 3 drones", EXIST),
        ("7  Real flight", "Crazyflies first, then Starlings", EXIST),
    ]
    boxes = []
    for i, (head, body, fill) in enumerate(stages):
        x = x0 + i * (w + gap)
        boxes.append(node(s, P, x, 2.15, w, h, [(head, {"bold": True, "size": 14})], fill=fill))
        note(s, x, 3.5, w, 1.4, body, size=12, align=PP_ALIGN.CENTER)
    for a, b in zip(boxes, boxes[1:]):
        link(s, a, RIGHT, b, LEFT)
    note(s, 0.6, 5.15, 12.1, 1.5,
         [("Stages 1 to 5 live in the new folder and touch nothing else.", {"bold": True}),
          "Stages 6 and 7 use the existing AirStack simulator and flight procedures as they are; "
          "the pipeline only hands them a policy file and an interface file."],
         size=14, color=DARK)


def slide_gates(prs):
    s = new_slide(prs, "Each stage has a gate, and a failed gate sends work back")
    pw, ph, dw, dh, gap = 1.7, 0.9, 1.7, 1.1, 0.4
    x = [0.57]
    for wd in (pw, pw, dw, pw, dw):
        x.append(x[-1] + wd + gap)
    ya = 1.5   # row A top for diamonds
    yb = 3.05  # row B top
    yc = 4.35  # row C top (diamond)
    yd = 5.9   # row D top
    band(s, x[5] - 0.2, yb - 0.38, pw + 0.4, 2.98, "AirStack simulator")
    band(s, x[4] - 0.2, yd - 0.38, x[5] + pw + 0.2 - (x[4] - 0.2), 1.45, "Flight lab")

    train = node(s, P, x[0], ya + 0.1, pw, ph, [("2  Train", {"bold": True}), "parallel games"])
    evalu = node(s, P, x[1], ya + 0.1, pw, ph, [("3  Evaluate", {"bold": True}), "fixed test suite"])
    g1 = node(s, D, x[2], ya, dw, dh, "Gates\npassed?", fill=DECIDE, size=12)
    cross = node(s, P, x[3], ya + 0.1, pw, ph, [("4  Cross-check", {"bold": True}), "rigid-body Starling"])
    g2 = node(s, D, x[4], ya, dw, dh, "Gap within\nlimit?", fill=DECIDE, size=12)
    export = node(s, DOC, x[5], ya + 0.1, pw, ph, [("5  Export", {"bold": True}), "policy + interface"])

    revise = node(s, P, x[2], yb, pw, ph, "Revise curriculum,\nreward or opponents", fill=None, outline=PIPE,
                  text_color=INK, size=12)
    refit = node(s, P, x[4], yb, pw, ph, "Refit the drone\nresponse model (1)", fill=None, outline=PIPE,
                 text_color=INK, size=12)
    simfly = node(s, P, x[5], yb, pw, ph, [("6  Simulated flight", {"bold": True}), "PX4 software"], fill=EXIST)
    g3 = node(s, D, x[5], yc, dw, dh, "Matches\ntraining?", fill=DECIDE, size=12)
    real = node(s, P, x[5], yd, pw, ph, [("7  Real flight", {"bold": True}), "existing flight rules"], fill=EXIST)
    done = node(s, T, x[4], yd + 0.1, pw, ph - 0.2, "Video and\nledger row", fill=PASS, size=12)

    link(s, train, RIGHT, evalu, LEFT)
    link(s, evalu, RIGHT, g1, LEFT)
    link(s, g1, RIGHT, cross, LEFT, label="yes", label_dy=-0.17, color=PASS)
    link(s, cross, RIGHT, g2, LEFT)
    link(s, g2, RIGHT, export, LEFT, label="yes", label_dy=-0.17, color=PASS)
    link(s, g1, BOTTOM, revise, TOP, label="no", label_dx=0.25, color=STRIKE)
    link(s, g2, BOTTOM, refit, TOP, label="no", label_dx=0.25, color=STRIKE)
    link(s, revise, LEFT, train, BOTTOM, kind="elbow2", label="retrain", label_dx=-0.35, label_dy=0.33)
    link(s, refit, LEFT, revise, RIGHT, label="new model", label_dy=-0.17)
    link(s, export, BOTTOM, simfly, TOP)
    link(s, simfly, BOTTOM, g3, TOP)
    link(s, g3, BOTTOM, real, TOP, label="yes", label_dx=0.3, color=PASS)
    link(s, g3, LEFT, refit, BOTTOM, kind="elbow2", label="no",
         label_at=(x[5] - 0.3, yc + dh / 2 - 0.17), color=STRIKE)
    link(s, real, LEFT, done, RIGHT)

    note(s, 0.57, 4.5, 6.7, 2.4,
         [("How to read it", {"bold": True, "size": 14, "color": DARK}),
          "Gates are numbers written down before a run and never moved afterwards.",
          "A failed training gate changes the training set-up. A failed cross-check or a mismatch in the "
          "AirStack simulator means the drone model is wrong, so it is refitted.",
          "Solid teal = new pipeline. Grey = existing AirStack and flight procedures, unchanged."],
         size=12, space_after=5)


def slide_loop(prs):
    s = new_slide(prs, "Inside one step of the parallel games")
    w, h = 2.3, 0.9
    cx = [0.87, 3.97, 7.07, 10.17]
    yt, yg, ys, yb = 2.05, 1.5, 2.65, 5.0
    obs = node(s, P, cx[0], yt, w, h, "Each drone's view: itself,\ndrones in sight, surroundings")
    guard = node(s, P, cx[1], yg, w, h, [("Guard policy", {"bold": True}), "being trained"], fill=GUARD)
    strike = node(s, P, cx[1], ys, w, h, [("Strike policy", {"bold": True}), "drawn from the pool"], fill=STRIKE)
    cmd = node(s, P, cx[2], yt, w, h, "Velocity command\nfor every drone")
    cbf = node(s, PRE, cx[3], yt, w, h, "Safety filter within\neach team", size=13)
    dyn = node(s, P, cx[3], yb, w, h, "Drone response model:\nPX4 velocity loop + delay")
    rules = node(s, P, cx[2], yb, w, h, "Game rules: contact tag,\nreach the zone, time-out")
    rew = node(s, P, cx[1], yb, w, h, "Rewards for\neach team")
    reset = node(s, P, cx[0], yb, w, h, "Restart finished games\nfrom new positions")
    pool = node(s, DISK, cx[1] + 0.4, 3.82, w - 0.8, 0.78, "Opponent pool", fill=LIGHT, text_color=INK,
                outline=EXIST, size=12)
    arch = node(s, DISK, cx[0] + 0.4, 6.12, w - 0.8, 0.78, "Start archive", fill=LIGHT, text_color=INK,
                outline=EXIST, size=12)

    link(s, obs, RIGHT, guard, LEFT, kind="elbow3")
    link(s, obs, RIGHT, strike, LEFT, kind="elbow3")
    link(s, guard, RIGHT, cmd, LEFT, kind="elbow3")
    link(s, strike, RIGHT, cmd, LEFT, kind="elbow3")
    link(s, cmd, RIGHT, cbf, LEFT)
    link(s, cbf, BOTTOM, dyn, TOP, label="safe command", label_dx=-0.75)
    link(s, dyn, LEFT, rules, RIGHT)
    link(s, rules, LEFT, rew, RIGHT)
    link(s, rew, LEFT, reset, RIGHT)
    link(s, reset, TOP, obs, BOTTOM, label="next step", label_dx=0.62)
    link(s, pool, TOP, strike, BOTTOM, dashed=True, color=EXIST)
    link(s, arch, TOP, reset, BOTTOM, dashed=True, color=EXIST)
    world = node(s, DISK, cx[3] + 0.4, 6.12, w - 0.8, 0.78, "World shape", fill=LIGHT, text_color=INK,
                 outline=EXIST, size=12)
    link(s, world, TOP, dyn, BOTTOM, dashed=True, color=EXIST)

    note(s, 3.6, 6.05, 6.6, 0.95,
         [("Every box runs once for all games together, as one tensor operation on the GPU.", {"bold": True}),
          "20 steps a second of game time. The same loop trains the Strike team when the roles swap."],
         size=13, color=DARK, space_after=2)


def slide_options(prs):
    s = new_slide(prs, "Three ways to build it; C was chosen")
    cols = [
        ("A  Full physics only", EXIST,
         ["Every drone is a rigid body with rotors in Isaac Lab.",
          "+ Closest to the real airframe",
          "+ Depth cameras available later",
          "– Slowest: 8 bodies per game",
          "– Strategy does not need rotor physics",
          "– Isaac Lab has no PX4-like velocity controller"]),
        ("B  Response model only", EXIST,
         ["Each drone is a point that follows a velocity command the way PX4 does. Plain PyTorch, no Isaac.",
          "+ Fastest and simplest",
          "+ This kind of model has flown through PX4",
          "– No check near tilt and thrust limits",
          "– No camera path, no 3D replay"]),
        ("C  Two tiers, one game  (chosen)", PIPE,
         ["Game, safety filter and rewards written once. Tier 1 = response model for bulk training. "
          "Tier 2 = rigid body in Isaac Lab for the cross-check.",
          "+ Speed of B, check of A",
          "+ Game code testable without Isaac",
          "+ Tier 2 also serves flight control and cameras",
          "– Two drone models to keep in step"]),
    ]
    w, gap, x0 = 3.85, 0.39, 0.5
    for i, (head, fill, lines) in enumerate(cols):
        x = x0 + i * (w + gap)
        node(s, ALT, x, 1.5, w, 0.75, [(head, {"bold": True, "size": 15})], fill=fill)
        card = node(s, P, x, 2.4, w, 3.3, "", fill=LIGHT)
        card.name = f"Option card {head[:1]}"
        note(s, x + 0.2, 2.55, w - 0.4, 3.05,
             [(lines[0], {"size": 14})] + [(t, {"size": 14, "bold": t.startswith("+")}) for t in lines[1:]],
             size=14, space_after=6)
    note(s, 0.5, 5.95, 12.33, 0.9,
         "Why C: published work shows velocity-level policies trained on a fitted response model fly on real PX4 drones, "
         "and a second, heavier simulator is the standard check before hardware.",
         size=14, color=DARK, bold=True)


def slide_opponents(prs):
    s = new_slide(prs, "Who the team practises against, and from where")
    # Opponents
    note(s, 0.6, 1.4, 6.0, 0.35, ("Opponents: one drawn per game", {"bold": True}), size=15, color=DARK)
    src = [("Latest version of the other team", "about 40 % of games", STRIKE),
           ("Earlier saved versions", "about 35 %", STRIKE),
           ("Scripted textbook opponents", "about 25 %", EXIST)]
    boxes = []
    for i, (a, b, fill) in enumerate(src):
        boxes.append(node(s, P, 0.6, 1.9 + i * 1.05, 2.9, 0.85, [(a, {"bold": True, "size": 12}), (b, {"size": 12})],
                          fill=fill))
    games = node(s, PRE, 4.3, 2.95, 2.3, 0.85, "Parallel games")
    score = node(s, P, 7.4, 2.95, 2.3, 0.85, "Win rate against\neach opponent")
    weights = node(s, P, 10.4, 2.95, 2.3, 0.85, "Draw hard opponents\nmore often", fill=None, outline=PIPE,
                   text_color=INK)
    for b in boxes:
        link(s, b, RIGHT, games, LEFT, kind="elbow3")
    link(s, games, RIGHT, score, LEFT)
    link(s, score, RIGHT, weights, LEFT)
    # Starts
    note(s, 0.6, 5.1, 6.0, 0.35, ("Starting positions", {"bold": True}), size=15, color=DARK)
    u = node(s, P, 0.6, 5.65, 2.9, 0.85, "Anywhere in the arena,\nany team size")
    a = node(s, DISK, 4.5, 5.6, 1.9, 0.95, "Start archive", fill=LIGHT, text_color=INK, outline=EXIST, size=12)
    r = node(s, P, 7.4, 5.65, 2.3, 0.85, "Restart finished\ngames")
    k = node(s, P, 10.4, 5.65, 2.3, 0.85, "Keep starts won\n50 to 90 % of the time", fill=None, outline=PIPE,
             text_color=INK)
    link(s, u, RIGHT, a, LEFT)
    link(s, a, RIGHT, r, LEFT)
    link(s, r, RIGHT, k, LEFT)
    note(s, 7.4, 1.4, 5.4, 1.3,
         ["Practising only against the newest opponent can go in circles; a mixed pool and textbook opponents guard against that.",
          ],
         size=12)
    note(s, 7.4, 4.3, 5.4, 1.0,
         "Skills trained from fixed starting positions failed outside them. Starts are random from day one, and the "
         "archive keeps the ones that are hard but winnable.",
         size=12)


def slide_worlds(prs):
    s = new_slide(prs, "Games move into realistic environments, one rung at a time")
    rungs = [
        ("E0", "Open arena", "Game rules and contact tags first", PIPE),
        ("E1", "Random blocks and columns", "A new layout every game", PIPE),
        ("E2", "Construction-site world", "The lab's own world, plus random clutter", PIPE),
        ("E3", "More worlds", "Warehouse, hospital, office, city blocks; one held out", EXIST),
        ("E4", "A scanned real place", "Photos or LiDAR turned into a mesh", EXIST),
    ]
    w, gap, x0 = 2.2, 0.31, 0.57
    prev = None
    for i, (tag, head, body, fill) in enumerate(rungs):
        x = x0 + i * (w + gap)
        b = node(s, P, x, 1.6, w, 1.0, [(tag, {"bold": True, "size": 16}), (head, {"size": 13})], fill=fill)
        note(s, x, 2.75, w, 0.9, body, size=12, align=PP_ALIGN.CENTER)
        if prev is not None:
            link(s, prev, RIGHT, b, LEFT)
        prev = b
    note(s, 0.57, 3.85, 12.2, 0.4, ("Does a realistic environment affect training? Yes, in four ways",
                                    {"bold": True}), size=15, color=DARK)
    facts = [
        ("Sight", "Drones lose sight of each other behind structures, so the policy needs memory of where the other team was last seen."),
        ("Cost", "Training needs far more games. A published game with a few columns took over 2 billion samples."),
        ("Variety", "One site is learnt by heart. Every game draws its own placement and clutter; one world is never trained on."),
        ("Shape, not looks", "Without cameras, only the shape of the world matters. Textures and lighting are dropped."),
    ]
    fw, fgap = 2.83, 0.3
    for i, (head, body) in enumerate(facts):
        x = 0.57 + i * (fw + fgap)
        node(s, ALT, x, 4.4, fw, 0.5, [(head, {"bold": True, "size": 13})], fill=DECIDE)
        note(s, x + 0.05, 5.0, fw - 0.1, 1.5, body, size=12)
    note(s, 0.57, 6.6, 12.2, 0.4,
         "Teal = in the first build (S2 to S4). Grey = afterwards. A camera-ready copy of a scanned place comes with camera-based policies.",
         size=12, color=EXIST)


def slide_shared_world(prs):
    s = new_slide(prs, "One copy of the world serves every game")
    src = node(s, DOC, 0.6, 2.75, 2.5, 1.15, [("Construction-site world", {"bold": True, "size": 13}),
                                               ("546 x 575 m, 5.8 million triangles", {"size": 11})], fill=EXIST)
    prep = node(s, P, 3.75, 2.85, 2.2, 0.95, "Merge, crop,\nsimplify the mesh")
    t1 = node(s, P, 6.7, 1.75, 2.6, 0.95, [("Tier 1", {"bold": True}), "bake one distance field"])
    t2 = node(s, P, 6.7, 3.95, 2.6, 0.95, [("Tier 2", {"bold": True}), "one static collision mesh"])
    g1 = node(s, PRE, 10.1, 1.75, 2.6, 0.95, "Thousands of games\nlook up the same field")
    g2 = node(s, PRE, 10.1, 3.95, 2.6, 0.95, "Games share the mesh;\ndrones of other games ignored")
    link(s, src, RIGHT, prep, LEFT)
    link(s, prep, RIGHT, t1, LEFT, kind="elbow3")
    link(s, prep, RIGHT, t2, LEFT, kind="elbow3")
    link(s, t1, RIGHT, g1, LEFT)
    link(s, t2, RIGHT, g2, LEFT)
    per = node(s, P, 10.1, 2.9, 2.6, 0.75, "Per game: its own placement,\nstarts and clutter", fill=None,
               outline=PIPE, text_color=INK, size=12)
    link(s, per, TOP, g1, BOTTOM, dashed=True, color=EXIST)
    link(s, per, BOTTOM, g2, TOP, dashed=True, color=EXIST)
    note(s, 0.6, 5.3, 12.1, 1.7,
         [("Why one copy", {"bold": True, "size": 14, "color": DARK}),
          "A distance field answers three questions with one look-up each: has a drone touched a structure, how far is the nearest surface along a ray, can two drones see each other.",
          "Both tiers start from the same world file, so they cannot drift apart. The world is read, never changed.",
          "To be measured: tier 2 may need several copies of the world when thousands of games overlap in one place."],
         size=12, space_after=4)


def slide_contact(prs):
    s = new_slide(prs, "A tag is physical contact; S2 tests the control level")
    m = node(s, P, 0.6, 1.75, 2.5, 1.0, [("S2", {"bold": True}), "measure the tag rate with\nvelocity commands"])
    d = node(s, D, 3.8, 1.6, 2.2, 1.3, "Tag rate\nabove its gate?", fill=DECIDE, size=12)
    keep = node(s, P, 6.9, 1.75, 2.7, 1.0, "Strategy and tagging both\nat velocity level", fill=PASS)
    add = node(s, P, 3.55, 3.6, 2.7, 1.0, "Add a final-approach skill:\nthrust and body rates, tier 2",
               fill=None, outline=PIPE, text_color=INK)
    use3 = node(s, T, 6.9, 3.72, 2.7, 0.76, "Flight control (use 3)\nmoves forward", fill=EXIST, size=12)
    link(s, m, RIGHT, d, LEFT)
    link(s, d, RIGHT, keep, LEFT, label="yes", label_dy=-0.17, color=PASS)
    link(s, d, BOTTOM, add, TOP, label="no", label_dx=0.25, color=STRIKE)
    link(s, add, RIGHT, use3, LEFT)
    note(s, 10.0, 1.6, 2.8, 3.0,
         [("Published evidence", {"bold": True, "color": DARK, "size": 13}),
          "In one study, velocity-commanded drones caught an agile drone in 17.7 % of games; thrust-and-body-rate ones in 88.4 %.",
          "It did not use PX4 at 20 commands a second, so the size of the effect here is unknown."],
         size=12, space_after=5)
    cols = [
        ("In the game", ["Contact = centres closer than 0.50 m (twice the Starling's 0.25 m enclosing radius).",
                         "No tag radius."]),
        ("Safety filter", ["Acts between drones of the same team only.",
                           "A drone that touches a structure leaves the game."]),
        ("Before a real flight", ["Today's flight filter keeps every pair of drones apart; it needs a pair mask (CMU).",
                                  "Published real flights use a virtual contact distance, not impact."]),
    ]
    cw, cg = 3.85, 0.39
    for i, (head, lines) in enumerate(cols):
        x = 0.5 + i * (cw + cg)
        node(s, ALT, x, 4.95, cw, 0.45, [(head, {"bold": True, "size": 13})], fill=EXIST)
        note(s, x + 0.1, 5.5, cw - 0.2, 1.5, lines, size=12, space_after=3)


def slide_build(prs):
    s = new_slide(prs, "Build order: measure first, then grow the game")
    steps = [
        ("S0", "Measure", "Games per second against number of games, with and without obstacles"),
        ("S1", "Drone model", "Fitted to velocity steps; error against PX4 simulator within a stated limit"),
        ("S2", "1 against 1", "Open arena; contact tags against scripted Strike drones, at a rate set beforehand"),
        ("S3", "2 against 1", "Random blocks and columns; holds the zone from any start and layout"),
        ("S4", "5 against 3", "Construction-site world; drop-outs; rigid-body cross-check"),
        ("S5", "Hand-over", "Policy and interface file flown in the AirStack simulator"),
    ]
    w, gap, x0 = 1.8, 0.3, 0.57
    prev = None
    for i, (tag, head, body) in enumerate(steps):
        x = x0 + i * (w + gap)
        b = node(s, P, x, 1.8, w, 1.0, [(tag, {"bold": True, "size": 16}), (head, {"size": 13})],
                 fill=PIPE if i < 5 else EXIST)
        note(s, x, 3.0, w, 1.9, body, size=12, align=PP_ALIGN.CENTER)
        if prev is not None:
            link(s, prev, RIGHT, b, LEFT)
        prev = b
    note(s, 0.57, 4.6, 12.2, 2.0,
         [("Each step ends on a number, not on \"it runs\".", {"bold": True, "size": 14, "color": DARK}),
          "S0 comes first because no published games-per-second figure exists for Isaac Lab quadrotor teams; the answer decides how training is split between the two tiers.",
          "S2 also answers whether velocity commands are fast enough for a contact tag.",
          "S5 needs a small ROS 2 node inside the AirStack tree. That is outside the new folder and needs separate approval.",
          "S0 to S5 deliver use 1 (team strategy). Partner strategies, flight control and cameras follow in that order."],
         size=13, space_after=5)


def slide_decisions(prs):
    s = new_slide(prs, "Decided on 14 November 2026, and still open")
    rows = [
        ("1", "What it is for", "Team strategy, partner strategies, flight control; cameras later."),
        ("2", "How it is built", "Two tiers sharing one game, safety filter and reward code."),
        ("3", "Which Isaac Lab", "2.3.2 on Isaac Sim 5.1 now; 3.0 later on the training workstations."),
        ("4", "Where it lives", "svg_training, a new folder; nothing outside it is edited."),
        ("5", "What a tag is", "Physical contact between a Guard drone and a Strike drone; no tag radius."),
        ("6", "Safety filter", "Acts between drones of the same team only."),
        ("7", "Where games are played", "Realistic 3D environments; the construction-site world first."),
    ]
    y = 1.45
    for num, head, body in rows:
        node(s, MSO_SHAPE.FLOWCHART_CONNECTOR, 0.6, y + 0.04, 0.46, 0.46, [(num, {"bold": True, "size": 13})],
             fill=PIPE)
        note(s, 1.3, y, 3.2, 0.54, (head, {"bold": True}), size=15, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
        note(s, 4.6, y, 8.1, 0.54, body, size=14, anchor=MSO_ANCHOR.MIDDLE)
        y += 0.6
    note(s, 0.6, 5.8, 12.1, 1.3,
         [("Still open", {"bold": True, "color": DARK, "size": 14}),
          "After a tag, does the Guard drone also leave the game · the zone's size and place in each world · "
          "what the real drone senses its surroundings with · the licence of the construction-site asset · "
          "a pair mask in CMU's safety filter before any contact policy can fly."],
         size=13, space_after=3)


def main(out):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    apply_theme(prs)
    style_layouts(prs)
    slide_title(prs)
    slide_interface(prs)
    slide_uses(prs)
    slide_overview(prs)
    slide_gates(prs)
    slide_loop(prs)
    slide_options(prs)
    slide_opponents(prs)
    slide_worlds(prs)
    slide_shared_world(prs)
    slide_contact(prs)
    slide_build(prs)
    slide_decisions(prs)
    prs.core_properties.title = "Training drone teams in parallel: proposed Isaac Lab pipeline"
    prs.core_properties.author = "NEAR Lab, ST Engineering"
    prs.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1])
