"""FCS の試験の記録から、撃った瞬間の照準のずれ（試験 E3 と同じ計算）と、標的に当たった数を出す。

使い方：python tools/analyze_fcs_shots.py logs/run-日時   （.jsonl と -addon.jsonl を読む）
前提（test calc のつなぎのマイコン）：入力 ch20 = 砲身の Tilt（回転数）、FCS のデバッグ ch7 = 飛ぶ時間、ch8 = 水平距離、
ch9 = 仰角の解（°）、ch13 = 予測のずれ、on/off ch5 = 射撃可。
撃った瞬間：砲身が 0.15°以上いっぺんに動いた（反動）直前の値。当たった数：標的が傷ついた知らせを、0.5 秒より離れたらまとまりを分けて数える。
"""
import json, math, statistics as st, sys

base = sys.argv[1]
vals = [json.loads(l) for l in open(base + ".jsonl", encoding="utf-8")]
addon = [json.loads(l) for l in open(base + "-addon.jsonl", encoding="utf-8")]
t0 = vals[0]["t"]

# --- shots: barrel kick (E3 method). barrel elevation = ch20 * 360 deg, solution = ch9 deg
KICK = 0.15
shots = []
prev = None
last_kick = -1e9
for r in vals:
    v = r["v"]
    try:
        barrel = float(v[19]) * 360.0
        req = float(v[8])
        rng = float(v[7])
    except (TypeError, ValueError):
        prev = None
        continue
    ready = 5 in r.get("b", [])
    if prev is not None and r["t"] - last_kick > 1.0 and abs(barrel - prev["barrel"]) >= KICK and (prev["ready"] or ready):
        shots.append({"t": prev["t"] - t0, "diff": prev["barrel"] - prev["req"], "req": prev["req"], "range": prev["range"],
                      "pred_miss_m": prev["pred"]})
        last_kick = r["t"]
    prev = {"t": r["t"], "barrel": barrel, "req": req, "range": rng, "ready": ready, "pred": float(v[12])}

print("samples", len(vals), "span", round(vals[-1]["t"] - t0, 1), "s")
print("shots detected (recoil):", len(shots))
if len(shots) >= 2:
    d = [s["diff"] for s in shots]
    rng = st.mean(s["range"] for s in shots)
    print(f"  range mean {rng:.1f} m")
    print(f"  DIFF mean {st.mean(d):+.4f} deg  SD {st.stdev(d):.4f} deg  -> at target: mean {rng*math.radians(st.mean(d)):+.2f} m, SD {rng*math.radians(st.stdev(d)):.2f} m")
    print(f"  REQ SD {st.stdev(s['req'] for s in shots):.4f} deg")
    print("  first shots:", [(round(s["t"], 1), round(s["diff"], 3)) for s in shots[:12]])

# --- hits: damage events to the target, clustered in time
ev = []
for r in addon:
    for d in r.get("dmg", []):
        ev.append((r["t"] - t0, d))
ev.sort(key=lambda x: x[0])
clusters = []
for t, d in ev:
    if clusters and t - clusters[-1]["t1"] <= 0.5:
        c = clusters[-1]
        c["t1"] = t
        c["n"] += 1
        c["vox"].append(d["voxel"])
    else:
        clusters.append({"t0": t, "t1": t, "n": 1, "vox": [d["voxel"]]})
print("damage events", len(ev), "clusters (hits, gap>0.5s):", len(clusters))
for c in clusters[:40]:
    ys = [v[1] for v in c["vox"]]; xs = [v[0] for v in c["vox"]]; zs = [v[2] for v in c["vox"]]
    print(f"  t={c['t0']:6.1f}..{c['t1']:6.1f} events={c['n']:4d} voxel x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}] z[{min(zs)},{max(zs)}]")

# --- shot -> hit matching: a hit within TOF+1s after a shot
tof = st.mean(float(r["v"][6]) for r in vals if isinstance(r["v"][6], float) and r["v"][6] > 0) if vals else 0
print(f"time of flight (FCS ch7) mean {tof:.2f} s")
hit_shots = 0
for s in shots:
    if any(s["t"] + tof - 1.0 <= c["t0"] <= s["t"] + tof + 1.0 for c in clusters):
        hit_shots += 1
print(f"shots with a hit cluster about TOF later: {hit_shots} / {len(shots)}")
