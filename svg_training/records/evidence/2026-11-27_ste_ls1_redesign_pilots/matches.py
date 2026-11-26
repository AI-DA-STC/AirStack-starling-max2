"""4.3 'matches B' rule on the control arms: pooled R5 and R7 (max over active channels; per channel pooled over rounds
0 and 3 by row counts), plus r2 (bias) and r3 (turn) per round where B meets them."""
import json, math
def load(t): return json.load(open(f"s1/{t}.json"))
def pooled(m, key):
    n0, n3 = m["0"]["rows"], m["3"]["rows"]
    return max(math.sqrt((n0 * a * a + n3 * b * b) / (n0 + n3)) for a, b in zip(m["0"][key], m["3"][key]))
def joint_marks(tag, sk):
    return load(tag)["marks"][sk]
R2 = {"strike": 0.005, "guard": 0.003}
rows = []
for side, sks in (("strike", ["strike_high", "strike_flank"]), ("guard", ["guard_mirror", "guard_field"])):
    for sk in sks:
        b = load(f"B_{sk}")["marks"]
        B5, B7 = pooled(b, "r5_rmse_debiased"), pooled(b, "r7_rmse")
        counts = B7 <= 0.030
        for arm, m in (("C-in", load(f"Cin_{sk}")["marks"]), ("C-lr", load(f"Clr_{sk}")["marks"]),
                       ("C-head", joint_marks(f"Chead_{side}", sk)), ("C-one", joint_marks(f"Cone_{side}", sk))):
            A5, A7 = pooled(m, "r5_rmse_debiased"), pooled(m, "r7_rmse")
            ok57 = A5 <= max(1.2 * B5, B5 + 0.002) and A7 <= max(1.2 * B7, B7 + 0.002)
            ok23 = True
            for r in ("0", "3"):
                if max(abs(x) for x in b[r]["r2_bias"]) <= R2[side] and max(abs(x) for x in m[r]["r2_bias"]) > R2[side]: ok23 = False
                if abs(b[r]["r3_turn_deg"]) <= 0.5 and abs(m[r]["r3_turn_deg"]) > 0.5: ok23 = False
            call = ("matches" if ok57 and ok23 else "misses") if counts else "not counted (B misses r7)"
            rows.append((side, sk, arm, B5, B7, A5, A7, call))
            print(f"{side:6s} {sk:16s} {arm:6s} B R5 {B5:.4f} R7 {B7:.4f} | arm R5 {A5:.4f} R7 {A7:.4f} -> {call}")
json.dump(rows, open("matches.json", "w"), indent=1)
