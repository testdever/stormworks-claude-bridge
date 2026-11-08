+++
id = "E-012"
grade = "measured"
date = "2026-11-08"
source = "docs/evidence/data/q4-20261108-230802.jsonl"
quote = "サーバー側ではビークルが0/1から1/1になり、Playerは常に0だった。"
questions = []
claims = [
  "rom\\data\\missions\\ClaudeBridge に置いた専用サーバー用の ClaudeBridge は、誰も接続していない専用サーバーで動き、中継プログラムと通信できた（連絡 2706 回）",
  "専用サーバーから、%APPDATA%\\Stormworks\\data\\vehicles に保存した claude_test・claude_test_ka を server.spawnVehicle で置け、片付けられた",
  "キープアクティブブロックのない claude_test は、マイコンからの値が60秒間0件だった（getVehicleSimulating は偽のまま）",
  "キープアクティブブロックを積んだ claude_test_ka は、マイコンが60秒間動き続けた（1秒に約20件、tick は1秒に約62進んだ）。サーバー画面の vehicles は 0/1 から 1/1 になった",
  "claude_test_ka は置いた直後に落ち（縦の速度 -16 m/s）、転がって回り、約29秒で止まって休んだ。そのあと値は変わらなかった",
  "専用サーバーでは物理センサーの位置（ch1〜3）が60秒間ずっと 0 だった（1人用の Q1 では実際の座標が出ていた）",
  "アドオンから見たプレイヤーの数は1人だったが、サーバー画面は常に0人。専用サーバーの getPlayers にはサーバー自身が入っていると見られる",
  "専用サーバー（server64）の負荷は CPU 平均 1.4%・最大 2.1%（16論理コアに対する割合）、メモリ最大 1362.6 MB",
]
+++

手順：本人がメインPCで、Claude の示した手順で行った。専用サーバー用の ClaudeBridge（game/addon/server/ClaudeBridge）を Steam\steamapps\common\Stormworks\rom\data\missions\ に置き、server_config.xml の playlists を rom/data/missions/ClaudeBridge の1行にし、autosave_server を消した。DebugView を開き、中継プログラムを `--mode q4` で起動してから、server64.exe を起動した。ゲームからは接続しなかった。中継プログラムは claude_test と claude_test_ka を1台ずつ (-260.9, 8, -18949) に置き、出力1を1にして60秒ずつ値を記録した。

結果：claims のとおり。Q4 の基準（どの10秒の区切りでも値が届いて変わる、プレイヤー0人）は、判定の上では満たさなかった。ただし、(1) プレイヤー数はサーバー自身を数えていた、(2) claude_test_ka の後半30秒が「止まっている」のは、落ちて転がったあと休んだためで、物理が止まったためとは言えない、の2点で、この確かめ方では Q4 を判定できない。そのため、この記録は Q4 の判定に使わない。次の試しでは、サーバー自身をプレイヤーに数えないようにし、10秒ごとに機体を15m持ち上げて落とし、物理が進んでいるかを毎回確かめる。
