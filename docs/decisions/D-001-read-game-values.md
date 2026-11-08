+++
id = "D-001"
title = "ゲーム内の値を Claude に渡す方法"
status = "accepted"
level = "core"
date = "2026-11-08"
functions = ["FN2", "FN3"]
criteria = ["W1", "W2", "W3", "W4"]
datum = "A"
chosen = "H"
override_reason = ""
depends_on = []
survey = ["docs/evidence/E-001-game-data-survey.md"]
supersedes = []
superseded_by = ""
blocks_future = ["なし"]
y_statement = "Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、ゲーム内の値を Claude に渡し指示をゲームに伝えるため、「マイコンとアドオンの両方を中継プログラムにつなぎ、値と指示を受け渡す」を選び、「アドオンのスクリプトが値を送り、返事で Claude の指示も受け取る」「機体のマイコンが値を中継プログラムに送る」「ゲーム画面を画像認識で数値にする」は採らなかった。実験を人の手なしで一通り回せ、センサーの値を配線するだけで読める利点の代わりに、マイコン側・アドオン側・中継プログラムの3つを作る手間を受け入れる。"
suspended_at = ""
pending_question = ""

[trial]
check = "別PCで小さな試作を作り、マイコンから値が届くか、返事の指示で機体が動くか、アドオンから機体を置き直せるかを確かめる"
revisit_if = "マイコンから値が届かない、または返事の指示が機体に反映されないならマイコンを使う部分を、アドオンから機体を置き直せないならアドオンを使う部分を見直す"
questions = ["Q1", "Q2", "Q3"]

[[option]]
id = "A"
name = "アドオンのスクリプトが値を中継プログラムに送る"
family = "ゲーム内スクリプトの通信"

[[option]]
id = "B"
name = "機体のマイコンが値を中継プログラムに送る"
family = "機体内スクリプトの通信"

[[option]]
id = "C"
name = "アドオンのスクリプトが値を送り、返事で Claude の指示も受け取る"
family = "ゲーム内スクリプトの通信（双方向）"

[[option]]
id = "H"
name = "マイコンとアドオンの両方を中継プログラムにつなぎ、値と指示を受け渡す"
family = "スクリプトの通信（機体内とゲーム内の併用）"

[[option]]
id = "D"
name = "スクリプトのデバッグ出力を、ログを拾う道具で読み取る"
family = "ログ"

[[option]]
id = "E"
name = "ゲーム画面を画像認識で数値にする"
family = "画面"

[[option]]
id = "F"
name = "ゲームのメモリを外から読む"
family = "メモリ"

[[option]]
id = "G"
name = "作らない（今まで通り本人が測って伝える）"
family = "作らない"

[[cell]]
option = "A"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "HTTP の通信はゲームの裏で動き、マウス・キーボード・画面を使わない。ゲームは別PCか専用サーバーで動かせる"

[[cell]]
option = "B"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "A と同じ通信の仕組みで、入力を奪わない"

[[cell]]
option = "C"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "指示も通信の返事で受け取るので、マウス・キー操作を使わない"

[[cell]]
option = "H"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "A・B と同じ通信だけを使い、マウス・キー操作を使わない"

[[cell]]
option = "D"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "ログを拾う道具は裏で動く。画面は使わない"

[[cell]]
option = "E"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "画面を描く必要があるが、別PCで動かせばメインPCの画面は奪わない"

[[cell]]
option = "F"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "メモリの読み取りは裏で動き、入力を使わない"

[[cell]]
option = "G"
criterion = "M1"
value = "fail"
grade = "reported"
source = "docs/evidence/E-002-user-tied-to-game.md"
note = ""

[[cell]]
option = "A"
criterion = "M2"
value = "pass"
grade = "third_party"
source = "docs/evidence/E-001-game-data-survey.md"
note = ""

[[cell]]
option = "B"
criterion = "M2"
value = "pass"
grade = "third_party"
source = "docs/evidence/E-001-game-data-survey.md"
note = ""

[[cell]]
option = "C"
criterion = "M2"
value = "pass"
grade = "third_party"
source = "docs/evidence/E-001-game-data-survey.md"
note = ""

[[cell]]
option = "H"
criterion = "M2"
value = "pass"
grade = "third_party"
source = "docs/evidence/E-001-game-data-survey.md"
note = ""

[[cell]]
option = "D"
criterion = "M2"
value = "pass"
grade = "third_party"
source = "docs/evidence/E-001-game-data-survey.md"
note = ""

[[cell]]
option = "E"
criterion = "M2"
value = "pass"
grade = "inference"
source = ""
note = "中継の画像認識が数値にしてから渡すので、Claude は映像を見ない"

[[cell]]
option = "F"
criterion = "M2"
value = "pass"
grade = "inference"
source = ""
note = "読み取った値を数値として渡せる"

[[cell]]
option = "G"
criterion = "M2"
value = "fail"
grade = "reported"
source = "docs/evidence/E-002-user-tied-to-game.md"
note = ""

[[cell]]
option = "B"
criterion = "W1"
value = "S"
grade = "inference"
source = ""
note = "値を送る点は A と同じで、ゲームへの指示は別の手段が要る"

[[cell]]
option = "B"
criterion = "W2"
value = "+"
grade = "inference"
source = ""
note = "マイコンは配線した値をそのまま読める。アドオンは名前付きのダイヤルやボタン経由でしか機体の値を読めず、値ごとに機体側の準備が要る"

[[cell]]
option = "B"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "どちらも必要な数値だけを送れる"

[[cell]]
option = "C"
criterion = "W1"
value = "+"
grade = "inference"
source = ""
note = "指示も同じ通り道で受け取れるので、値を読んで次の操作をする流れを人の手なしで回せる"

[[cell]]
option = "C"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の値の読み方は A と同じ"

[[cell]]
option = "C"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "送る値は A と同じ"

[[cell]]
option = "H"
criterion = "W1"
value = "+"
grade = "inference"
source = ""
note = "アドオンで機体の配置やリセット、マイコンで機体への入力ができ、実験を一通り人の手なしで回せる"

[[cell]]
option = "H"
criterion = "W2"
value = "+"
grade = "inference"
source = ""
note = "センサーの値はマイコンで直接読めるので、確認実験は機体にマイコンを1つ足すだけで済む"

[[cell]]
option = "H"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "どちらも必要な数値だけを送れる"

[[cell]]
option = "D"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "読み取り専用で指示は別の手段が要り、ログを拾う道具も同じPCで動かし続ける必要がある"

[[cell]]
option = "D"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "値の出し方はスクリプトに書く点で A と同じ"

[[cell]]
option = "D"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "必要な値だけを書き出せる"

[[cell]]
option = "E"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "視点や表示が少し変わるだけで読み取りが崩れ、見張りが要る"

[[cell]]
option = "E"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "読ませたい値を毎回画面に読める形で並べる準備が要る"

[[cell]]
option = "E"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "中継で数値にすれば Claude が読む量は同じ"

[[cell]]
option = "F"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "ゲームの更新でメモリの場所が変わると止まる"

[[cell]]
option = "F"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "センサーの値ごとにメモリの場所を探す手間がかかる"

[[cell]]
option = "F"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "数値だけを渡せる"

[[cell]]
option = "B"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "読める値の範囲が違うだけで、異常に気づく手段は A と同じ"

[[cell]]
option = "C"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "異常に気づく手段は A と同じ"

[[cell]]
option = "H"
criterion = "W4"
value = "+"
grade = "inference"
source = ""
note = "センサーの値（マイコン）と機体の位置や有無（アドオン）の両方を見られるので、機体が壊れた・消えたなどにも気づける"

[[cell]]
option = "D"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "出せる値は A と同じ"

[[cell]]
option = "E"
criterion = "W4"
value = "+"
grade = "inference"
source = ""
note = "画面には、事前に想定していない異常（機体がひっくり返った等）も映る"

[[cell]]
option = "F"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "読める値は探したメモリの場所に限られ、A と同程度"

+++

Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、ゲーム内の値を Claude に渡し指示をゲームに伝えるため、「マイコンとアドオンの両方を中継プログラムにつなぎ、値と指示を受け渡す」を選び、「アドオンのスクリプトが値を送り、返事で Claude の指示も受け取る」「機体のマイコンが値を中継プログラムに送る」「ゲーム画面を画像認識で数値にする」は採らなかった。実験を人の手なしで一通り回せ、センサーの値を配線するだけで読める利点の代わりに、マイコン側・アドオン側・中継プログラムの3つを作る手間を受け入れる。

本人が一番重く見ているのは、実験中に拘束されないこと（W1）。H はアドオンで機体の配置や片付けを、マイコンでセンサーの読み取りと機体への入力を受け持ち、同じ中継プログラムを通して値と指示をやり取りするので、実験を一通り人の手なしで回せる。センサーの値はマイコンに配線するだけで読めるので、小さな確認実験の準備も少ない（W2）。

アドオンだけの案（A・C）は、機体の値を名前付きのダイヤルやボタン経由でしか読めず、値ごとに機体側の準備が要る（W2）。マイコンだけの案（B）は機体の置き直しができず、実験ごとに人の手が要る（W1）。デバッグ出力を拾う案（D）は読み取り専用で、指示に別の仕組みが要る（W1）。画像認識（E）とメモリの読み取り（F）は表示やゲームの更新で壊れやすい（W1・W2）。作らない案（G）は本人が拘束されるので、外せない条件（M1・M2）で外れた。

選んだ理由（本人）：「大事なのは拘束されないことだから」。評価の多くは調べた情報からの推論なので、別PCでの試作で Q1〜Q3 を確かめる。

2026-11-08 見直し：企画書に「実験中に想定外のことが起きたら気づける」（W4）が加わったので比べ直した。H はセンサーの値と機体の位置や有無の両方を見られるので W4 でも有利で、結論は変わらない。
