#!/usr/bin/env python3
"""Draw the learned-skills route deck: high-level flowcharts of the STE learning track's third route.

Writes ``ste_learning/figures/learned_skills_route.pptx`` (native PowerPoint flowchart shapes; arrows are connectors
glued to the shapes, so they follow a box moved in PowerPoint). With ``--png`` it also renders every flowchart slide
to ``ste_learning/figures/ls_*.png`` through LibreOffice and pdftoppm, for the pages that show them on GitHub.

The drawing helpers and the palette are those of ``docs/pipeline/build_deck.py`` (the pipeline deck), loaded from
that file, so both decks look the same and are edited the same way.

Usage, from ``svg_training/``:
    python3 scripts/make_ste_learned_skills_deck.py            # the .pptx only
    python3 scripts/make_ste_learned_skills_deck.py --png      # the .pptx and the PNG renders

The content follows ``ste_learning/LEARNED_SKILLS_ROUTE.md`` and ``ste_learning/drafts/LS_EXECUTION_WORKFLOW.md`` (v3,
rulings R39 to R45); LS1's stop (R49, 26 Nov 2026) and its redesign follow ``ste_learning/drafts/LS1_REDESIGN.md``. Slides 8 and 9 (what a useful policy still needs; where it stands) are not rendered to PNG: the page
carries them as tables.
"""
import argparse
import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from lxml import etree
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "ste_learning" / "figures"
DECK = OUT_DIR / "learned_skills_route.pptx"
# slide number (1-based) -> PNG name; slide 1 is the title and is not rendered
PNGS = {2: "ls_architecture.png", 3: "ls_three_routes.png", 4: "ls_four_stages.png", 5: "ls_one_decision.png",
        6: "ls_new_strategy.png", 7: "ls_after_training.png"}

_spec = importlib.util.spec_from_file_location("build_deck", ROOT / "docs" / "pipeline" / "build_deck.py")
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)

P, D, DOC, ALT, PRE, DISK = bd.P, bd.D, bd.DOC, bd.ALT, bd.PRE, bd.DISK
TOP, LEFT, BOTTOM, RIGHT = bd.TOP, bd.LEFT, bd.BOTTOM, bd.RIGHT
LEARN, GUARD, STRIKE, GATE, HAND, PASS = bd.PIPE, bd.GUARD, bd.STRIKE, bd.DECIDE, bd.EXIST, bd.PASS
DARK, LIGHT, INK, PAPER = bd.DARK, bd.LIGHT, bd.INK, bd.PAPER
node, note, band, link, new_slide, set_run = bd.node, bd.note, bd.band, bd.link, bd.new_slide, bd.set_run


def legend(s, y):
    """Colour key: learned (teal) and hand-written (grey) boxes."""
    node(s, P, 0.6, y, 0.32, 0.26, "", fill=LEARN)
    note(s, 1.0, y - 0.03, 1.6, 0.32, "learned", size=12)
    node(s, P, 2.3, y, 0.32, 0.26, "", fill=HAND)
    note(s, 2.7, y - 0.03, 1.8, 0.32, "hand-written", size=12)


# --------------------------------------------------------------------------- slides
def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.background.fill.solid()
    s.background.fill.fore_color.theme_color = DARK
    s.shapes.title.text = "The learned-skills route"
    s.shapes.title.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for r in s.shapes.title.text_frame.paragraphs[0].runs:
        set_run(r, 44, True, PAPER)
    sub = s.placeholders[1]
    sub.text = "Drone teams that learn their own skills and their own team strategy"
    sub.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
    for r in sub.text_frame.paragraphs[0].runs:
        set_run(r, 22, False, LIGHT)
    note(s, 0.8, 6.3, 11.7, 0.5,
         "Third route of the STE learning track · adopted 25 November 2026 · LS1 stopped 26 November 2026, redesign in "
         "trials · nothing flown",
         size=14, color=LIGHT)
    s.notes_slide.notes_text_frame.text = (
        "The STE learning track trains Guard and Strike drone teams for the area-denial game. It has two routes "
        "today: pure RL and the skills route. This deck shows the third route, adopted on 25 November 2026: the "
        "drones learn their own skills and their own team strategy, starting from the hand-written ones. A skill "
        "network is the learned part that flies any skill from a skill code (first design: one per team; redesign: "
        "one small network per skill); PPO is the "
        "reinforcement-learning method; tier 1 is the fast training engine and tier 2 the Isaac Lab drone. The aim is "
        "a policy that is useful on the drones, not a pipeline check. The route has no GPU-hour cap, by decision; the settings file still carries 200 GPU-h for it because the launcher needs a number, each job is stopped at its own stated ask, and a single job above 5 GPU-h is announced before launch. The LS1 build was merged on 26 November 2026. Its first copy did not pass "
        "the copy check on either team, so LS1 was stopped on 26 November 2026 (R49) and a redesign of the skill network "
        "is planned as CPU trials, its first stage on hold. Nothing has been flown.")



def poly(s, pts, color=INK, dashed=False, arrow=True, width=1.75, name=None):
    """A free-form arrow through points (inches); for loops and bypasses a glued connector cannot route."""
    ff = s.shapes.build_freeform(Inches(pts[0][0]), Inches(pts[0][1]), scale=1.0)
    ff.add_line_segments([(Inches(x), Inches(y)) for x, y in pts[1:]], close=False)
    shp = ff.convert_to_shape()
    shp.fill.background()
    shp.line.color.theme_color = color
    shp.line.width = Pt(width)
    shp.shadow.inherit = False
    ln = shp.line._get_or_add_ln()
    if dashed:
        etree.SubElement(ln, qn("a:prstDash")).set("val", "dash")
    if arrow:
        etree.SubElement(ln, qn("a:tailEnd")).attrib.update({"type": "triangle", "w": "med", "len": "med"})
    if name:
        shp.name = name
    return shp


def label(s, x, y, w, text, color=INK, align=PP_ALIGN.LEFT):
    return note(s, x, y, w, 0.28, (text, {"bold": True}), size=11, color=color, align=align, anchor=MSO_ANCHOR.MIDDLE)


def slide_architecture(prs):
    """The whole route on one slide: every game (top band), training only (middle), after training (bottom)."""
    s = new_slide(prs, "Strategy architecture at a glance")
    band(s, 0.45, 1.25, 12.45, 2.75, "Every game, in training and after", label_bottom=True)
    band(s, 0.45, 4.1, 12.45, 1.3, "Training only")
    band(s, 0.45, 5.5, 12.45, 1.15, "After training", label_bottom=True)
    # every game: see -> decide -> fly -> stay safe -> play
    obs = node(s, P, 0.6, 1.75, 2.0, 1.7, [("What each drone sees", {"bold": True}), "itself, team-mates,",
                                           "opponents, zone, clock"], fill=HAND, size=12, name="obs")
    heads = node(s, P, 3.0, 2.55, 2.4, 1.0, [("Heads, every 0.6 s", {"bold": True}), "team strategy for all, or",
                                             "\"free\": each drone picks"], fill=LEARN, size=12, name="heads")
    net = node(s, P, 6.2, 2.55, 2.2, 1.0, [("Skill network", {"bold": True}), "flies the chosen skill:",
                                           "a velocity every 0.05 s"], fill=LEARN, size=12, name="skill_net",
               outline=GATE)
    net.line.width = Pt(4)
    opp = node(s, DISK, 8.8, 1.62, 1.9, 0.72, [("Opponent team", {"bold": True}), "scripts; later: saved teams"],
               fill=HAND, size=11, name="opponents")
    filt = node(s, P, 8.8, 2.55, 1.9, 1.0, [("Safety filter", {"bold": True}), "keeps every pair", "of drones apart"],
                fill=HAND, size=12, name="filter")
    game = node(s, P, 11.0, 2.55, 1.8, 1.0, [("Game step", {"bold": True}), "tags, zone, clock"], fill=HAND, size=12,
                name="game")
    link(s, obs, RIGHT, heads, LEFT, kind="elbow3")
    link(s, heads, RIGHT, net, LEFT)
    label(s, 5.42, 3.12, 0.78, "code", align=PP_ALIGN.CENTER)
    link(s, net, RIGHT, filt, LEFT)
    link(s, filt, RIGHT, game, LEFT)
    link(s, opp, BOTTOM, filt, TOP)
    poly(s, [(2.6, 1.98), (7.3, 1.98), (7.3, 2.55)], name="obs to skill network")
    label(s, 3.0, 2.02, 3.2, "what it sees + which drone it is, every tick")
    poly(s, [(11.9, 2.55), (11.9, 1.45), (1.6, 1.45), (1.6, 1.75)], name="next tick")
    label(s, 3.0, 1.5, 2.4, "next observation, every tick")
    # training only: score and learn
    scripts = node(s, PRE, 0.6, 4.5, 2.0, 0.78, [("Teacher scripts", {"bold": True}), "hand-written skills"],
                   fill=HAND, size=12, name="teacher scripts")
    learn = node(s, P, 3.0, 4.45, 5.4, 0.85,
                 [("Learning step", {"bold": True}),
                  "LS1 copies the scripts (stopped; redesign planned);",
                  "then heads, later skills: PPO"],
                 fill=LEARN, size=12, name="learning step")
    out = node(s, P, 11.0, 4.45, 1.8, 0.85, [("Outcome", {"bold": True}), "reward"], fill=HAND, size=12,
               name="outcome")
    link(s, scripts, RIGHT, learn, LEFT, dashed=True, color=HAND)
    link(s, game, BOTTOM, out, TOP)
    link(s, out, LEFT, learn, RIGHT, label="zone held or reached", label_at=(9.7, 4.68), label_w=2.0)
    poly(s, [(4.2, 4.45), (4.2, 3.55)], name="updates the heads")
    poly(s, [(7.3, 4.45), (7.3, 3.55)], name="updates the skills")
    label(s, 4.3, 3.82, 1.6, "updates choices")
    label(s, 7.4, 3.82, 1.4, "updates skills")
    # after training: one export per team
    gate = node(s, D, 5.42, 5.82, 0.56, 0.52, "", fill=GATE, name="gates")
    link(s, learn, BOTTOM, gate, TOP)
    label(s, 5.85, 5.48, 2.4, "each team's gates pass")
    guard = node(s, DOC, 2.75, 5.72, 2.3, 0.78, [("Guard team export", {"bold": True}), "heads + skill network"],
                 fill=GUARD, size=12, name="guard export")
    strike = node(s, DOC, 6.35, 5.72, 2.3, 0.78, [("Strike team export", {"bold": True}), "heads + skill network"],
                  fill=STRIKE, size=12, name="strike export")
    link(s, gate, LEFT, guard, RIGHT)
    link(s, gate, RIGHT, strike, LEFT)
    note(s, 9.0, 5.6, 3.8, 0.95, ["Each export: network files + a settings file;",
                                  "any opponent can face it. Real flight needs",
                                  "a separate approval. LS1 built, then stopped:",
                                  "nothing exported or flown yet."],
         size=12, space_after=0)
    legend(s, 6.82)
    note(s, 4.3, 6.7, 8.6, 0.5, ["Blue: Guard team · red: Strike team · amber: gate · dashed: teaching, in training only",
                                 "Amber outline: being redesigned (LS1 stopped 26 Nov 2026; one small network per skill; trials not started)"],
         size=12, space_after=0)
    s.notes_slide.notes_text_frame.text = (
        "Read from top left to bottom right. The top band runs in every game, in training and after it. Each drone "
        "sees itself, its team-mates, the opponents, the zone and the clock. Every 0.6 seconds the heads decide: the "
        "team head (the lowest-index live drone's choice counts for the team) picks a named team strategy for all "
        "drones, or 'free', in which case each drone's own head picks a skill. Either way every drone gets a skill "
        "code, held for 0.6 seconds. Every tick, 0.05 seconds, the skill network turns what the drone sees, which "
        "drone it is and its code into a velocity. The hand-written safety filter keeps every pair of drones apart, "
        "the opponents' too, and the game step applies tags, the zone and the clock; the next observation starts "
        "the next tick. The middle band exists only in training. In LS1 the learning step copies the hand-written "
        "scripts into the skill network with a supervised fit; the head training that follows, and LS2 and later, "
        "use reinforcement learning (PPO) on the game's reward, with a tie that keeps each skill near its script "
        "in LS2. It updates the heads' choices from the head training on and the skills from LS2; self-play adds "
        "saved teams as opponents, and LS3, last, adds new skill codes with no script. The bottom "
        "band is what comes out: when each team's gates pass, each team is exported on its own, heads plus skill "
        "network, and any opponent that obeys the game's rules can face it. Real flight needs a separate approval. "
        "The skill network has an amber outline: the first design, one network per team, did not pass LS1's copy check "
        "on either team, LS1 was stopped on 26 November 2026 (R49), and a redesign with one small network per skill, "
        "each in its own frame, is planned as CPU trials before any build; the trials have not started. Nothing has been exported or flown.")


def slide_routes(prs):
    s = new_slide(prs, "Three routes, one game")
    lanes = [("Pure RL (velocity route; built, L3)", 1.3), ("Skills route (built, L3)", 2.95), ("Learned-skills route (new)", 4.6)]
    for label, y in lanes:
        band(s, 0.45, y, 9.55, 1.5, label)
    w, h = 2.0, 0.8
    cx = [0.75, 3.05, 5.35, 7.65]
    ys = [y + 0.55 for _, y in lanes]
    cmds = []
    # lane 1
    a = node(s, P, cx[0], ys[0], w, h, "What each drone sees", fill=HAND)
    b = node(s, P, cx[1], ys[0], w * 2 + 0.3, h, [("Policy network", {"bold": True}), "outputs a velocity"],
             fill=LEARN)
    c = node(s, P, cx[3], ys[0], w, h, "Velocity command", fill=HAND)
    link(s, a, RIGHT, b, LEFT)
    link(s, b, RIGHT, c, LEFT)
    cmds.append(c)
    # lane 2
    a = node(s, P, cx[0], ys[1], w, h, "What each drone sees", fill=HAND)
    b = node(s, P, cx[1], ys[1], w, h, [("Team head + drone heads", {"bold": True}), "every 0.6 s"], fill=LEARN,
             size=12)
    k = node(s, PRE, cx[2], ys[1], w, h, [("Hand-written scripts", {"bold": True}), "one of K flies"], fill=HAND,
             size=12)
    c = node(s, P, cx[3], ys[1], w, h, "Velocity command", fill=HAND)
    link(s, a, RIGHT, b, LEFT)
    link(s, b, RIGHT, k, LEFT)
    link(s, k, RIGHT, c, LEFT)
    cmds.append(c)
    # lane 3
    a = node(s, P, cx[0], ys[2], w, h, "What each drone sees", fill=HAND)
    b = node(s, P, cx[1], ys[2], w, h, [("Team head + drone heads", {"bold": True}), "every 0.6 s"], fill=LEARN,
             size=12)
    k = node(s, P, cx[2], ys[2], w, h, [("Skill network", {"bold": True}), "every 0.05 s"], fill=LEARN, size=12)
    c = node(s, P, cx[3], ys[2], w, h, "Velocity command", fill=HAND)
    link(s, a, RIGHT, b, LEFT)
    link(s, b, RIGHT, k, LEFT)
    link(s, k, RIGHT, c, LEFT)
    cmds.append(c)
    game = node(s, P, 10.4, 2.35, 2.45, 2.7,
                [("Safety filter", {"bold": True}), "on every pair of drones", "",
                 ("Game", {"bold": True}), "tier 1 fast engine,", "tier 2 Isaac Lab"], fill=HAND, size=13)
    for c in cmds:
        link(s, c, RIGHT, game, LEFT, kind="elbow3")
    legend(s, 6.45)
    note(s, 4.8, 6.35, 8.1, 0.6,
         "Same game, filter, scoring and export for all three: only what turns the view into a command changes.",
         size=13, color=DARK, bold=True)
    s.notes_slide.notes_text_frame.text = (
        "All three routes share the game, the safety filter, the scoring and the export. They differ only in what "
        "turns a drone's view into a velocity command. Pure RL: one network outputs the velocity directly. Skills "
        "route: two learned heads choose which hand-written script flies. Learned-skills route: the same heads "
        "choose a skill code, and a learned skill network flies it. Teal is learned, grey is hand-written.")


def slide_stages(prs):
    s = new_slide(prs, "Five steps, each starting from the one before")
    w = 2.0
    xs = [0.45 + i * 2.5 for i in range(5)]
    heads = [("LS1 Distil", "copy the scripts: STOPPED"), ("Head training", "heads on the skill network"),
             ("LS2 Fine-tune", "improve the skills"), ("Self-play", "teams against teams"),
             ("LS3 Free codes", "last: an extension")]
    cards = [
        ["Tried: one skill network per team; 0.17 GPU-h of 0.9 asked",
         "Copy check: NOT DISTILLED on both teams; every control passed",
         "Stopped 26 Nov 2026 (R49); redesigned below"],
        ["Learned: the heads again, on the skill network; both teams",
         "Expected: scores about as the skills route's",
         "Built; waits for LS1 to pass on both teams",
         "Asks 4.0 GPU-h (job group LS1.4)"],
        ["Learned: skills and heads, in turns; a tie keeps each code near its script",
         "Gate: in its note; proposed: above the best fixed mix",
         "Hours: its own note"],
        ["Learned: choices against saved and present teams",
         "Pilot right after head training",
         "Gate: in its note; read on opponents never trained against",
         "Hours: its own note"],
        ["Learned: skill codes with no script",
         "Gate: in its note; proposed: new codes chosen, worst result up",
         "Hours: its own note"],
    ]
    stages = []
    for i, (x, (t, sub), lines) in enumerate(zip(xs, heads, cards)):
        st = node(s, ALT, x, 1.35, w, 0.95, [(t, {"bold": True, "size": 14}), sub], fill=LEARN, size=11,
                  outline=GATE if i == 0 else None)
        if i == 0:
            st.line.width = Pt(4)
        stages.append(st)
        card = node(s, ALT, x, 2.5, w, 2.55, "", fill=LIGHT, text_color=INK)
        card.name = f"Card: {t}"
        note(s, x + 0.1, 2.6, w - 0.2, 2.4, lines, size=11, space_after=5)
    for a, b in zip(stages, stages[1:]):
        mid = (a.left + a.width + b.left) / 2 / 914400
        dm = node(s, D, mid - 0.2, 1.62, 0.4, 0.4, "", fill=GATE)
        link(s, a, RIGHT, dm, LEFT)
        link(s, dm, RIGHT, b, LEFT)
    # the LS1 redesign: CPU trials before any build
    band(s, 0.45, 5.2, 12.45, 1.5, "LS1 redesign: one small network per skill, each in its own frame; CPU trials, no GPU",
         label_bottom=True)
    pw, px = 2.1, [0.6, 3.05, 5.5, 7.95, 10.4]
    pilots = [
        [("Stage 0: ON HOLD", {"bold": True}), "five checks, no training"],
        [("Stage 1", {"bold": True}), "small fits, every skill", "of both teams"],
        [("Stage 2", {"bold": True}), "students replay all 280", "test cells; two seeds"],
        [("Build approval", {"bold": True}), "decided after the trials"],
        [("LS1 again", {"bold": True}), "distil, then the copy check", "of record"],
    ]
    boxes = []
    for i, (x, lines) in enumerate(zip(px, pilots)):
        fill = GATE if i == 3 else PAPER
        color = PAPER if i == 3 else INK
        bx = node(s, ALT, x, 5.3, pw, 0.8, lines, fill=fill, text_color=color, size=11,
                  outline=GATE if i == 0 else DARK, name=f"Pilot: {lines[0][0]}")
        if i == 0:
            bx.line.width = Pt(3)
        boxes.append(bx)
    for a, b in zip(boxes, boxes[1:]):
        link(s, a, RIGHT, b, LEFT)
    poly(s, [(0.45, 3.775), (0.3, 3.775), (0.3, 5.7), (0.6, 5.7)], dashed=True, name="LS1 to its redesign")
    note(s, 0.45, 6.78, 12.4, 0.6,
         ["Gate (amber diamond): pass marks written before the run; a step that fails stops the route there. Amber outline: "
          "stopped or on hold. Solid amber box: a decision, not a trial. Dashed arrow: LS1's redesign.",
          "Hours are asks, not results; no cap, by decision (200 GPU-h in settings). Trials: about 9 to 16.5 CPU-hours "
          "one job at a time (estimate)."],
         size=11, color=DARK, space_after=0)
    s.notes_slide.notes_text_frame.text = (
        "The order is LS1, head training, LS2, self-play, LS3. Each step starts from the behaviour of the one "
        "before, so none starts from random flight. LS1 copies the hand-written scripts into the skill network; its "
        "gate has the copy and the scripts play the same starts and counts the games that change. The first design, "
        "one skill network per team, was built and trained (0.17 of the 0.9 GPU-h asked). Its copy check found it NOT "
        "DISTILLED on both teams while every control passed, so the result is real, and LS1 was stopped on 26 "
        "November 2026 (R49). The lower band is the redesign: one small network per skill, each in the frame of its "
        "drone's line to the zone, with exact zeros for the parked skill and unused controls. It is tried on the CPU "
        "before any build. Stage 0 has five checks and no training, and is on hold. Stage 1 fits every skill of both "
        "teams at small size. Stage 2 has the students replay all 280 test cells against the stored script games; "
        "a design passes only with two training seeds. A pass is a go for the build, decided after the trials; LS1 "
        "then runs again: distil, then the copy check of record. Head training, job group LS1.4, is built and waits "
        "for LS1 to pass on both teams; it asks 4.0 GPU-h. LS2 trains the skills with the game reward while a tie "
        "keeps each skill near its script. Self-play's pilot runs right after head training. LS3, free skill codes, "
        "comes last. The route has no GPU-hour cap, by decision; the settings file carries 200 GPU-h because the "
        "launcher needs a number, and each job is stopped at its own stated ask. The trials need about 9 to 16.5 "
        "CPU-hours one job at a time, an estimate; they use no GPU.")


def slide_decision(prs):
    s = new_slide(prs, "Inside one decision: two speeds")
    band(s, 0.45, 1.25, 12.45, 1.75, "Every 0.6 s (12 ticks): who flies what")
    band(s, 0.45, 3.2, 12.45, 2.35, "Every 0.05 s (one tick): how to fly it", label_bottom=True)
    sees = node(s, P, 0.75, 1.7, 2.45, 1.0, "What each drone sees: its own state, team-mates, opponents, zone",
                fill=HAND, size=12)
    team = node(s, P, 3.75, 1.7, 2.6, 1.0,
                [("Team head", {"bold": True}), "a team strategy, or \"free\""], fill=LEARN, size=13)
    drones = node(s, P, 6.9, 1.7, 2.6, 1.0,
                  [("Drone heads", {"bold": True}), "under \"free\": one skill per drone"], fill=LEARN, size=13)
    net = node(s, P, 6.9, 3.55, 2.6, 1.15,
               [("Skill network", {"bold": True}), "view + drone slot + skill code", "-> velocity"], fill=LEARN,
               size=13)
    scripts = node(s, PRE, 10.15, 3.55, 2.5, 1.15,
                   [("Hand-written scripts", {"bold": True}), "the teachers: copied in LS1, a tie in LS2"],
                   fill=HAND, size=12)
    filt = node(s, P, 3.75, 3.6, 2.6, 1.05, [("Safety filter", {"bold": True}), "every pair"], fill=HAND, size=13)
    game = node(s, P, 0.75, 3.6, 2.45, 1.05, [("Game step", {"bold": True}), "tags, zone, clock"], fill=HAND,
                size=13)
    link(s, sees, RIGHT, team, LEFT)
    link(s, team, RIGHT, drones, LEFT)
    link(s, drones, BOTTOM, net, TOP, label="one code per drone, held 0.6 s", label_dx=1.6, label_w=2.9)
    link(s, scripts, LEFT, net, RIGHT, dashed=True, color=HAND)
    link(s, net, LEFT, filt, RIGHT)
    link(s, filt, LEFT, game, RIGHT)
    link(s, game, TOP, sees, BOTTOM, label="next tick", label_dx=0.6, label_w=1.0)
    note(s, 0.6, 5.75, 12.2, 0.5,
         "The skill code is the only link between the two speeds: the heads choose it, the skill network flies it.",
         size=13, color=DARK, bold=True)
    legend(s, 6.45)
    s.notes_slide.notes_text_frame.text = (
        "Two speeds, as in today's skills route. Every 0.6 seconds the team head picks a team strategy or 'free'; "
        "under 'free' each drone's head picks its own skill. That gives every drone a skill code, held for 12 ticks. "
        "Every tick, the skill network turns the drone's view, its slot in the team and its code into a velocity. "
        "The hand-written scripts are the teachers: copied in LS1, and a tie that keeps each code near its script "
        "in LS2. The safety filter and the game are unchanged.")


def slide_strategy(prs):
    s = new_slide(prs, "How a new team strategy appears")
    w, h = 2.6, 1.05
    a = node(s, P, 0.6, 1.5, w, h, [("Team gives out codes", {"bold": True}), "a pattern over its drones"],
             fill=LEARN, size=13)
    b = node(s, P, 3.85, 1.5, w, h, [("Thousands of games", {"bold": True}), "against opponents that adapt"],
             fill=HAND, size=13)
    c = node(s, P, 3.85, 4.1, w, h, [("Outcome", {"bold": True}), "zone held or reached, tags"], fill=HAND,
             size=13)
    d = node(s, P, 0.6, 4.1, w, h, [("Learning step (PPO)", {"bold": True}), "choices before wins get likelier"],
             fill=LEARN, size=13)
    link(s, a, RIGHT, b, LEFT)
    link(s, b, BOTTOM, c, TOP)
    link(s, c, LEFT, d, RIGHT)
    link(s, d, TOP, a, BOTTOM, label="repeat", label_dx=0.55, label_w=0.9)
    xs, w2 = 7.05, 5.8
    note(s, xs, 1.4, w2, 0.4, ("Three sources of \"new\"", {"bold": True}), size=17, color=DARK)
    items = [
        ("1  A new mix", "two Guards mark, one holds the centre: no script does this"),
        ("2  A new switching rule", "hold the ring while one Strike charges alone; mark when two close in"),
        ("3  New skills, then new roles", "LS2 changes how a skill flies; LS3, last, adds skills no script has"),
    ]
    for i, (t, body) in enumerate(items):
        y = 1.95 + i * 1.22
        node(s, ALT, xs, y, w2, 1.05, "", fill=LIGHT, text_color=INK)
        note(s, xs + 0.2, y + 0.1, w2 - 0.4, 0.9, [(t, {"bold": True, "size": 14}), body], size=13, space_after=2)
    note(s, 0.6, 5.55, 12.2, 0.95,
         ["Seen in the choice logs, clusters of code patterns and clips; named after the fact.",
          "It may not appear: the team can settle on one fixed choice, or beat only its sparring partners. The gates "
          "check both (the best fixed mix of scripts; opponents never trained against)."],
         size=13, color=DARK, space_after=3)
    s.notes_slide.notes_text_frame.text = (
        "Nobody writes the strategy. The team gives out skill codes, thousands of games are played, and the "
        "learning step makes the choices that came before wins more likely. Self-play closes the loop: when one "
        "team finds a pattern that wins, the other team's training adapts to it, which pushes the first team to "
        "something new. A possible example: against a decoy attack, a Guard team that holds its ring while one Strike "
        "charges alone might win more, so that rule could grow; no script says it. A new strategy may also not appear, and the gates "
        "are there to tell.")


def slide_after(prs):
    s = new_slide(prs, "After training: two separate team policies")
    guard = node(s, DOC, 5.15, 1.35, 2.75, 1.05,
                 [("Guard team export", {"bold": True}), "heads + skill network (ONNX)"], fill=GUARD, size=13)
    opp = [("Hand-written Strike script", STRIKE), ("Outside code (package.module:Class)", HAND),
           ("Trained Strike team export", STRIKE), ("Hand-flown drone (flight only)", HAND)]
    nodes = []
    for i, (t, col) in enumerate(opp):
        nodes.append(node(s, P, 0.6, 1.5 + i * 1.08, 3.4, 0.82, t, fill=col, size=13))
    match = node(s, P, 5.15, 3.1, 2.75, 1.25,
                 [("Match", {"bold": True}), "training simulator:", "1,000 games in seconds"], fill=HAND, size=13)
    score = node(s, P, 8.9, 3.1, 2.5, 1.25,
                 [("Score per opponent", {"bold": True}), "hold rate with its interval"], fill=PASS, size=13)
    pool = node(s, DISK, 8.9, 4.95, 2.5, 0.95, "Training pool for the next run", fill=LIGHT, text_color=INK,
                outline=HAND, size=12)
    for n in nodes:
        link(s, n, RIGHT, match, LEFT, kind="elbow3")
    link(s, guard, BOTTOM, match, TOP)
    link(s, match, RIGHT, score, LEFT)
    link(s, score, BOTTOM, pool, TOP, dashed=True, color=HAND, label="an opponent that wins", label_dx=1.2,
         label_w=2.1)
    note(s, 0.6, 6.0, 12.2, 0.95,
         ["The Strike team is exported the same way and is tested against hand-written Guards in the mirror match.",
          "A policy reads only positions and velocities: any player that obeys the game's rules can face it. "
          "Flight is phases L7 and L8, each needing a separate approval; nothing here has flown."],
         size=13, color=DARK, space_after=3)
    s.notes_slide.notes_text_frame.text = (
        "Training gives two separate exports, one per team, each the two heads plus the skill network as ONNX "
        "files. Either can be used alone. A policy reads only positions and velocities, so it does not know what "
        "flies the other team: a hand-written script, outside code, a trained team, or in flight a hand-flown "
        "drone. In the training simulator a match is a thousand games in seconds; an opponent that wins joins the "
        "training pool for the next run. Flight needs a separate approval for each phase.")


def slide_needs(prs):
    s = new_slide(prs, "What a useful policy still needs beyond this route")
    rows = [
        ("Self-play against saved teams", "the opponent pool takes script names only: a pool entry for saved teams is a new build"),
        ("A held-out test", "proposed: new scripts, two per side, written for it: every current Strike script is in the training pool"),
        ("Holding the team plan when a drone is lost", "a shared actor and training at drawn team sizes"),
        ("Training on the Isaac Lab drone (tier 2)", "a separate task: this route trains on the fast engine (tier 1)"),
    ]
    for i, (t, body) in enumerate(rows):
        y = 1.45 + i * 1.15
        node(s, ALT, 0.6, y, 12.1, 0.95, "", fill=LIGHT, text_color=INK)
        note(s, 0.8, y + 0.08, 11.7, 0.85, [(t, {"bold": True, "size": 15}), body], size=14, space_after=2)
    note(s, 0.6, 6.15, 12.1, 0.6,
         "The aim is a policy that is useful on the drones. The route covers the learning; these four items come from "
         "the wider track goal.", size=13, color=DARK, bold=True)
    s.notes_slide.notes_text_frame.text = (
        "Four things a useful policy needs that the route does not give by itself. Self-play needs a pool that can "
        "hold saved teams: today the pool takes script names only, so this is a new build. A held-out test, still only proposed, needs new "
        "scripts written for it, because every current Strike script is in the training pool. Holding the team plan "
        "when a drone is lost needs a shared actor. Training on the Isaac Lab drone, tier 2, is a separate task.")


def slide_status(prs):
    s = new_slide(prs, "Where it stands")
    rows = [
        ("The route", "adopted, 25 November 2026; no GPU-hour cap, by decision; per-job asks"),
        ("The LS1 build", "merged 26 November 2026: skill network, distillation, copy check, export, head training"),
        ("LS1", "first copy NOT DISTILLED on both teams; stopped 26 November 2026 (R49); 0.17 GPU-h used"),
        ("Redesign", "one small network per skill, reviewed; CPU trials before any build; Stage 0 on hold"),
        ("Head training", "built, not started: needs LS1 to pass on both teams"),
        ("Later steps", "LS2, self-play and LS3 each wait for their own design note"),
    ]
    for i, (t, body) in enumerate(rows):
        y = 1.4 + i * 0.82
        node(s, ALT, 0.6, y, 3.2, 0.66, t, fill=LEARN, size=14)
        node(s, ALT, 3.9, y, 8.8, 0.66, body, fill=LIGHT, text_color=INK, size=14)
    note(s, 0.6, 6.4, 12.1, 0.5, "Nothing has been exported or flown.", size=15, color=DARK, bold=True)
    s.notes_slide.notes_text_frame.text = (
        "The route was adopted on 25 November 2026 and has no GPU-hour cap, by decision; each job is stopped at its own "
        "stated ask. The LS1 build was merged on 26 November 2026. The first copy, one skill network per team, used "
        "0.17 GPU-h and was found NOT DISTILLED on both teams by the copy check, with every control passing; LS1 was "
        "stopped the same day (R49). A redesign with one small network per skill is reviewed and is tried on the CPU "
        "before any build; its first stage is on hold. Head training is built and waits for LS1 to pass on both "
        "teams. Nothing has been exported or flown.")


def render_pngs(deck: Path) -> None:
    """deck -> PDF (LibreOffice, headless) -> one PNG per flowchart slide (pdftoppm, 110 dpi)."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, str(deck)], check=True,
                       capture_output=True, timeout=300)
        pdf = Path(tmp) / (deck.stem + ".pdf")
        subprocess.run(["pdftoppm", "-png", "-r", "110", str(pdf), str(Path(tmp) / "s")], check=True, timeout=300)
        for n, name in PNGS.items():
            shutil.copyfile(Path(tmp) / f"s-{n}.png", OUT_DIR / name)
            print("wrote", OUT_DIR / name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--png", action="store_true", help="also render the flowchart slides to PNG (needs soffice)")
    args = ap.parse_args()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(bd.W), Inches(bd.H)
    bd.apply_theme(prs)
    bd.style_layouts(prs)
    slide_title(prs)
    slide_architecture(prs)
    slide_routes(prs)
    slide_stages(prs)
    slide_decision(prs)
    slide_strategy(prs)
    slide_after(prs)
    slide_needs(prs)
    slide_status(prs)
    prs.core_properties.title = "The learned-skills route: drone teams that learn their own skills and team strategy"
    prs.core_properties.author = "NEAR Lab, ST Engineering"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(DECK)
    print("wrote", DECK)
    if args.png:
        render_pngs(DECK)


if __name__ == "__main__":
    main()
