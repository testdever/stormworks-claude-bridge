#!/usr/bin/env python3
"""中継プログラム（試作 Q1：マイコンから値が届くか）。

Stormworks の機体のマイコンが async.httpGet で送ってくる値を受け取り、
受信件数・欠け・1秒あたりの件数を数えて記録する。標準ライブラリだけで動く。

使い方:
    python relay/relay.py                 # ポート 8765 で待つ。最初の受信から60秒で止まる
    python relay/relay.py --seconds 0     # 自動では止めない（Ctrl+C で止める）

マイコンからの要求の形:
    /q1?s=<通し番号>&t=<tick>&v=<値1>,<値2>,...
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
Q1_MIN_SECONDS = 60
Q1_MIN_PER_SEC = 10


def parse_q1(path: str) -> tuple[int, int, list[float]]:
    """要求のパスから (通し番号, tick, 値の列) を取り出す。形が違えば ValueError。"""
    q = parse_qs(urlsplit(path).query, keep_blank_values=True)
    try:
        seq = int(q["s"][0])
        tick = int(q["t"][0])
        raw = q["v"][0]
    except (KeyError, IndexError) as e:
        raise ValueError(f"項目 {e} がない") from e
    vals = [float(x) for x in raw.split(",")] if raw else []
    return seq, tick, vals


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

    def add(self, seq: int, tick: int, values: list[float], t: float | None = None) -> None:
        t = time.monotonic() if t is None else t
        with self._lock:
            self._times.append(t)
            self._seqs.append(seq)
            if len(values) != self.expected_values:
                self._bad_values += 1
            if self._log:
                row = {"t": round(t, 4), "seq": seq, "tick": tick,
                       "v": [v if math.isfinite(v) else str(v) for v in values]}
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


def make_server(host: str, port: int, recorder: Recorder) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if urlsplit(self.path).path != "/q1":
                self._reply(404, "error: unknown path")
                return
            try:
                seq, tick, vals = parse_q1(self.path)
            except ValueError as e:
                recorder.add_malformed()
                self._reply(200, f"error: {e}")
                return
            recorder.add(seq, tick, vals)
            self._reply(200, "ok")

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


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Stormworks のマイコンから値を受け取る中継プログラム（試作 Q1）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"待ち受けるポート（既定 {DEFAULT_PORT}）")
    ap.add_argument("--seconds", type=float, default=Q1_MIN_SECONDS,
                    help="最初の受信からこの秒数で自動で止める。0 なら止めない（既定 60）")
    ap.add_argument("--values", type=int, default=DEFAULT_VALUES, help="1回に届くはずの値の数（既定 32）")
    ap.add_argument("--logdir", default="logs", help="記録を書くフォルダ（既定 logs）")
    args = ap.parse_args(argv)

    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logdir / f"q1-{stamp}.jsonl"
    rec = Recorder(expected_values=args.values, log_path=log_path)
    server = make_server("127.0.0.1", args.port, rec)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"待ち受け中: http://127.0.0.1:{args.port}/q1   記録: {log_path}")
    print("ゲームで機体を出すと受信が始まります。Ctrl+C で止めます。")

    try:
        while True:
            time.sleep(1)
            t0 = rec.first_time()
            if t0 is None:
                continue
            now = time.monotonic()
            s = rec.summary()
            print(f"経過 {now - t0:5.0f}秒  受信 {s['received']}件  直近1秒 {rec.count_since(now - 1)}件  "
                  f"欠け {s['missing']}件")
            if args.seconds > 0 and now - t0 >= args.seconds + 0.5:
                break
    except KeyboardInterrupt:
        print("\n止めました。")
    finally:
        server.shutdown()
        server.server_close()
        rec.close()

    s = rec.summary()
    summary_path = logdir / f"q1-{stamp}-summary.json"
    summary_path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report(s))
    print(f"まとめ: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
