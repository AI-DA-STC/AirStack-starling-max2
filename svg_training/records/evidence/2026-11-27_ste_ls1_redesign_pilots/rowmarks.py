import json
R6 = {"strike_flank": 0.03067, "guard_field": 0.0157, "strike_sacrifice": 0.02091, "strike_converge": 0.0319}
out = []
for t in ["B_guard_parked_ring","B_guard_mark_edge","B_guard_mirror","B_guard_field","B_strike_straight","B_strike_flank","B_strike_high","B_strike_low","A3_strike_sacrifice","A3_strike_converge"]:
    d = json.load(open(f"s1/{t}.json")); sk = d["skill"]; g = sk.startswith("guard")
    miss = []
    for r in ("0", "3"):
        m = d["marks"][r]
        if not m["r1_masked_zero"]: miss.append(f"r1 r{r}")
        if max(abs(x) for x in m["r2_bias"]) > (0.003 if g else 0.005): miss.append(f"r2 r{r} {max(abs(x) for x in m['r2_bias']):.4f}")
        if abs(m["r3_turn_deg"]) > 0.5: miss.append(f"r3 r{r} {m['r3_turn_deg']:.2f}")
        if not 0.99 <= m["r4_scale"] <= 1.01: miss.append(f"r4 r{r} {m['r4_scale']:.4f}")
        if max(m["r5_rmse_debiased"]) > (0.015 if g else 0.010): miss.append(f"r5 r{r} {max(m['r5_rmse_debiased']):.4f}")
        if m["r6_tail"] > R6.get(sk, 0.002): miss.append(f"r6 r{r} {m['r6_tail']:.4f}")
        if max(m["r7_rmse"]) > 0.030: miss.append(f"r7 r{r} {max(m['r7_rmse']):.4f}")
    out.append((sk, d["rung"], miss))
    print(f"| {sk} | {d['rung']} | {'all met' if not miss else '; '.join(miss)} |")
