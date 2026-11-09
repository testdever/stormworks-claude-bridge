+++
id = "D-004"
title = "実験の場面を用意する方法（見直し）"
status = "proposed"
level = "core"
date = "2026-11-08"
functions = ["FN1"]
criteria = ["W1", "W2", "W3", "W4"]
datum = "A"
chosen = ""
override_reason = ""
depends_on = ["D-001"]
survey = ["docs/evidence/E-003-scene-setup-survey.md", "docs/evidence/E-009-addon-api.md"]
supersedes = ["D-002"]
superseded_by = ""
blocks_future = []
y_statement = ""
suspended_at = ""
pending_question = ""

[[option]]
id = "A"
name = "別PCでゲーム本体（1人用）を起動したままにし、アドオンが機体を置く"
family = "別PC・ゲーム本体"

[[option]]
id = "B"
name = "別PCで専用サーバーを動かし、誰も接続しない"
family = "別PC・専用サーバー"

[[option]]
id = "C"
name = "メインPCの裏で専用サーバーを動かし、誰も接続しない"
family = "メインPC・専用サーバー"

[[option]]
id = "J"
name = "メインPCの裏で専用サーバーを動かし、別PCのゲーム本体を接続しておく"
family = "専用サーバーと接続の併用"

[[option]]
id = "E"
name = "メインPCでゲーム本体を裏のウィンドウで動かす"
family = "メインPC・ゲーム本体"

[[option]]
id = "D"
name = "メインPCの仮想マシンでゲーム本体を動かす"
family = "メインPC・仮想マシン"

[[option]]
id = "F"
name = "作らない（本人が毎回ゲームを立ち上げて機体を置く）"
family = "作らない"

[[cell]]
option = "A"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "別PCで動くので、メインPCの入力も画面も使わない"

[[cell]]
option = "B"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "別PCで動くので、メインPCの入力も画面も使わない"

[[cell]]
option = "C"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "専用サーバーは画面を描かず、マウス・キーボードも使わない"

[[cell]]
option = "J"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "メインPCでは画面を描かない専用サーバーだけが動き、ゲーム本体は別PC"

[[cell]]
option = "E"
criterion = "M1"
value = "?"
grade = "unknown"
source = ""
note = ""

[[cell]]
option = "D"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "仮想マシンの窓は最小化しておける。ただし GPU を仮想マシンに渡せるかは分からない"

[[cell]]
option = "F"
criterion = "M1"
value = "fail"
grade = "reported"
source = "docs/evidence/E-002-user-tied-to-game.md"
note = ""

[[cell]]
option = "B"
criterion = "W1"
value = "+"
grade = "inference"
source = ""
note = "C と同じ専用サーバーの形を別PCで動かす。E-014 はメインPCで確かめたもの。使い始めはサーバーを起動するだけでよい"

[[cell]]
option = "C"
criterion = "W1"
value = "+"
grade = "inference"
source = ""
note = "誰も接続していない専用サーバーで、アドオンが機体を置き、キープアクティブの機体の物理が60秒進み続けた（E-014）。専用サーバーは server64.exe を起動するだけでワールドが始まる。A はゲーム本体なので、使い始めるたびにメニューを操作してワールドに入る必要がある（E-003）"

[[cell]]
option = "J"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "別PCのゲーム本体が接続し続けている必要があり、切れると実験が止まる。プレイヤーが接続すればアドオンが動くかも、同じPCからは接続できず確かめられていない"

[[cell]]
option = "E"
criterion = "W1"
value = "S"
grade = "inference"
source = ""
note = "A と同じくゲーム本体を一度起動して入っておけば、あとはアドオンと中継プログラムで回る"

[[cell]]
option = "D"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "中身は A と同じだが、仮想マシンで GPU が使えないとゲームが動かない"

[[cell]]
option = "B"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "C と同じく、キープアクティブブロックが要り、物理センサーの位置が使えない"

[[cell]]
option = "C"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "試す機体にキープアクティブブロックを積む必要がある（積まないとマイコンも物理も動かない、E-014）。物理センサーの位置（ch1〜3）が専用サーバーでは落ちている間も 0 のままだった（実測、E-014）。位置の出力が働いていないと見られ（推論）、位置を使う実験には別の手段が要るかもしれない"

[[cell]]
option = "J"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の置き方と値の読み方は A と同じ"

[[cell]]
option = "E"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "A と同じ"

[[cell]]
option = "D"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "A と同じ"

[[cell]]
option = "B"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は D-001 の作りで同じ"

[[cell]]
option = "C"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "J"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "E"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "D"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "B"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "異常に気づく手段は中継プログラムの見張りで同じ"

[[cell]]
option = "C"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "同じ"

[[cell]]
option = "J"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "同じ"

[[cell]]
option = "E"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "同じ"

[[cell]]
option = "D"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "同じ"

+++
