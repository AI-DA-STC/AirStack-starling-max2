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

The content follows ``ste_learning/LEARNED_SKILLS_ROUTE.md`` and ``ste_learning/drafts/LEARNED_SKILLS_BRIDGE_PLAN.md``.
"""
import argparse
import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "ste_learning" / "figures"
DECK = OUT_DIR / "learned_skills_route.pptx"
# slide number (1-based) -> PNG name; slide 1 is the title and is not rendered
PNGS = {2: "ls_three_routes.png", 3: "ls_four_stages.png", 4: "ls_one_decision.png",
        5: "ls_new_strategy.png", 6: "ls_after_training.png"}

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
         "Third route of the STE learning track · adopted 25 November 2026 · a design: nothing built, trained or flown",
         size=14, color=LIGHT)
    s.notes_slide.notes_text_frame.text = (
        "The STE learning track trains Guard and Strike drone teams for the area-denial game. It has two routes "
        "today: pure RL and the skills route. This deck shows the third route, adopted on 25 November 2026: the "
        "drones learn their own skills and their own team strategy, starting from the hand-written ones. It is a "
        "design; nothing has been built, trained or flown.")


def slide_routes(prs):
    s = new_slide(prs, "Three routes, one game")
    lanes = [("Pure RL (velocity route)", 1.3), ("Skills route (built, L3)", 2.95), ("Learned-skills route (new)", 4.6)]
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
    s = new_slide(prs, "Four stages, each starting from the one before")
    w = 2.65
    xs = [0.5, 3.75, 7.0, 10.25]
    heads = [("LS1 Distil", "copy the scripts"), ("LS2 Fine-tune", "improve the skills"),
             ("LS3 Free codes", "skills no script has"), ("LS4 League", "team strategy emerges")]
    cards = [
        ["Learned: a copy of every script as codes of one network per team",
         "Hand-written: the scripts, as teachers",
         "Gate: plays like the scripts, cell by cell",
         "Estimate: about 1 GPU-h"],
        ["Learned: the choices and the skills",
         "Hand-written: a tie to each script, weakened step by step",
         "Gate: beats the best fixed mix of scripts",
         "Estimate: 5 to 8 GPU-h"],
        ["Learned: new skill codes, rewarded for being distinct and useful",
         "Hand-written: nothing for the new codes",
         "Gate: new codes are chosen and raise the worst cell",
         "Estimate: 10 to 20 GPU-h"],
        ["Learned: which code each drone gets, against past and present opponents",
         "Opponents: scripts, past teams, saved exploits",
         "Gate: the robustness suite",
         "Estimate: open"],
    ]
    stages = []
    for x, (t, sub), lines in zip(xs, heads, cards):
        st = node(s, ALT, x, 1.4, w, 0.95, [(t, {"bold": True, "size": 17}), sub], fill=LEARN, size=13)
        stages.append(st)
        card = node(s, ALT, x, 2.6, w, 3.0, "", fill=LIGHT, text_color=INK)
        card.name = f"Card: {t}"
        note(s, x + 0.15, 2.75, w - 0.3, 2.8, lines, size=13, space_after=8)
    for a, b in zip(stages, stages[1:]):
        mid = (a.left + a.width + b.left) / 2 / 914400
        dm = node(s, D, mid - 0.26, 1.61, 0.52, 0.52, "", fill=GATE)
        link(s, a, RIGHT, dm, LEFT)
        link(s, dm, RIGHT, b, LEFT)
    node(s, D, 0.6, 5.95, 0.32, 0.32, "", fill=GATE)
    note(s, 1.05, 5.9, 11.8, 0.8,
         ["Gate: pass marks written before the run. A stage that fails stops the route there; every stage before it",
          "is still a usable result. Only LS1 is planned task by task; LS2 to LS4 return with their own notes and costs."],
         size=13, color=DARK, space_after=0)
    s.notes_slide.notes_text_frame.text = (
        "Each stage starts from the exact behaviour of the stage before, so no stage starts from random flight. "
        "LS1 copies the hand-written scripts into one skill network per team: same behaviour, but now trainable. "
        "LS2 trains those skills with the game reward while a penalty keeps each skill near its script. LS3 adds "
        "skill codes with no script, rewarded for being distinct and useful. LS4 puts both teams in a league of past "
        "and present opponents, where a team strategy is the pattern of codes the team gives its drones. GPU hours "
        "after LS1 are estimates; LS1 itself is the only stage planned in detail.")


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
    b = node(s, P, 3.85, 1.5, w, h, [("Thousands of games", {"bold": True}), "against a league that adapts"],
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
        ("3  New skills, then new roles", "LS2 changes how a skill flies; LS3 adds skills no script has"),
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
        "learning step makes the choices that came before wins more likely. The league closes the loop: when one "
        "team finds a pattern that wins, the other team's opponents adapt to it, which pushes the first team to "
        "something new. Example: against a decoy attack, a Guard team that holds its ring while one Strike charges "
        "alone wins more, so that rule grows; no script says it. A new strategy may also not appear, and the gates "
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
          "Flight is phases L7 and L8, gated by the owner; nothing here has flown."],
         size=13, color=DARK, space_after=3)
    s.notes_slide.notes_text_frame.text = (
        "Training gives two separate exports, one per team, each the two heads plus the skill network as ONNX "
        "files. Either can be used alone. A policy reads only positions and velocities, so it does not know what "
        "flies the other team: a hand-written script, outside code, a trained team, or in flight a hand-flown "
        "drone. In the training simulator a match is a thousand games in seconds; an opponent that wins joins the "
        "training pool for the next run. Flight stays gated by the owner.")


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
    slide_routes(prs)
    slide_stages(prs)
    slide_decision(prs)
    slide_strategy(prs)
    slide_after(prs)
    prs.core_properties.title = "The learned-skills route: drone teams that learn their own skills and team strategy"
    prs.core_properties.author = "NEAR Lab, ST Engineering"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(DECK)
    print("wrote", DECK)
    if args.png:
        render_pngs(DECK)


if __name__ == "__main__":
    main()
