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
    return f"{x:.7g}"


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
    vals = [float(x) for x in raw.split(",")] if raw else []
    return seq, tick, vals, ack


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
        self._log = open(log_path, "a", encoding="utf-8") if log_path else None

    def add(self, seq: int, tick: int, values: list[float], t: float | None = None, ack: int | None = None) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            self._times.append(t)
            self._seqs.append(seq)
            if self._prev and seq == self._prev[0] + 1 and tick - self._prev[1] >= RESEND_TICKS:
                self._resent += 1
            self._prev = (seq, tick)
            if len(values) != self.expected_values:
                self._bad_values += 1
            if self._log:
                row = {"t": round(t, 4), "seq": seq, "tick": tick}
                if ack is not None:
                    row["a"] = ack
                row["v"] = [v if math.isfinite(v) else str(v) for v in values]
                self._log.write(json.dumps(row, ensure_ascii=False) + "\n")

    def add_malformed(self) -> None:
        with self._lock:
            self._malformed += 1

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
        s = {"received": len(times), "malformed": malformed, "bad_values": bad, "resent": resent,
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
            c = self._commands[-1]
            body = ",".join(f"{ch}={format_value(v)}" for ch, v in c["values"].items())
            return f"ok|{c['id']}|{body}"

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

    def __init__(self):
        self._lock = threading.Lock()
        self._ops: list[dict] = []  # {id, op, args, issued_t, done_t, ok, vid}
        self._status = {"vid": -1, "sim": -1, "players": 0, "t": None}
        self.polls = 0

    def _issue(self, op: str, args: list[str], t: float | None) -> int:
        t = time.monotonic() if t is None else t
        with self._lock:
            oid = len(self._ops) + 1
            self._ops.append({"id": oid, "op": op, "args": args, "issued_t": t,
                              "done_t": None, "ok": None, "vid": None})
            return oid

    def spawn(self, name: str, pos: tuple[float, float, float], relative: bool, t: float | None = None) -> int:
        if not name or any(c in name for c in "|\r\n"):
            raise ValueError("機体の名前が空か、使えない文字（| や改行）を含む")
        args = [name, *(format_value(float(v)) for v in pos), "1" if relative else "0"]
        return self._issue("spawn", args, t)

    def despawn(self, t: float | None = None) -> int:
        return self._issue("despawn", [], t)

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

    def on_poll(self, ack: int, ok: bool, vid: int, sim: int, players: int, t: float | None = None) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            self.polls += 1
            self._status = {"vid": vid, "sim": sim, "players": players, "t": t}
            for o in self._ops:
                if o["id"] <= ack and o["done_t"] is None:
                    o["done_t"] = t
                    if o["id"] == ack:
                        o["ok"] = ok
                        o["vid"] = vid

    def get(self, oid: int) -> dict:
        with self._lock:
            return dict(self._ops[oid - 1])

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def summary(self) -> dict:
        with self._lock:
            ops = [dict(o) for o in self._ops]
        rows = [{"id": o["id"], "op": o["op"], "args": o["args"], "ok": o["ok"], "vid": o["vid"],
                 "latency_s": None if o["done_t"] is None else round(o["done_t"] - o["issued_t"], 3)}
                for o in ops]
        return {"ops": rows, "polls": self.polls}


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
            except (KeyError, ValueError) as e:
                self._reply(200, f"error: {e}")
                return
            addon.on_poll(ack, ok, vid, sim, players)
            self._reply(200, addon.reply_body())

        def _values(self) -> None:
            try:
                seq, tick, vals, ack = parse_values(self.path)
            except ValueError as e:
                recorder.add_malformed()
                self._reply(200, f"error: {e}")
                return
            now = time.monotonic()
            recorder.add(seq, tick, vals, t=now, ack=ack)
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


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Stormworks のマイコン・アドオンと値・指示をやり取りする中継プログラム")
    ap.add_argument("--mode", choices=("q1", "q2", "q3"), default="q1",
                    help="q1: 値が届くかを数える（既定）。q2: 指示を10回出して反映までの時間を測る。"
                         "q3: アドオンで機体を置く・片付けるを10回くり返す")
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
    ap.add_argument("--logdir", default="logs", help="記録を書くフォルダ（既定 logs）")
    args = ap.parse_args(argv)
    cmd_values = [float(x) for x in args.cmd_values.split(",")]
    if args.mode == "q3" and not args.vehicle:
        ap.error("--mode q3 には --vehicle（置く機体の保存名）が要る")
    offset = tuple(float(x) for x in args.offset.split(","))
    if len(offset) != 3:
        ap.error("--offset は x,y,z の3つの数")

    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{args.mode}-{stamp}"
    log_path = logdir / f"{name}.jsonl"
    rec = Recorder(expected_values=args.values, log_path=log_path)
    com = Commander()
    ops = AddonOps()
    runner = None
    if args.mode == "q3":
        runner = Q3Runner(ops, rec, vehicle=args.vehicle, offset=offset, relative=not args.absolute)
    server = make_server("127.0.0.1", args.port, rec, com, ops)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"待ち受け中: http://127.0.0.1:{args.port}   記録: {log_path}")
    if args.mode == "q2":
        print(f"値が届き始めたら、{Q2_INTERVAL:g}秒ごとに出力1へ指示を{Q2_COMMANDS}回出します。")
        print("ゲームで機体を出すと受信が始まります。Ctrl+C で止めます。")
    elif args.mode == "q3":
        print(f"アドオンから連絡が来たら、機体「{args.vehicle}」を置く・片付けるを{Q3_CYCLES}回くり返します。")
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
                          f"置いている機体 {st['vid']}  マイコンからの値 {rec.summary()['received']}件")
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
        server.shutdown()
        server.server_close()
        rec.close()

    s = rec.summary()
    summary_path = logdir / f"{name}-summary.json"
    if args.mode == "q1":
        out = s
        text = report(s)
    elif args.mode == "q2":
        out = {"values": s, "commands": com.summary()}
        text = report_q2(out["commands"], s)
    else:
        out = {"values": s, "q3": runner.summary(), "addon_ops": ops.summary()}
        text = report_q3(out["q3"])
    summary_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    if args.mode != "q3" and s["resent"]:
        print("注意: マイコンが返事を待ちきれず送り直しました。中継プログラムを機体より後に起動すると、"
              "その間の要求がゲームに溜まり、最初の数秒は返事が遅れます。")
    print(f"まとめ: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
