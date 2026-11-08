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
VALUE_PATHS = ("/v", "/q1")


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
        self._log = open(log_path, "a", encoding="utf-8") if log_path else None

    def add(self, seq: int, tick: int, values: list[float], t: float | None = None, ack: int | None = None) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            self._times.append(t)
            self._seqs.append(seq)
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
            bad, malformed = self._bad_values, self._malformed
        s = {"received": len(times), "malformed": malformed, "bad_values": bad,
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


def make_server(host: str, port: int, recorder: Recorder, commander: Commander | None = None) -> ThreadingHTTPServer:
    commander = commander or Commander()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlsplit(self.path).path
            if path in VALUE_PATHS:
                self._values()
            elif path == "/cmd":
                try:
                    cid = commander.issue(parse_command(self.path))
                except ValueError as e:
                    self._reply(400, f"error: {e}")
                    return
                self._reply(200, f"id={cid}")
            else:
                self._reply(404, "error: unknown path")

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


def report_q2(c: dict) -> str:
    lines = ["---- 指示の結果 ----"]
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


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Stormworks のマイコンと値・指示をやり取りする中継プログラム")
    ap.add_argument("--mode", choices=("q1", "q2"), default="q1",
                    help="q1: 値が届くかを数える（既定）。q2: 指示を10回出して反映までの時間を測る")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"待ち受けるポート（既定 {DEFAULT_PORT}）")
    ap.add_argument("--seconds", type=float, default=Q1_MIN_SECONDS,
                    help="q1: 最初の受信からこの秒数で自動で止める。0 なら止めない（既定 60）")
    ap.add_argument("--values", type=int, default=DEFAULT_VALUES, help="1回に届くはずの値の数（既定 32）")
    ap.add_argument("--cmd-values", default="1,0",
                    help="q2: 出力1に順に出す値（カンマ区切り、既定 1,0）")
    ap.add_argument("--logdir", default="logs", help="記録を書くフォルダ（既定 logs）")
    args = ap.parse_args(argv)
    cmd_values = [float(x) for x in args.cmd_values.split(",")]

    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{args.mode}-{stamp}"
    log_path = logdir / f"{name}.jsonl"
    rec = Recorder(expected_values=args.values, log_path=log_path)
    com = Commander()
    server = make_server("127.0.0.1", args.port, rec, com)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"待ち受け中: http://127.0.0.1:{args.port}/v   記録: {log_path}")
    if args.mode == "q2":
        print(f"値が届き始めたら、{Q2_INTERVAL:g}秒ごとに出力1へ指示を{Q2_COMMANDS}回出します。")
    print("ゲームで機体を出すと受信が始まります。Ctrl+C で止めます。")

    last_print = 0.0
    q2_done_at = None
    try:
        while True:
            time.sleep(0.1)
            t0 = rec.first_time()
            if t0 is None:
                continue
            now = time.monotonic()
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
                      f"欠け {s['missing']}件{extra}")
            if args.mode == "q1" and args.seconds > 0 and now - t0 >= args.seconds + 0.5:
                break
    except KeyboardInterrupt:
        print("\n止めました。")
    finally:
        server.shutdown()
        server.server_close()
        rec.close()

    s = rec.summary()
    out = {"values": s}
    if args.mode == "q2":
        out["commands"] = com.summary()
    summary_path = logdir / f"{name}-summary.json"
    summary_path.write_text(json.dumps(out if args.mode == "q2" else s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report(s) if args.mode == "q1" else report_q2(out["commands"]))
    print(f"まとめ: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
