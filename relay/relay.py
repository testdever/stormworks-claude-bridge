#!/usr/bin/env python3
"""中継プログラム（試作 Q1・Q2）。

Stormworks の機体のマイコンが async.httpGet で送ってくる値を受け取り、
返事に Claude からの指示を載せて返す。標準ライブラリだけで動く。

使い方:
    python relay/relay.py                 # Q1：値が届くか。最初の受信から60秒で止まる
    python relay/relay.py --mode q2       # Q2：指示を10回出し、機体に反映されるまでの時間を測る
    python relay/relay.py --seconds 0     # 自動では止めない（Ctrl+C で止める）

マイコンからの要求:
    /v?s=<通し番号>&t=<tick>&a=<反映した指示の番号>&v=<値1>,<値2>,...   （/q1 でも可。a は省略可）
返事:
    ok                          … 新しい指示なし
    ok|<指示の番号>|<ch>=<値>,…  … この指示を出力に反映する
指示を出す（同じPCから）:
    /cmd?1=0.5&2=1              … 出力1を0.5、出力2を1にする。返事は id=<指示の番号>
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DEFAULT_PORT = 8765
DEFAULT_VALUES = 32
COMMAND_CHANNELS = 8
Q1_MIN_SECONDS = 60
Q1_MIN_PER_SEC = 10
Q2_COMMANDS = 10
Q2_MAX_LATENCY = 2.0
Q2_INTERVAL = 3.0
Q3_CYCLES = 10
VALUE_PATHS = ("/v", "/q1")
RESEND_TICKS = 60  # マイコンの Lua が返事を待つ tick 数。これ以上空いた次の要求は送り直し


def format_value(x: float) -> str:
    # 9桁：ワールドの座標（-24052.37 など）を 1 mm の桁まで渡す。マイコンの数値（32ビット）より細かい
    return f"{x:.9g}"


def parse_values(path: str) -> tuple[int, int, list[float], int | None]:
    """要求のパスから (通し番号, tick, 値の列, 反映した指示の番号) を取り出す。形が違えば ValueError。"""
    q = parse_qs(urlsplit(path).query, keep_blank_values=True)
    try:
        seq = int(q["s"][0])
        tick = int(q["t"][0])
        raw = q["v"][0]
    except (KeyError, IndexError) as e:
        raise ValueError(f"項目 {e} がない") from e
    ack = int(q["a"][0]) if "a" in q else None
    vals = [parse_number(x) for x in raw.split(",")] if raw else []
    return seq, tick, vals, ack


def parse_number(text: str) -> float:
    """数を読む。Windows の Lua が書く数でない値（-nan(ind)、1.#INF など）も nan・inf として読む。"""
    try:
        return float(text)
    except ValueError:
        low = text.strip().lower()
        if "nan" in low or "ind" in low:
            return math.nan
        if "inf" in low:
            return -math.inf if low.startswith("-") else math.inf
        raise


def parse_channels(path: str) -> list[int] | None:
    """マイコンが一部のチャンネルだけ送るときの ch=7,8,9（v の並びと同じ順）。なければ None（v は 1ch から順）。"""
    q = parse_qs(urlsplit(path).query)
    if "ch" not in q:
        return None
    chans = [int(x) for x in q["ch"][0].split(",") if x]
    if any(not 1 <= c <= 32 for c in chans):
        raise ValueError("ch は 1〜32")
    return chans


SHOT_FIELDS = ("n", "tick", "diff", "req", "range", "pred", "tof")


def parse_shots(path: str) -> list[dict]:
    """FCS のつなぎの Lua の shot=<n>:<tick>:<diff>:<req>:<range>:<pred>:<tof>;... を読む。"""
    q = parse_qs(urlsplit(path).query)
    out = []
    for item in q.get("shot", [""])[0].split(";"):
        if not item:
            continue
        f = item.split(":")
        if len(f) != len(SHOT_FIELDS):
            raise ValueError(f"shot の形が違う: {item}")
        rec = {"n": int(f[0]), "tick": int(f[1])}
        for k, x in zip(SHOT_FIELDS[2:], f[2:]):
            rec[k] = parse_number(x)
        out.append(rec)
    return out


def parse_bools(path: str) -> list[bool] | None:
    """マイコンが送るオン/オフの値 b=<32ビットの数>（1ch が最下位ビット）。なければ None。"""
    q = parse_qs(urlsplit(path).query)
    if "b" not in q:
        return None
    mask = int(float(q["b"][0]))
    return [bool(mask >> i & 1) for i in range(32)]


def parse_q1(path: str) -> tuple[int, int, list[float]]:
    seq, tick, vals, _ = parse_values(path)
    return seq, tick, vals


def parse_command(path: str) -> dict[int, float]:
    """/cmd?1=0.5&2=1 から {1: 0.5, 2: 1.0}。チャンネルは 1〜COMMAND_CHANNELS。"""
    q = parse_qs(urlsplit(path).query)
    if not q:
        raise ValueError("指示がない")
    out = {}
    for k, v in q.items():
        ch = int(k)
        if not 1 <= ch <= COMMAND_CHANNELS:
            raise ValueError(f"チャンネル {ch} は 1〜{COMMAND_CHANNELS} の外")
        x = float(v[-1])
        if not math.isfinite(x):
            raise ValueError(f"値 {v[-1]} は数でない")
        out[ch] = x
    return out


class Recorder:
    """受信した値を数え、必要ならファイルに1行ずつ書く。スレッドから呼んでよい。"""

    def __init__(self, expected_values: int = DEFAULT_VALUES, log_path: Path | None = None):
        self.expected_values = expected_values
        self._lock = threading.Lock()
        self._times: list[float] = []
        self._seqs: list[int] = []
        self._bad_values = 0
        self._malformed = 0
        self._resent = 0
        self._prev: tuple[int, int] | None = None
        self._log = open(log_path, "a", encoding="utf-8", buffering=1) if log_path else None
        self._listeners: list = []
        self.malformed_examples: list[dict] = []  # はじいた要求の中身（はじめの20件）
        self._shots: dict[int, dict] = {}  # FCS のつなぎの Lua が送る1発ごとの記録（番号で重複を除く）

    def add_listener(self, fn) -> None:
        """値が届くたびに fn(t, seq, tick, values) を呼ぶ。"""
        self._listeners.append(fn)

    def add(self, seq: int, tick: int, values: list[float], t: float | None = None, ack: int | None = None,
            bools: list[bool] | None = None, channels: list[int] | None = None,
            shots: list[dict] | None = None) -> None:
        t = time.monotonic() if t is None else t
        if channels is not None:
            if len(channels) != len(values):
                raise ValueError("ch と v の数が合わない")
            raw, values = values, [0.0] * self.expected_values
            for c, x in zip(channels, raw):
                if c <= len(values):
                    values[c - 1] = x
        with self._lock:
            for s in shots or []:
                if s["n"] not in self._shots:
                    self._shots[s["n"]] = {**s, "t": t}
            self._times.append(t)
            self._seqs.append(seq)
            if self._prev and seq == self._prev[0] + 1 and tick - self._prev[1] >= RESEND_TICKS:
                self._resent += 1
            self._prev = (seq, tick)
            if len(values) != self.expected_values:
                self._bad_values += 1
            sent = list(zip(channels, raw)) if channels is not None else None
            if self._log:
                row = {"t": round(t, 4), "seq": seq, "tick": tick}
                if ack is not None:
                    row["a"] = ack
                if sent is not None:
                    row["ch"] = [c for c, _ in sent]
                    row["v"] = [x if math.isfinite(x) else str(x) for _, x in sent]
                else:
                    row["v"] = [v if math.isfinite(v) else str(v) for v in values]
                if shots:
                    row["shots"] = shots
                if bools is not None:
                    row["b"] = [i + 1 for i, x in enumerate(bools) if x]
                self._log.write(json.dumps(row, ensure_ascii=False) + "\n")
        for fn in self._listeners:
            fn(t, seq, tick, values)

    def shot_count(self) -> int:
        with self._lock:
            return len(self._shots)

    def shots(self) -> list[dict]:
        with self._lock:
            return [dict(s) for _, s in sorted(self._shots.items())]

    def add_malformed(self, raw: str | None = None, reason: str = "") -> None:
        with self._lock:
            self._malformed += 1
            if raw is not None and len(self.malformed_examples) < 20:
                self.malformed_examples.append({"reason": reason, "request": raw[:2000]})

    def first_time(self) -> float | None:
        with self._lock:
            return self._times[0] if self._times else None

    def count_since(self, t: float) -> int:
        with self._lock:
            return sum(1 for x in self._times if x >= t)

    def summary(self) -> dict:
        with self._lock:
            times, seqs = list(self._times), list(self._seqs)
            bad, malformed, resent = self._bad_values, self._malformed, self._resent
        s = {"received": len(times), "malformed": malformed, "malformed_examples": list(self.malformed_examples), "bad_values": bad, "resent": resent,
             "expected_values": self.expected_values, "duplicates": 0, "missing": 0,
             "duration_s": 0.0, "full_seconds": 0, "min_per_sec": 0, "max_per_sec": 0,
             "avg_per_sec": 0.0, "q1_pass": False}
        if not times:
            return s
        uniq = set(seqs)
        s["duplicates"] = len(seqs) - len(uniq)
        s["missing"] = (max(uniq) - min(uniq) + 1) - len(uniq)
        t0 = times[0]
        duration = times[-1] - t0
        full = int(duration)
        s["duration_s"] = round(duration, 3)
        s["full_seconds"] = full
        if full > 0:
            bins = [0] * full
            for x in times:
                i = int(x - t0)
                if i < full:
                    bins[i] += 1
            s["min_per_sec"] = min(bins)
            s["max_per_sec"] = max(bins)
            s["avg_per_sec"] = round(sum(bins) / full, 2)
        s["q1_pass"] = (full >= Q1_MIN_SECONDS and s["min_per_sec"] >= Q1_MIN_PER_SEC
                        and s["missing"] == 0 and bad == 0)
        return s

    def close(self) -> None:
        if self._log:
            self._log.close()
            self._log = None


class Commander:
    """指示を出し、機体が反映したと知らせるまでの時間を測る。新しい指示は古い指示を置き換える。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._commands: list[dict] = []  # {id, values, issued_t, ack_t}

    def issue(self, values: dict[int, float], t: float | None = None) -> int:
        t = time.monotonic() if t is None else t
        with self._lock:
            cid = len(self._commands) + 1
            self._commands.append({"id": cid, "values": dict(sorted(values.items())), "issued_t": t, "ack_t": None})
            return cid

    def on_ack(self, ack: int, t: float | None = None) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            for c in self._commands:
                if c["id"] <= ack and c["ack_t"] is None:
                    c["ack_t"] = t

    def reply_body(self) -> str:
        with self._lock:
            if not self._commands or self._commands[-1]["ack_t"] is not None:
                return "ok"
            # まだ届いていない指示は、まとめて送る（あとの指示が同じチャンネルを上書きする）。
            # 置き換えると、たとえば「射撃許可を切る」が、座標の渡し直しで消えてしまう
            merged: dict[int, float] = {}
            for c in self._commands:
                if c["ack_t"] is None:
                    merged.update(c["values"])
            body = ",".join(f"{ch}={format_value(v)}" for ch, v in sorted(merged.items()))
            return f"ok|{self._commands[-1]['id']}|{body}"

    def issued(self) -> int:
        with self._lock:
            return len(self._commands)

    def all_acked(self) -> bool:
        with self._lock:
            return all(c["ack_t"] is not None for c in self._commands)

    def summary(self) -> dict:
        with self._lock:
            cmds = [dict(c) for c in self._commands]
        rows, lats = [], []
        for c in cmds:
            lat = None if c["ack_t"] is None else round(c["ack_t"] - c["issued_t"], 3)
            if lat is not None:
                lats.append(lat)
            rows.append({"id": c["id"], "values": {str(k): v for k, v in c["values"].items()}, "latency_s": lat})
        acked = len(lats)
        return {"issued": len(cmds), "acked": acked, "commands": rows,
                "max_latency_s": max(lats) if lats else None,
                "q2_pass": (len(cmds) >= Q2_COMMANDS and acked == len(cmds)
                            and max(lats) <= Q2_MAX_LATENCY)}


class AddonOps:
    """アドオンへの指示（機体を置く・片付ける）。古いものから順に1件ずつ渡し、結果を受け取る。"""

    def __init__(self, log_path: Path | None = None):
        self._lock = threading.Lock()
        self._ops: list[dict] = []  # {id, op, args, issued_t, done_t, ok, vid}
        self._status = {"vid": -1, "sim": -1, "players": 0, "pos": None, "t": None, "target": None}
        self.polls = 0
        # 標的（や置いた機体）が傷ついた知らせ。{t, vehicle, amount, voxel:[x,y,z], body}
        self.damage: list[dict] = []
        self.damage_lost = 0
        self.stop_requests = 0  # 本人がチャットで ?claude stop と打った回数（アドオンが数える）
        self.target_pose: dict[int, dict] = {}  # 標的ごとの、向き（方位）と立ち具合の最小・最大
        self.pose_log: list[tuple[float, int, float, float]] = []  # (時刻, 標的, 方位, 立ち具合)。着弾のときの向きを調べる
        # 指示の番号は _base+1 から。同じワールドのまま中継プログラムを起動し直すと、アドオンは前の番号まで
        # 受け取り済みと覚えていて、それ以下の番号を無視する。最初の連絡で、その続きから振るようにする。
        self._base = 0
        self._log = open(log_path, "a", encoding="utf-8", buffering=1) if log_path else None

    def _issue(self, op: str, args: list[str], t: float | None) -> int:
        t = time.monotonic() if t is None else t
        with self._lock:
            oid = self._base + len(self._ops) + 1
            self._ops.append({"id": oid, "op": op, "args": args, "issued_t": t,
                              "done_t": None, "ok": None, "vid": None})
            return oid

    def spawn(self, name: str, pos: tuple[float, float, float], relative: bool, t: float | None = None,
              look: bool = False) -> int:
        """relative：プレイヤーの位置からの差（世界の向き）。look：プレイヤーの向きで [右, 上, 前] の差。"""
        if not name or any(c in name for c in "|\r\n"):
            raise ValueError("機体の名前が空か、使えない文字（| や改行）を含む")
        mode = "2" if look else ("1" if relative else "0")
        args = [name, *(format_value(float(v)) for v in pos), mode]
        return self._issue("spawn", args, t)

    def despawn(self, t: float | None = None) -> int:
        return self._issue("despawn", [], t)

    def move_player(self, pos: tuple[float, float, float], t: float | None = None) -> int:
        """プレイヤー（ゲーム本体の自分）を pos へ移す。まわりの地面と海が読み込まれる。"""
        return self._issue("move_player", [format_value(float(v)) for v in pos], t)

    def target(self, name: str, distance: float, y: float, same_direction: bool = False, t: float | None = None) -> int:
        """プレイヤーが向いている方向（水平）の distance m 先、高さ y に標的を置く。
        same_direction なら、前の標的と同じ場所から同じ方向に置く（その間にプレイヤーが向きを変えてもよい）。"""
        if not name or any(c in name for c in "|\r\n"):
            raise ValueError("標的の名前が空か、使えない文字（| や改行）を含む")
        return self._issue("target", [name, format_value(float(distance)), format_value(float(y)),
                                      "1" if same_direction else "0"], t)

    def target_reset(self, t: float | None = None) -> int:
        """標的を、置いたときの位置と向きに戻す（機体は読み込み直される）。"""
        return self._issue("target_reset", [], t)

    def target_renew(self, t: float | None = None) -> int:
        """標的を、置いた場所に新しく置き直す（回転も速さも傷もない。当たった標的は戻しても回り続けるため）。"""
        return self._issue("target_renew", [], t)

    def target_despawn(self, t: float | None = None) -> int:
        return self._issue("target_despawn", [], t)

    def weather(self, fog: float, rain: float, wind: float, t: float | None = None) -> int:
        """天気を変える（霧・雨・風、それぞれ 0〜1）。"""
        vals = [float(fog), float(rain), float(wind)]
        if any(not 0.0 <= v <= 1.0 for v in vals):
            raise ValueError("霧・雨・風は 0〜1")
        return self._issue("weather", [format_value(v) for v in vals], t)

    def lift(self, dy: float = 15.0, t: float | None = None) -> int:
        """置いている機体を dy メートル持ち上げる（物理が進んでいれば、そこから落ちる）。"""
        return self._issue("lift", [format_value(float(dy))], t)

    def pending(self) -> dict | None:
        with self._lock:
            for o in self._ops:
                if o["done_t"] is None:
                    return dict(o)
        return None

    def reply_body(self) -> str:
        o = self.pending()
        if o is None:
            return "ok"
        return "|".join(["ok", str(o["id"]), o["op"], *o["args"]])

    def on_poll(self, ack: int, ok: bool, vid: int, sim: int, players: int, t: float | None = None,
                pos: tuple[float, float, float] | None = None, target: dict | None = None,
                damage: list[dict] | None = None, damage_lost: int = 0, stop_requests: int = 0) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            self.polls += 1
            if self.polls == 1 and ack > 0 and not self._ops:
                self._base = ack
            self._status = {"vid": vid, "sim": sim, "players": players, "pos": pos, "t": t, "target": target}
            for d in damage or []:
                self.damage.append({"t": t, **d})
            self.damage_lost = max(self.damage_lost, damage_lost)
            self.stop_requests = max(self.stop_requests, stop_requests)
            if target and "yaw" in target:
                p = self.target_pose.setdefault(target["vid"], {"yaw_min": target["yaw"], "yaw_max": target["yaw"],
                                                                "up_min": target.get("up", 1.0)})
                p["yaw_min"] = min(p["yaw_min"], target["yaw"])
                p["yaw_max"] = max(p["yaw_max"], target["yaw"])
                p["up_min"] = min(p["up_min"], target.get("up", 1.0))
                if len(self.pose_log) < 100000:
                    self.pose_log.append((t, target["vid"], target["yaw"], target.get("up", 1.0)))
            if self._log and (vid >= 0 or target or damage):
                row = {"t": round(t, 4), "vid": vid, "sim": sim, "players": players}
                if pos is not None:
                    row["pos"] = list(pos)
                if target:
                    row["target"] = target
                if damage:
                    row["dmg"] = damage
                self._log.write(json.dumps(row, ensure_ascii=False) + "\n")
            for o in self._ops:
                if o["id"] <= ack and o["done_t"] is None:
                    o["done_t"] = t
                    if o["id"] == ack:
                        o["ok"] = ok
                        o["vid"] = vid

    def get(self, oid: int) -> dict:
        with self._lock:
            return dict(self._ops[oid - self._base - 1])

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def close(self) -> None:
        if self._log:
            self._log.close()
            self._log = None

    def summary(self) -> dict:
        with self._lock:
            ops = [dict(o) for o in self._ops]
        rows = [{"id": o["id"], "op": o["op"], "args": o["args"], "ok": o["ok"], "vid": o["vid"],
                 "latency_s": None if o["done_t"] is None else round(o["done_t"] - o["issued_t"], 3)}
                for o in ops]
        return {"ops": rows, "polls": self.polls, "damage": self.damage_summary(),
                "target_pose": {str(k): v for k, v in self.target_pose.items()}}

    def damage_summary(self) -> dict:
        with self._lock:
            dmg = list(self.damage)
            lost = self.damage_lost
        per: dict[int, dict] = {}
        for d in dmg:
            v = per.setdefault(d["vehicle"], {"events": 0, "amount": 0.0, "voxels": set()})
            v["events"] += 1
            v["amount"] += d["amount"]
            v["voxels"].add(tuple(d["voxel"]))
        return {"lost": lost, "vehicles": {str(k): {"events": v["events"], "amount": round(v["amount"], 3),
                                                    "voxels": len(v["voxels"])} for k, v in per.items()}}


def fcs_summary(shots: list[dict], damage: list[dict], target_vids: set[int] | None = None,
                poses: list[tuple] | None = None) -> dict:
    """1発ごとに当たったか（飛ぶ時間のあたりに標的が傷ついたか）を決め、距離ごとにまとめる。
    poses（時刻, 標的, 方位, 立ち具合）があれば、着弾のときの標的の向きも付ける。"""
    hits_t = sorted(d["t"] for d in damage if target_vids is None or d["vehicle"] in target_vids)
    poses = poses or []
    pose_t = [p[0] for p in poses]
    rows = []
    for s in shots:
        lo, hi = s["t"] + s["tof"] - 0.7, s["t"] + s["tof"] + 1.5
        hit = any(lo <= h <= hi for h in hits_t)
        miss_m = s["range"] * math.tan(math.radians(s["diff"]))
        row = {"n": s["n"], "t": round(s["t"], 3), "range": round(s["range"], 1), "diff_deg": s["diff"],
               "aim_miss_m": round(miss_m, 3), "pred_m": s["pred"], "tof": s["tof"], "hit": hit}
        i = bisect.bisect_right(pose_t, s["t"] + s["tof"]) - 1
        if i >= 0:
            row["impact_yaw"], row["impact_up"] = poses[i][2], poses[i][3]
        rows.append(row)
    groups: dict[int, list[dict]] = {}
    for r in rows:
        groups.setdefault(int(round(r["range"] / 100.0)) * 100, []).append(r)
    out = []
    for rng, g in sorted(groups.items()):
        m = [r["aim_miss_m"] for r in g]
        mean = sum(m) / len(m)
        sd = (sum((x - mean) ** 2 for x in m) / (len(m) - 1)) ** 0.5 if len(m) > 1 else 0.0
        row = {"range_m": rng, "shots": len(g), "hits": sum(r["hit"] for r in g),
               "aim_bias_m": round(mean, 3), "aim_sd_m": round(sd, 3)}
        yaws = [r["impact_yaw"] for r in g if "impact_yaw" in r]
        if yaws:
            row["impact_yaw_min"], row["impact_yaw_max"] = min(yaws), max(yaws)
        out.append(row)
    return {"by_range": out, "shots": rows}


def report_fcs(f: dict) -> list[str]:
    lines = []
    for g in f["by_range"]:
        lines.append(f"約 {g['range_m']} m：{g['shots']}発中 {g['hits']}発当たり。撃った瞬間の照準のずれ（標的の位置で）"
                     f" 偏り {g['aim_bias_m']:+.2f} m、ばらつき {g['aim_sd_m']:.2f} m"
                     + (f"。着弾のときの標的の方位 {g['impact_yaw_min']:.1f}〜{g['impact_yaw_max']:.1f}°"
                        if "impact_yaw_min" in g else ""))
    return lines


def parse_damage(text: str) -> list[dict]:
    """アドオンの dmg=<機体>:<量>:<x>:<y>:<z>:<部分>;... を読む。"""
    out = []
    for item in text.split(";"):
        if not item:
            continue
        f = item.split(":")
        if len(f) != 6:
            raise ValueError(f"dmg の形が違う: {item}")
        out.append({"vehicle": int(f[0]), "amount": float(f[1]), "voxel": [int(f[2]), int(f[3]), int(f[4])],
                    "body": int(f[5])})
    return out


class Q3Runner:
    """機体を置く → hold 秒待つ → 片付ける → gap 秒待つ、を cycles 回くり返す。step(now) を呼び続けて進める。"""

    def __init__(self, ops: AddonOps, recorder: Recorder, vehicle: str, offset: tuple[float, float, float],
                 relative: bool = True, cycles: int = 10, hold: float = 3.0, gap: float = 2.0, timeout: float = 10.0):
        self.ops, self.recorder = ops, recorder
        self.vehicle, self.offset, self.relative = vehicle, offset, relative
        self.cycles, self.hold, self.gap, self.timeout = cycles, hold, gap, timeout
        self.results: list[dict] = []
        self.state = "start"
        self.done = False
        self._cur: dict = {}
        self._op = 0
        self._mark = 0.0
        self.log: list[str] = []

    def step(self, now: float) -> None:
        if self.done:
            return
        if self.state == "start":
            if self.ops.polls == 0:
                return
            self._begin_cycle(now)
        elif self.state == "spawning":
            o = self.ops.get(self._op)
            if o["done_t"] is not None or now - self._mark >= self.timeout:
                self._cur["spawn_ok"] = bool(o["ok"])
                self._cur["spawn_latency_s"] = None if o["done_t"] is None else round(o["done_t"] - o["issued_t"], 3)
                self._cur["vid"] = o["vid"]
                self._cur["spawned_t"] = now
                self.log.append(f"{len(self.results) + 1}回目: 置く → "
                                + ("できた" if o["ok"] else ("返事なし" if o["done_t"] is None else "失敗")))
                self.state, self._mark = "holding", now
        elif self.state == "holding":
            if now - self._mark >= self.hold:
                self._cur["mc_values"] = self.recorder.count_since(self._cur["spawned_t"])
                self._cur["sim"] = self.ops.status()["sim"]
                self._op = self.ops.despawn(t=now)
                self.state, self._mark = "despawning", now
        elif self.state == "despawning":
            o = self.ops.get(self._op)
            if o["done_t"] is not None or now - self._mark >= self.timeout:
                self._cur["despawn_ok"] = bool(o["ok"])
                self._cur["despawn_latency_s"] = None if o["done_t"] is None else round(o["done_t"] - o["issued_t"], 3)
                self.log.append(f"{len(self.results) + 1}回目: 片付ける → "
                                + ("できた" if o["ok"] else ("返事なし" if o["done_t"] is None else "失敗")))
                self._cur.pop("spawned_t", None)
                self.results.append(self._cur)
                self.state, self._mark = "gap", now
        elif self.state == "gap":
            if now - self._mark >= self.gap:
                if len(self.results) >= self.cycles:
                    self.done = True
                else:
                    self._begin_cycle(now)

    def _begin_cycle(self, now: float) -> None:
        self._cur = {"cycle": len(self.results) + 1}
        self._op = self.ops.spawn(self.vehicle, self.offset, self.relative, t=now)
        self.state, self._mark = "spawning", now

    def summary(self) -> dict:
        spawn_ok = sum(1 for r in self.results if r.get("spawn_ok"))
        despawn_ok = sum(1 for r in self.results if r.get("despawn_ok"))
        return {"cycles": len(self.results), "spawn_ok": spawn_ok, "despawn_ok": despawn_ok,
                "results": self.results,
                "q3_pass": len(self.results) >= Q3_CYCLES and spawn_ok == despawn_ok == len(self.results)}


class Q4Runner:
    """機体を1台ずつ決まった場所に置き、出力1で回し、seconds 秒のあいだ物理が進み続けるかを見る。

    window 秒ごとの区切りの始めに機体を lift メートル持ち上げ、物理が進んでいれば落ちて値が変わるようにする
    （止まって休んでいる機体と、物理が止まった機体を見分けるため）。
    各区切りで、マイコンから値が届いているか・値が変わっているかを調べる。
    どの区切りも届いていて変わっていて、その間プレイヤーが0人なら、その機体は合格。
    """

    CHANGE_EPS = 1e-5
    WATCH_CHANNELS = 17

    def __init__(self, ops: AddonOps, recorder: Recorder, commander: Commander, vehicles: list[str],
                 pos: tuple[float, float, float], seconds: float = 60.0, window: float = 10.0,
                 gap: float = 5.0, timeout: float = 10.0, lift: float = 15.0):
        self.ops, self.recorder, self.commander = ops, recorder, commander
        self.lift = lift
        self._lifts_done = 0
        self.vehicles, self.pos = list(vehicles), pos
        self.seconds, self.window, self.gap, self.timeout = seconds, window, gap, timeout
        self.state, self.done = "start", False
        self.results: list[dict] = []
        self.log: list[str] = []
        self._cur: dict = {}
        self._op, self._mark = 0, 0.0
        self._samples: list[tuple[float, list[float]]] = []
        self._pos_samples: list[tuple[float, tuple[float, float, float]]] = []
        self._lock = threading.Lock()
        recorder.add_listener(self._on_values)

    def _on_values(self, t, seq, tick, values) -> None:
        with self._lock:
            if self.state == "observing":
                self._samples.append((t, list(values)))

    def step(self, now: float) -> None:
        if self.done:
            return
        if self.state == "start":
            if self.ops.polls:
                self._spawn_next(now)
        elif self.state == "spawning":
            o = self.ops.get(self._op)
            if o["done_t"] is not None or now - self._mark >= self.timeout:
                self._cur["spawn_ok"] = bool(o["ok"])
                self.log.append(f"「{self._cur['name']}」を置く → " + ("できた" if o["ok"] else "できなかった"))
                if o["ok"]:
                    self.commander.issue({1: 1.0}, t=now)
                    with self._lock:
                        self._samples = []
                        self._pos_samples = []
                        self.state = "observing"
                    self._mark = now
                    self._cur["max_players"] = self.ops.status()["players"]
                    self._cur["sim_seen"] = set()
                    self._cur["lifts"] = []
                    self._lifts_done = 0
                    self.log.append(f"{self.seconds:g}秒間、物理が進むかを見ます（誰も接続しないでください）")
                else:
                    self._finish_vehicle(now, observed=False)
        elif self.state == "observing":
            st = self.ops.status()
            self._cur["max_players"] = max(self._cur["max_players"], st["players"])
            self._cur["sim_seen"].add(st["sim"])
            if st.get("pos") is not None:
                self._pos_samples.append((now, st["pos"]))
            n_windows = max(1, int(round(self.seconds / self.window)))
            if self.lift and self._lifts_done < n_windows and now >= self._mark + self._lifts_done * self.window + 0.5:
                self._cur["lifts"].append(self.ops.lift(self.lift, t=now))
                self._lifts_done += 1
            if now - self._mark >= self.seconds:
                with self._lock:
                    self.state = "despawning"
                    samples = list(self._samples)
                self._cur["windows"] = self._judge(samples, self._mark)
                self._cur["addon_pos_windows"] = self._pos_windows(list(self._pos_samples), self._mark)
                self._op = self.ops.despawn(t=now)
                self._mark = now
        elif self.state == "despawning":
            o = self.ops.get(self._op)
            if o["done_t"] is not None or now - self._mark >= self.timeout:
                self._cur["despawn_ok"] = bool(o["ok"])
                self._finish_vehicle(now, observed=True)
        elif self.state == "gap":
            if now - self._mark >= self.gap:
                if len(self.results) >= len(self.vehicles):
                    self.done = True
                else:
                    self._spawn_next(now)

    def _spawn_next(self, now: float) -> None:
        name = self.vehicles[len(self.results)]
        self._cur = {"name": name}
        self._op = self.ops.spawn(name, self.pos, relative=False, t=now)
        self.state, self._mark = "spawning", now

    def _judge(self, samples: list[tuple[float, list[float]]], start: float) -> list[dict]:
        n = max(1, int(round(self.seconds / self.window)))
        wins = []
        for i in range(n):
            lo, hi = start + i * self.window, start + (i + 1) * self.window
            vals = [v for t, v in samples if lo <= t < hi]
            changed = False
            if len(vals) >= 2:
                for ch in range(min(self.WATCH_CHANNELS, len(vals[0]))):
                    col = [v[ch] for v in vals if ch < len(v) and math.isfinite(v[ch])]
                    if col and max(col) - min(col) > self.CHANGE_EPS:
                        changed = True
                        break
            wins.append({"from_s": round(i * self.window, 1), "values": len(vals), "changed": changed})
        return wins

    def _pos_windows(self, samples, start: float) -> list[dict]:
        """アドオンが送る機体の位置（ゲームが持つ位置）を、区切りごとにまとめる。"""
        n = max(1, int(round(self.seconds / self.window)))
        out = []
        for i in range(n):
            lo, hi = start + i * self.window, start + (i + 1) * self.window
            ys = [p[1] for t, p in samples if lo <= t < hi]
            out.append({"from_s": round(i * self.window, 1), "samples": len(ys),
                        "y_min": round(min(ys), 2) if ys else None, "y_max": round(max(ys), 2) if ys else None})
        return out

    def _finish_vehicle(self, now: float, observed: bool) -> None:
        c = self._cur
        c["lifts"] = [bool(self.ops.get(i)["ok"]) for i in c.get("lifts", [])]
        c.setdefault("windows", [])
        c["sim_seen"] = sorted(c.get("sim_seen", set()))
        c["pass"] = bool(observed and c.get("spawn_ok") and c.get("max_players", 1) == 0 and c["windows"]
                         and all(w["values"] > 0 and w["changed"] for w in c["windows"]))
        self.log.append(f"「{c['name']}」: " + ("物理が進み続けた" if c["pass"] else "物理が進み続けたとは言えない"))
        self.results.append(c)
        self.state, self._mark = "gap", now

    def summary(self) -> dict:
        return {"vehicles": self.results, "q4_pass": any(v["pass"] for v in self.results)}


class ExperimentRunner:
    """Claude が書いた手順書（JSON）を最後まで流し、見張りが異常を見つけたら止めて理由を残す。

    手順の op：
      move_player {pos:[x,y,z]}            プレイヤーを移す（まわりの地面と海が読み込まれる）
      spawn {vehicle, offset:[dx,dy,dz]}    プレイヤーからのずれの位置に機体を置く（pos:[x,y,z] ならワールドの座標）
      wait {seconds}                        待つ（その間も値は記録される）
      set {outputs:{"1":1.0}}               マイコンの出力に指示を出し、反映を待つ
      despawn {}                            機体を片付ける
      inject {kind:"despawn"|"nan"}         試験用にわざと異常を起こす（機体を消す／マイコンに壊れた値を送らせる）
    どの op にも label を付けられる。
    見張り（watch）：values_timeout_s（値が届き始めたあと、途切れたとみなす秒数。既定3）、
      addon_timeout_s（既定3）、values_grace_s（置いてから最初の値を待つ秒数。既定15）、stop_if:[{ch, lt|gt, reason}]
    """

    OPS = {"move_player", "spawn", "wait", "set", "despawn", "inject", "target", "target_despawn", "weather",
           "aim_target", "fire", "target_reset", "target_renew"}
    FOLLOW_INTERVAL = 0.5   # 標的の座標を渡し直す間隔の下限（秒）
    FOLLOW_MOVE = 0.02      # これより動いたら渡し直す（m）
    STEP_TIMEOUT = 10.0
    FAIL_TEXT = {"move_player": "プレイヤーを移せなかった", "spawn": "機体を置けなかった",
                 "despawn": "機体を片付けられなかった", "target": "標的を置けなかった",
                 "target_despawn": "標的を片付けられなかった", "weather": "天気を変えられなかった",
                 "target_reset": "標的を戻せなかった", "target_renew": "標的を置き直せなかった"}
    CLEANUP_TIMEOUT = 5.0

    def __init__(self, ops: AddonOps, recorder: Recorder, commander: Commander, script: dict):
        self.ops, self.recorder, self.commander = ops, recorder, commander
        self.script = script
        self.steps = self._validate(script)
        w = script.get("watch", {})
        self.values_timeout = float(w.get("values_timeout_s", 3.0))
        self.addon_timeout = float(w.get("addon_timeout_s", 3.0))
        # 機体を置いてから最初の値が届くまで待つ時間。プレイヤーを移した直後はまわりの読み込みで遅れる
        self.values_grace = float(w.get("values_grace_s", 15.0))
        self.stop_if = list(w.get("stop_if", []))
        self.done = False
        self.status = "waiting"
        self.reason = ""
        self.log: list[str] = []
        self._t0: float | None = None
        self._i = -1
        self._step_t = 0.0
        self._op = 0
        self._rows: list[dict] = []
        self._injects: list[dict] = []
        self._expected_vid: int | None = None
        self._spawned_t: float | None = None
        self._last_value_t: float | None = None
        self._alarm: str | None = None
        self._stopped_t: float | None = None
        self._cleanup_op: int | None = None
        # aim_target のあと、標的の座標を出力 1〜3（と 4 = 1：有効）でマイコンに渡し続ける
        self._follow: list[int] | None = None
        self._follow_last: tuple | None = None
        self._follow_t = -1e9
        self._stops_seen = 0
        self._fire_ch: int | None = None   # fire で射撃許可を出したチャンネル
        self._fire_base = 0
        self._fire_armed = True            # 射撃許可を出したか（steady のときは、標的が落ち着いてから出す）
        self._fire_armed_t: float | None = None
        self._steady: list[tuple[float, tuple]] = []  # 標的の位置の、直近の記録
        self._shot_marks: list[dict] = []  # fire の手順ごとの、撃った番号の範囲
        # マイコンごとの値の流れ。1台のマイコンの通し番号と tick は増え続けるので、続かない値は別のマイコンから来ている
        self._streams: list[dict] = []
        self._lock = threading.Lock()
        recorder.add_listener(self._on_values)

    @classmethod
    def _expand(cls, steps: list) -> list:
        """repeat {times, steps} を展開する。"""
        out = []
        for s in steps:
            if isinstance(s, dict) and s.get("op") == "repeat":
                n = int(s.get("times", 0))
                inner = s.get("steps")
                if n < 1 or not isinstance(inner, list) or not inner:
                    raise ValueError("repeat には times（1以上）と steps が要る")
                for k in range(n):
                    for x in cls._expand(inner):
                        x = dict(x)
                        if x.get("label"):
                            x["label"] = f"{x['label']}（{k + 1}/{n}）"
                        out.append(x)
            else:
                out.append(s)
        return out

    @classmethod
    def _validate(cls, script: dict) -> list[dict]:
        steps = script.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps（手順の並び）がない")
        steps = cls._expand(steps)
        for i, s in enumerate(steps, 1):
            op = s.get("op") if isinstance(s, dict) else None
            if op not in cls.OPS:
                raise ValueError(f"{i}番目の手順の op「{op}」は使えない（{', '.join(sorted(cls.OPS))}）")
            if op == "move_player" and len(s.get("pos", [])) != 3:
                raise ValueError(f"{i}番目の move_player には pos:[x,y,z] が要る")
            if op == "spawn" and not (s.get("vehicle") or script.get("vehicle")):
                raise ValueError(f"{i}番目の spawn には vehicle（機体の保存名）が要る")
            if op == "spawn" and len(s.get("offset", s.get("pos", s.get("look_offset", [0, 0, 0])))) != 3:
                raise ValueError(f"{i}番目の spawn の offset / pos は [x,y,z]、look_offset は [右, 上, 前]")
            if op == "wait" and float(s.get("seconds", -1)) < 0:
                raise ValueError(f"{i}番目の wait には seconds が要る")
            if op == "set" and not s.get("outputs"):
                raise ValueError(f"{i}番目の set には outputs が要る")
            if op == "target" and not (s.get("vehicle") and float(s.get("distance", 0)) > 0 and "y" in s):
                raise ValueError(f"{i}番目の target には vehicle・distance（m）・y（高さ）が要る")
            if op == "weather" and not all(k in s for k in ("fog", "rain", "wind")):
                raise ValueError(f"{i}番目の weather には fog・rain・wind（0〜1）が要る")
            if op == "fire" and int(s.get("shots", 0)) < 1:
                raise ValueError(f"{i}番目の fire には shots（撃つ数、1以上）が要る")
            if op == "fire" and "steady" in s:
                st = s["steady"]
                if not (isinstance(st, dict) and float(st.get("within_m", 0)) > 0 and float(st.get("for_s", 0)) > 0):
                    raise ValueError(f"{i}番目の fire の steady は {{within_m: 何m以内, for_s: 何秒}}")
            if op == "aim_target" and len(s.get("channels", [1, 2, 3, 4])) != 4:
                raise ValueError(f"{i}番目の aim_target の channels は [X, Y, Z, 有効] の4つ")
            if op == "inject" and s.get("kind") not in ("despawn", "nan"):
                raise ValueError(f"{i}番目の inject の kind は despawn か nan")
        return steps

    # ---- 見張り ----
    STREAM_WINDOW = 1.0   # この秒数の間に
    STREAM_MIN = 10       # それぞれ10件以上
    STREAM_FRESH = 0.2    # しかも両方がこの秒数以内に値を送っていたら、2台以上が同時に動いている

    def _track_stream(self, t: float, seq: int, tick: int) -> bool:
        """値をマイコンごとの流れに振り分け、2つ以上の流れが同時に続いていれば True。"""
        best = None
        for s in self._streams:
            if s["seq"] < seq <= s["seq"] + 100 and s["tick"] < tick <= s["tick"] + 6000:
                if best is None or tick - s["tick"] < tick - best["tick"]:
                    best = s
        if best is None:
            best = {"times": []}
            self._streams.append(best)
        best["seq"], best["tick"] = seq, tick
        best["times"].append(t)
        for s in self._streams:
            s["times"] = [x for x in s["times"] if t - x <= self.STREAM_WINDOW]
        self._streams = [s for s in self._streams if s["times"]]
        alive = [s for s in self._streams
                 if len(s["times"]) >= self.STREAM_MIN and t - s["times"][-1] <= self.STREAM_FRESH]
        return len(alive) >= 2

    def _on_values(self, t, seq, tick, values) -> None:
        with self._lock:
            if self._track_stream(t, seq, tick) and not self._alarm:
                self._alarm = "2台以上のマイコンから値が届いている（片付けられずに残った機体がある可能性）"
            if self._expected_vid is None:
                return
            self._last_value_t = t
            if self._alarm:
                return
            if any(not math.isfinite(v) for v in values):
                self._alarm = "値が壊れた（数でない値がマイコンから届いた）"
                return
            for c in self.stop_if:
                ch = int(c["ch"])
                if ch - 1 >= len(values):
                    continue
                v = values[ch - 1]
                if ("lt" in c and v < float(c["lt"])) or ("gt" in c and v > float(c["gt"])):
                    self._alarm = c.get("reason") or f"出力{ch}が条件を外れた（{v:g}）"
                    return

    def _watch(self, now: float) -> str | None:
        if self.ops.stop_requests > self._stops_seen:
            return "本人がチャットで止めた（?claude stop）"
        with self._lock:
            if self._alarm:
                return self._alarm
            last_value = self._last_value_t
        st = self.ops.status()
        if st["t"] is not None and now - st["t"] > self.addon_timeout:
            return f"アドオンからの連絡が途切れた（{now - st['t']:.1f}秒。ゲームが止まった可能性）"
        if self._expected_vid is not None and self._spawned_t is not None:
            if st["vid"] != self._expected_vid:
                return "機体が消えた（アドオンが置いている機体が変わった）"
            got_first = last_value is not None and last_value >= self._spawned_t
            if got_first and now - last_value > self.values_timeout:
                return f"マイコンからの値が途切れた（{now - last_value:.1f}秒）"
            if not got_first and now - self._spawned_t > self.values_grace:
                return f"機体を置いてから{self.values_grace:g}秒たっても、マイコンから値が届かない"
        return None

    # ---- 進行 ----
    def _rel(self, now: float) -> float:
        return round(now - (self._t0 or now), 3)

    def step(self, now: float) -> None:
        if self.done:
            return
        if self.status == "waiting":
            if self.ops.polls == 0:
                return
            self._stops_seen = self.ops.stop_requests  # 始める前の分は数えない
            self._t0 = now
            self.status = "running"
            self.log.append(f"手順書「{self.script.get('name', '')}」を始めます（{len(self.steps)}手順）")
            self._next(now)
            return
        if self.status == "cleanup":
            o = self.ops.get(self._cleanup_op) if self._cleanup_op else None
            if o is None or o["done_t"] is not None or now - self._stopped_t >= self.CLEANUP_TIMEOUT:
                self.done = True
            return
        alarm = self._watch(now)
        if alarm:
            self._stop(now, alarm)
            return
        self._feed_target(now)
        self._advance(now)

    def _next(self, now: float) -> None:
        if self._i >= 0:
            self._rows[-1]["end_s"] = self._rel(now)
        self._i += 1
        if self._i >= len(self.steps):
            self.status = "completed"
            self._safe_off(now)
            self.log.append("手順書を最後まで流しました")
            self.done = True
            return
        s = self.steps[self._i]
        self._rows.append({"i": self._i + 1, "op": s["op"], "label": s.get("label", ""),
                           "start_s": self._rel(now), "end_s": None, "ok": None})
        self._step_t = now
        op = s["op"]
        if op == "move_player":
            self._op = self.ops.move_player(tuple(s["pos"]), t=now)
        elif op == "spawn":
            self._expected_vid = None  # アドオンは前の機体を片付けてから置く。置き終わるまで「消えた」と見ない
            self._spawned_t = None
            name = s.get("vehicle") or self.script.get("vehicle")
            if "pos" in s:
                self._op = self.ops.spawn(name, tuple(s["pos"]), relative=False, t=now)
            elif "look_offset" in s:
                self._op = self.ops.spawn(name, tuple(s["look_offset"]), relative=True, look=True, t=now)
            else:
                self._op = self.ops.spawn(name, tuple(s.get("offset", [0, 3, 15])), relative=True, t=now)
        elif op == "target":
            self._op = self.ops.target(s["vehicle"], float(s["distance"]), float(s["y"]),
                                       same_direction=bool(s.get("same_direction")), t=now)
        elif op == "target_despawn":
            self._safe_off(now)
            self._op = self.ops.target_despawn(t=now)
        elif op == "target_reset":
            self._op = self.ops.target_reset(t=now)
        elif op == "target_renew":
            self._op = self.ops.target_renew(t=now)
        elif op == "fire":
            self._fire_ch = int(s.get("channel", 5))
            self._fire_base = self.recorder.shot_count()
            self._steady = []
            self._fire_armed = "steady" not in s
            self._fire_armed_t = now if self._fire_armed else None
            if self._fire_armed:
                self.commander.issue({self._fire_ch: 1.0}, t=now)
        elif op == "aim_target":
            self._follow = [int(c) for c in s.get("channels", [1, 2, 3, 4])]
            self._follow_last = None
            self._follow_t = -1e9
        elif op == "weather":
            self._op = self.ops.weather(s["fog"], s["rain"], s["wind"], t=now)
        elif op == "set":
            self.commander.issue({int(k): float(v) for k, v in s["outputs"].items()}, t=now)
        elif op == "despawn":
            self._expected_vid = None
            self._spawned_t = None
            self._op = self.ops.despawn(t=now)
        elif op == "inject":
            self._injects.append({"kind": s["kind"], "t_s": self._rel(now)})
            if s["kind"] == "despawn":
                self.ops.despawn(t=now)  # 手順としては機体を置いたまま。見張りが消えたことに気づくかを見る
            else:
                self.commander.issue({8: 1.0}, t=now)
            self.log.append(f"試験用の異常を起こした: {s['kind']}")
        what = s.get("label") or op
        self.log.append(f"{self._i + 1}. {what}")

    def _advance(self, now: float) -> None:
        s = self.steps[self._i]
        op = s["op"]
        elapsed = now - self._step_t
        if op in self.FAIL_TEXT:
            o = self.ops.get(self._op)
            if o["done_t"] is None:
                if elapsed >= self.STEP_TIMEOUT:
                    self._fail(now, self.FAIL_TEXT[op] + "（アドオンから返事がない）")
                return
            if not o["ok"]:
                self._fail(now, self.FAIL_TEXT[op])
                return
            if op == "spawn":
                self._expected_vid = o["vid"]
                self._spawned_t = now
            self._rows[-1]["ok"] = True
            self._next(now)
        elif op == "set":
            if self.commander.all_acked():
                self._rows[-1]["ok"] = True
                self._next(now)
            else:
                # 機体がまだ動き出していない（最初の値を待っている）間は、見張りの方に任せる
                deadline = self._step_t + 5.0
                if self._spawned_t is not None:
                    deadline = max(deadline, self._spawned_t + self.values_grace + 1.0)
                if now >= deadline:
                    self._fail(now, "指示が機体に届かない（5秒）")
        elif op == "wait":
            if elapsed >= float(s["seconds"]):
                self._rows[-1]["ok"] = True
                self._next(now)
        elif op == "fire":
            if not self._fire_armed and self._target_steady(now, s["steady"]):
                self.commander.issue({self._fire_ch: 1.0}, t=now)
                self._fire_armed, self._fire_armed_t = True, now
            got = self.recorder.shot_count() - self._fire_base
            want = int(s["shots"])
            if got >= want:
                self.commander.issue({self._fire_ch: 0.0}, t=now)
                self._shot_marks.append({"step": self._i + 1, "from": self._fire_base + 1, "to": self._fire_base + got,
                                         "t_s": self._rel(now),
                                         "steady_wait_s": round(self._fire_armed_t - self._step_t, 3)})
                self._rows[-1]["ok"] = True
                self._next(now)
            elif elapsed >= float(s.get("timeout_s", 30)):
                if not self._fire_armed:
                    self._fail(now, f"標的が落ち着かず、撃てなかった（{elapsed:.0f}秒）")
                else:
                    self._fail(now, f"{want}発撃てなかった（{elapsed:.0f}秒で{got}発）")
        elif op in ("inject", "aim_target"):
            self._rows[-1]["ok"] = True
            self._next(now)

    def _safe_off(self, now: float) -> None:
        """射撃許可を切り、目標を無効にする（X も 0：X が 0 でなければ有効とする FCS もある）。"""
        off: dict[int, float] = {}
        if self._fire_ch is not None:
            off[self._fire_ch] = 0.0
        if self._follow:
            off[self._follow[0]] = 0.0
            off[self._follow[3]] = 0.0
            self._follow = None
        if off:
            self.commander.issue(off, t=now)

    def _target_steady(self, now: float, st: dict) -> bool:
        """標的の位置が、直近 for_s 秒の間 within_m 以内に収まっているか（置き直した直後は海に落ちて揺れる）。"""
        pos = (self.ops.status().get("target") or {}).get("pos")
        if pos is None:
            return False
        span = float(st["for_s"])
        self._steady.append((now, tuple(pos)))
        while len(self._steady) > 1 and self._steady[1][0] <= now - span:
            self._steady.pop(0)
        if self._steady[0][0] > now - span:
            return False
        return all(max(p[k] for _, p in self._steady) - min(p[k] for _, p in self._steady) <= float(st["within_m"])
                   for k in range(3))

    def _feed_target(self, now: float) -> None:
        """標的の座標をマイコンに渡す。前の分が届いてから、動いたときだけ（指示を溜めない）。"""
        if not self._follow:
            return
        tg = self.ops.status().get("target") or {}
        pos = tg.get("pos")
        if pos is None or not self.commander.all_acked() or now - self._follow_t < self.FOLLOW_INTERVAL:
            return
        last = self._follow_last
        if last is not None and max(abs(a - b) for a, b in zip(pos, last)) < self.FOLLOW_MOVE:
            return
        cx, cy, cz, cv = self._follow
        self.commander.issue({cx: pos[0], cy: pos[1], cz: pos[2], cv: 1.0}, t=now)
        self._follow_last = tuple(pos)
        self._follow_t = now

    def _fail(self, now: float, reason: str) -> None:
        self._rows[-1]["ok"] = False
        self._stop(now, reason)

    def _stop(self, now: float, reason: str) -> None:
        self.status = "stopped"
        self.reason = reason
        self._stopped_t = now
        if self._rows and self._rows[-1]["end_s"] is None:
            self._rows[-1]["end_s"] = self._rel(now)
        self.log.append(f"止めました: {reason}")
        self._safe_off(now)
        st = self.ops.status()
        if st["vid"] >= 0:
            self._cleanup_op = self.ops.despawn(t=now)
        if st.get("target"):
            self._cleanup_op = self.ops.target_despawn(t=now)
        self._expected_vid = None
        self.status = "cleanup"

    def result(self) -> dict:
        status = "completed" if self.status == "completed" else ("stopped" if self._stopped_t is not None else self.status)
        res = {"name": self.script.get("name", ""), "status": status, "reason": self.reason,
               "steps": self._rows, "injects": self._injects,
               "stopped_at_s": self._rel(self._stopped_t) if self._stopped_t is not None else None,
               "stop_latency_s": None}
        if self._stopped_t is not None and self._injects:
            res["stop_latency_s"] = round(res["stopped_at_s"] - self._injects[-1]["t_s"], 3)
        if self._shot_marks:
            res["fire_steps"] = self._shot_marks
        return res


class ProcessSampler:
    """プロセスの CPU 使用率とメモリを一定間隔で記録する（Windows では PowerShell を使う）。"""

    def __init__(self, name: str, interval: float = 5.0, cores: int | None = None, query=None):
        import os
        self.name, self.interval = name, interval
        self.cores = cores or os.cpu_count() or 1
        self.query = query or self._powershell
        self.samples: list[dict] = []
        self._prev: tuple[float, float] | None = None
        self._stop = threading.Event()

    def _powershell(self) -> str:
        import subprocess
        if sys.platform != "win32":
            return ""
        cmd = (f"$p=Get-Process {self.name} -ErrorAction SilentlyContinue | Select-Object -First 1; "
               "if($p){'{0} {1}' -f $p.CPU,$p.WorkingSet64}")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                               capture_output=True, text=True, timeout=10)
            return r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def sample(self, t: float | None = None) -> None:
        t = time.monotonic() if t is None else t
        out = self.query().replace(",", ".").split()
        if len(out) != 2:
            self._prev = None
            return
        try:
            cpu_s, mem = float(out[0]), float(out[1])
        except ValueError:
            return
        row = {"t": t, "memory_mb": round(mem / 1048576, 1), "cpu_percent": None}
        if self._prev is not None and t > self._prev[0]:
            row["cpu_percent"] = round((cpu_s - self._prev[1]) / (t - self._prev[0]) / self.cores * 100, 1)
        self._prev = (t, cpu_s)
        self.samples.append(row)

    def start(self) -> None:
        def loop():
            while not self._stop.is_set():
                self.sample()
                self._stop.wait(self.interval)
        threading.Thread(target=loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def summary(self) -> dict:
        cpus = [s["cpu_percent"] for s in self.samples if s["cpu_percent"] is not None]
        mems = [s["memory_mb"] for s in self.samples]
        return {"process": self.name, "available": bool(mems), "cores": self.cores,
                "cpu_percent_avg": round(sum(cpus) / len(cpus), 1) if cpus else None,
                "cpu_percent_max": max(cpus) if cpus else None,
                "memory_mb_max": max(mems) if mems else None, "samples": len(self.samples)}


def parse_spawn(path: str) -> tuple[str, tuple[float, float, float], bool]:
    q = parse_qs(urlsplit(path).query)
    try:
        name = q["name"][0]
        pos = (float(q.get("x", ["0"])[0]), float(q.get("y", ["0"])[0]), float(q.get("z", ["0"])[0]))
    except (KeyError, ValueError) as e:
        raise ValueError(f"name と x,y,z が要る（{e}）") from e
    return name, pos, q.get("rel", ["1"])[0] == "1"


def make_server(host: str, port: int, recorder: Recorder, commander: Commander | None = None,
                addon: AddonOps | None = None) -> ThreadingHTTPServer:
    commander = commander or Commander()
    addon = addon or AddonOps()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlsplit(self.path).path
            if path in VALUE_PATHS:
                self._values()
            elif path == "/addon":
                self._addon()
            elif path in ("/cmd", "/spawn", "/despawn"):
                try:
                    if path == "/cmd":
                        oid = commander.issue(parse_command(self.path))
                    elif path == "/spawn":
                        name, pos, rel = parse_spawn(self.path)
                        oid = addon.spawn(name, pos, rel)
                    else:
                        oid = addon.despawn()
                except ValueError as e:
                    self._reply(400, f"error: {e}")
                    return
                self._reply(200, f"id={oid}")
            else:
                self._reply(404, "error: unknown path")

        def _addon(self) -> None:
            q = parse_qs(urlsplit(self.path).query)
            try:
                ack = int(q["a"][0])
                ok = q.get("r", ["1"])[0] == "1"
                vid = int(q.get("vid", ["-1"])[0])
                sim = int(q.get("sim", ["-1"])[0])
                players = int(q.get("np", ["0"])[0])
                pos = None
                if all(k in q for k in ("px", "py", "pz")):
                    pos = (float(q["px"][0]), float(q["py"][0]), float(q["pz"][0]))
                target = None
                if "tvid" in q:
                    target = {"vid": int(q["tvid"][0]), "sim": int(q.get("tsim", ["-1"])[0])}
                    if all(k in q for k in ("tx", "ty", "tz")):
                        target["pos"] = [float(q["tx"][0]), float(q["ty"][0]), float(q["tz"][0])]
                    if "tyaw" in q:
                        target["yaw"] = float(q["tyaw"][0])
                    if "tup" in q:
                        target["up"] = float(q["tup"][0])
                damage = parse_damage(q["dmg"][0]) if "dmg" in q else None
                lost = int(q.get("dlost", ["0"])[0])
                stops = int(q.get("stop", ["0"])[0])
            except (KeyError, ValueError) as e:
                self._reply(200, f"error: {e}")
                return
            addon.on_poll(ack, ok, vid, sim, players, pos=pos, target=target, damage=damage, damage_lost=lost,
                          stop_requests=stops)
            self._reply(200, addon.reply_body())

        def _values(self) -> None:
            try:
                seq, tick, vals, ack = parse_values(self.path)
            except ValueError as e:
                recorder.add_malformed(self.path, str(e))
                self._reply(200, f"error: {e}")
                return
            now = time.monotonic()
            try:
                bools = parse_bools(self.path)
            except ValueError:
                bools = None
            try:
                chans = parse_channels(self.path)
                shots = parse_shots(self.path)
                recorder.add(seq, tick, vals, t=now, ack=ack, bools=bools, channels=chans, shots=shots)
            except ValueError as e:
                recorder.add_malformed(self.path, str(e))
                self._reply(200, f"error: {e}")
                return
            if ack is not None:
                commander.on_ack(ack, t=now)
            self._reply(200, commander.reply_body())

        def _reply(self, code: int, text: str) -> None:
            body = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # 1件ごとの表示はしない
            pass

    return ThreadingHTTPServer((host, port), Handler)


def report(s: dict) -> str:
    lines = [
        "---- 結果 ----",
        f"受信: {s['received']}件（形が違う要求 {s['malformed']}件、重複 {s['duplicates']}件）",
        f"欠け（通し番号の抜け）: {s['missing']}件",
        f"マイコンが返事を待ちきれず送り直した回数: {s['resent']}回",
        f"値の数が {s['expected_values']} 個でない受信: {s['bad_values']}件",
        f"受信していた時間: {s['duration_s']}秒（数えた1秒の区切り {s['full_seconds']}個）",
        f"1秒あたり: 最小 {s['min_per_sec']} / 平均 {s['avg_per_sec']} / 最大 {s['max_per_sec']}",
    ]
    if s["q1_pass"]:
        lines.append("Q1 の基準（1秒に10回以上、60秒間、欠けなし）: 満たした")
    else:
        why = []
        if s["full_seconds"] < Q1_MIN_SECONDS:
            why.append("60秒に届いていない")
        if s["min_per_sec"] < Q1_MIN_PER_SEC:
            why.append("1秒に10回を下回った区切りがある")
        if s["missing"]:
            why.append("欠けがある")
        if s["bad_values"]:
            why.append("値の数が足りない受信がある")
        lines.append("Q1 の基準: 満たさなかった（" + "、".join(why or ["受信なし"]) + "）")
    return "\n".join(lines)


def report_q2(c: dict, s: dict | None = None) -> str:
    lines = ["---- 指示の結果 ----"]
    if s is not None:
        lines.append(f"受信: {s['received']}件、欠け {s['missing']}件、"
                     f"マイコンが返事を待ちきれず送り直した回数 {s['resent']}回")
    for row in c["commands"]:
        vals = ", ".join(f"出力{k}={v:g}" for k, v in row["values"].items())
        lat = "反映されなかった" if row["latency_s"] is None else f"{row['latency_s']:.3f}秒で反映"
        lines.append(f"指示{row['id']:2d}（{vals}）: {lat}")
    lines.append(f"反映された指示: {c['acked']}/{c['issued']}件、最も遅いもの: {c['max_latency_s']}秒")
    if c["q2_pass"]:
        lines.append("Q2 の基準（10回すべて2秒以内に反映）: 満たした")
    else:
        lines.append("Q2 の基準（10回すべて2秒以内に反映）: 満たさなかった")
    return "\n".join(lines)


def report_q3(q: dict) -> str:
    lines = ["---- 機体を置く・片付けるの結果 ----"]
    for r in q["results"]:
        sp = "できた" if r.get("spawn_ok") else "できなかった"
        dp = "できた" if r.get("despawn_ok") else "できなかった"
        sim = {1: "物理が動いている", 0: "読み込み中", -1: "不明"}.get(r.get("sim", -1), "不明")
        lines.append(f"{r['cycle']:2d}回目: 置く {sp}（{r.get('spawn_latency_s')}秒）、"
                     f"マイコンからの値 {r.get('mc_values', 0)}件、{sim}、片付ける {dp}（{r.get('despawn_latency_s')}秒）")
    lines.append(f"置けた: {q['spawn_ok']}/{q['cycles']}回、片付けられた: {q['despawn_ok']}/{q['cycles']}回")
    lines.append("Q3 の基準（置く・片付けるが10回中10回）: " + ("満たした" if q["q3_pass"] else "満たさなかった"))
    return "\n".join(lines)


def report_q4(q: dict, load: dict | None) -> str:
    lines = ["---- 誰も接続していない専用サーバーで物理が進むかの結果 ----"]
    for v in q["vehicles"]:
        lifts = v.get("lifts", [])
        lines.append(f"「{v['name']}」: 置く {'できた' if v.get('spawn_ok') else 'できなかった'}、"
                     f"その間のプレイヤー最大 {v.get('max_players', '-')}人、"
                     f"持ち上げ {sum(lifts)}/{len(lifts)}回成功")
        pws = v.get("addon_pos_windows", [])
        for k, w in enumerate(v.get("windows", [])):
            line = (f"  {w['from_s']:5.0f}秒〜: マイコンからの値 {w['values']}件、"
                    + ("値が変わっている" if w["changed"] else "値が止まっている"))
            if k < len(pws) and pws[k]["samples"]:
                line += f"、アドオンから見た高さ {pws[k]['y_min']}〜{pws[k]['y_max']} m"
            lines.append(line)
        lines.append("  → " + ("物理が進み続けた" if v["pass"] else "物理が進み続けたとは言えない"))
    lines.append("Q4 の基準（誰も接続していない状態で60秒間、値が変わり続けて届く）: "
                 + ("満たした" if q["q4_pass"] else "満たさなかった"))
    if load is not None:
        if load["available"]:
            lines.append(f"専用サーバーの負荷: CPU 平均 {load['cpu_percent_avg']}% / 最大 {load['cpu_percent_max']}%"
                         f"（{load['cores']}論理コアに対する割合）、メモリ最大 {load['memory_mb_max']} MB")
        else:
            lines.append(f"専用サーバー（{load['process']}）の負荷は測れなかった")
    return "\n".join(lines)


def target_status(st: dict, ops: "AddonOps") -> str:
    tg = st.get("target")
    if not tg and not ops.damage:
        return ""
    text = ""
    if tg:
        pos = tg.get("pos")
        where = f" 位置 ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})" if pos else ""
        text = f"  標的 {tg['vid']}（動いている={'はい' if tg['sim'] == 1 else 'いいえ'}）{where}"
    return text + f"  当たった知らせ {len(ops.damage)}件"


def report_damage(d: dict) -> list[str]:
    lines = []
    for vid, v in d.get("vehicles", {}).items():
        lines.append(f"機体 {vid} が傷ついた知らせ: {v['events']}件（ブロック {v['voxels']}か所、合計の量 {v['amount']}）")
    if d.get("lost"):
        lines.append(f"アドオンが溜めきれず捨てた知らせ: {d['lost']}件")
    return lines


def report_run(r: dict, s: dict, load: dict | None, damage: dict | None = None) -> str:
    lines = [f"---- 手順書「{r['name']}」の結果 ----"]
    for st in r["steps"]:
        mark = {True: "OK", False: "失敗", None: "途中"}[st["ok"]]
        label = f"（{st['label']}）" if st.get("label") else ""
        lines.append(f"{st['i']:2d}. {st['op']}{label}  {st['start_s']}〜{st['end_s']}秒  {mark}")
    if r["status"] == "completed":
        lines.append("最後まで流れた（本人の操作なし）")
    else:
        lines.append(f"止まった: {r['reason']}（{r['stopped_at_s']}秒）")
        if r.get("stop_latency_s") is not None:
            lines.append(f"試験用の異常を起こしてから止まるまで: {r['stop_latency_s']}秒")
    lines.append(f"マイコンからの値: {s['received']}件")
    if damage:
        lines.extend(report_damage(damage))
    if load is not None:
        if load["available"]:
            lines.append(f"{load['process']} の負荷: CPU 平均 {load['cpu_percent_avg']}% / 最大 {load['cpu_percent_max']}%"
                         f"（{load['cores']}論理コアに対する割合）、メモリ最大 {load['memory_mb_max']} MB")
        else:
            lines.append(f"{load['process']} の負荷は測れなかった")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Stormworks のマイコン・アドオンと値・指示をやり取りする中継プログラム")
    ap.add_argument("--mode", choices=("q1", "q2", "q3", "q4"), default="q1",
                    help="q1: 値が届くかを数える（既定）。q2: 指示を10回出して反映までの時間を測る。"
                         "q3: アドオンで機体を置く・片付けるを10回くり返す。"
                         "q4: 専用サーバーで、誰も接続していなくても物理が進むかを見る")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"待ち受けるポート（既定 {DEFAULT_PORT}）")
    ap.add_argument("--seconds", type=float, default=Q1_MIN_SECONDS,
                    help="q1: 最初の受信からこの秒数で自動で止める。0 なら止めない（既定 60）")
    ap.add_argument("--values", type=int, default=DEFAULT_VALUES, help="1回に届くはずの値の数（既定 32）")
    ap.add_argument("--cmd-values", default="1,0",
                    help="q2: 出力1に順に出す値（カンマ区切り、既定 1,0）")
    ap.add_argument("--vehicle", help="q3: 置く機体の保存名（ワークベンチで保存した名前）")
    ap.add_argument("--offset", default="0,3,15",
                    help="q3: 置く場所。プレイヤーの位置からのずれ x,y,z（m、既定 0,3,15。y が上）")
    ap.add_argument("--absolute", action="store_true", help="q3: --offset をプレイヤーからのずれではなくワールドの座標とする")
    ap.add_argument("--vehicles", default="claude_test,claude_test_ka",
                    help="q4: 順に置く機体の保存名（カンマ区切り、既定 claude_test,claude_test_ka）")
    ap.add_argument("--pos", default="-260.9,8,-18949",
                    help="q4: 機体を置くワールドの座標 x,y,z（既定は Q1 で機体があった場所の 3m 上）")
    ap.add_argument("--process", default=None,
                    help="負荷を記録するプロセス名（q4 の既定 server64、--run の既定 stormworks64）")
    ap.add_argument("--run", metavar="手順書.json",
                    help="Claude が書いた手順書を最後まで流す（--mode より優先）。見張りが異常を見つけたら止める")
    ap.add_argument("--logdir", default="logs", help="記録を書くフォルダ（既定 logs）")
    args = ap.parse_args(argv)
    cmd_values = [float(x) for x in args.cmd_values.split(",")]
    if args.mode == "q3" and not args.vehicle:
        ap.error("--mode q3 には --vehicle（置く機体の保存名）が要る")
    offset = tuple(float(x) for x in args.offset.split(","))
    if len(offset) != 3:
        ap.error("--offset は x,y,z の3つの数")

    script = None
    if args.run:
        try:
            script = json.loads(Path(args.run).read_text(encoding="utf-8"))
            ExperimentRunner._validate(script)
        except (OSError, ValueError) as e:
            ap.error(f"手順書 {args.run} が読めない: {e}")
        args.mode = "run"

    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{args.mode}-{stamp}"
    log_path = logdir / f"{name}.jsonl"
    rec = Recorder(expected_values=args.values, log_path=log_path)
    com = Commander()
    ops = AddonOps(log_path=logdir / f"{name}-addon.jsonl" if args.mode in ("q3", "q4", "run") else None)
    runner = None
    sampler = None
    if args.mode == "q3":
        runner = Q3Runner(ops, rec, vehicle=args.vehicle, offset=offset, relative=not args.absolute)
    elif args.mode == "q4":
        pos = tuple(float(x) for x in args.pos.split(","))
        if len(pos) != 3:
            ap.error("--pos は x,y,z の3つの数")
        vehicles = [v.strip() for v in args.vehicles.split(",") if v.strip()]
        runner = Q4Runner(ops, rec, com, vehicles=vehicles, pos=pos, seconds=args.seconds or Q1_MIN_SECONDS)
        sampler = ProcessSampler(args.process or "server64")
        sampler.start()
    elif args.mode == "run":
        runner = ExperimentRunner(ops, rec, com, script)
        sampler = ProcessSampler(args.process or "stormworks64")
        sampler.start()
    server = make_server("127.0.0.1", args.port, rec, com, ops)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"待ち受け中: http://127.0.0.1:{args.port}   記録: {log_path}")
    if args.mode == "q2":
        print(f"値が届き始めたら、{Q2_INTERVAL:g}秒ごとに出力1へ指示を{Q2_COMMANDS}回出します。")
        print("ゲームで機体を出すと受信が始まります。Ctrl+C で止めます。")
    elif args.mode == "q3":
        print(f"アドオンから連絡が来たら、機体「{args.vehicle}」を置く・片付けるを{Q3_CYCLES}回くり返します。")
        print("アドオンを有効にしたワールドに入ると始まります。Ctrl+C で止めます。")
    elif args.mode == "q4":
        print(f"アドオンから連絡が来たら、{', '.join(runner.vehicles)} を1台ずつ置き、"
              f"{runner.seconds:g}秒ずつ物理が進むかを見ます。")
        print("専用サーバーを起動すると始まります。終わるまで、ゲームからサーバーに接続しないでください。Ctrl+C で止めます。")
    elif args.mode == "run":
        print(f"手順書「{script.get('name', args.run)}」（{len(script['steps'])}手順）を、アドオンから連絡が来たら流します。")
        print("アドオンを有効にしたワールドに入ると始まります。Ctrl+C で止めます。")
    else:
        print("ゲームで機体を出すと受信が始まります。Ctrl+C で止めます。")

    last_print = 0.0
    q2_done_at = None
    shown_log = 0
    started = None
    try:
        while True:
            time.sleep(0.1)
            now = time.monotonic()
            if runner is not None:
                if ops.polls == 0:
                    continue
                started = started or now
                runner.step(now)
                for line in runner.log[shown_log:]:
                    print(line)
                shown_log = len(runner.log)
                if now - last_print >= 1.0:
                    last_print = now
                    st = ops.status()
                    print(f"経過 {now - started:5.0f}秒  アドオンからの連絡 {ops.polls}回  "
                          f"置いている機体 {st['vid']}  プレイヤー {st['players']}人  "
                          f"マイコンからの値 {rec.summary()['received']}件{target_status(st, ops)}")
                if runner.done:
                    break
                continue
            t0 = rec.first_time()
            if t0 is None:
                continue
            if args.mode == "q2":
                n = com.issued()
                if n < Q2_COMMANDS and now >= t0 + 2.0 + Q2_INTERVAL * n:
                    v = cmd_values[n % len(cmd_values)]
                    cid = com.issue({1: v}, t=now)
                    print(f"指示{cid}を出した: 出力1={v:g}")
                if com.issued() >= Q2_COMMANDS and q2_done_at is None:
                    q2_done_at = now
                if q2_done_at is not None and (com.all_acked() or now - q2_done_at >= Q2_INTERVAL + 2):
                    time.sleep(0.5)
                    break
            if now - last_print >= 1.0:
                last_print = now
                s = rec.summary()
                extra = f"  反映済みの指示 {com.summary()['acked']}/{com.issued()}" if args.mode == "q2" else ""
                print(f"経過 {now - t0:5.0f}秒  受信 {s['received']}件  直近1秒 {rec.count_since(now - 1)}件  "
                      f"欠け {s['missing']}件  送り直し {s['resent']}回{extra}")
            if args.mode == "q1" and args.seconds > 0 and now - t0 >= args.seconds + 0.5:
                break
    except KeyboardInterrupt:
        print("\n止めました。")
    finally:
        if sampler is not None:
            sampler.stop()
        server.shutdown()
        server.server_close()
        rec.close()
        ops.close()

    s = rec.summary()
    summary_path = logdir / f"{name}-summary.json"
    if args.mode == "q1":
        out = s
        text = report(s)
    elif args.mode == "q2":
        out = {"values": s, "commands": com.summary()}
        text = report_q2(out["commands"], s)
    elif args.mode == "q3":
        out = {"values": s, "q3": runner.summary(), "addon_ops": ops.summary()}
        text = report_q3(out["q3"])
    elif args.mode == "run":
        load = sampler.summary()
        out = {"script": script, "result": runner.result(), "values": s, "load": load,
               "load_samples": sampler.samples, "addon_ops": ops.summary()}
        text = report_run(out["result"], s, load, out["addon_ops"]["damage"])
        shots = rec.shots()
        if shots:
            tv = {int(k) for k in out["addon_ops"]["target_pose"]} or None
            out["fcs"] = fcs_summary(shots, ops.damage, tv, ops.pose_log)
            text += "\n" + "\n".join(report_fcs(out["fcs"]))
        poses = out["addon_ops"]["target_pose"]
        if len(poses) > 3:
            text += (f"\n標的 {len(poses)} 台（1発ごとに置き直し）の向き：方位 {min(p['yaw_min'] for p in poses.values()):.1f}〜"
                     f"{max(p['yaw_max'] for p in poses.values()):.1f}°（当たったあとの回転を含む）")
        else:
            for vid, p in out["addon_ops"]["target_pose"].items():
                text += (f"\n標的 {vid} の向き：方位 {p['yaw_min']:.1f}〜{p['yaw_max']:.1f}°、"
                         f"立ち具合の最小 {p['up_min']:.3f}（1 = まっすぐ）")
    else:
        load = sampler.summary()
        out = {"values": s, "q4": runner.summary(), "load": load, "load_samples": sampler.samples,
               "addon_ops": ops.summary()}
        text = report_q4(out["q4"], load)
    summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    if args.mode in ("q1", "q2") and s["resent"]:
        print("注意: マイコンが返事を待ちきれず送り直しました。中継プログラムを機体より後に起動すると、"
              "その間の要求がゲームに溜まり、最初の数秒は返事が遅れます。")
    print(f"まとめ: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
