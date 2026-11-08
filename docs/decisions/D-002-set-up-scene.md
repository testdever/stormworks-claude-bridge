+++
id = "D-002"
title = "実験の場面を用意する方法"
status = "accepted"
level = "core"
date = "2026-11-08"
functions = ["FN1"]
criteria = ["W1", "W2", "W3", "W4"]
datum = "B"
chosen = "C"
override_reason = "本人：「最初はメインでいいよ。addonをすべて切った状態ならそんなに重くならないと思うし、描画しないならそもそもGPUをそう食わないだろうから。」別PCで動かす案（B）とは同点で、本人の判断で選んだ"
depends_on = ["D-001"]
survey = ["docs/evidence/E-003-scene-setup-survey.md"]
supersedes = []
superseded_by = ""
blocks_future = ["なし"]
y_statement = "Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、実験の場面を人の操作なしで用意するため、「メインPCの裏で専用サーバーを動かし、アドオンが機体を置く」を選び、「別PCで専用サーバーを動かし、アドオンが機体を置く」「別PCでゲーム本体を動かし、アドオンが機体を置く」は採らなかった。速いPCで計算でき別PCを点けずに済む利点の代わりに、実験中にメインPCの CPU とメモリを使うことを受け入れる。"
suspended_at = ""
pending_question = ""
[trial]
check = "メインPCの裏で、ほかのアドオンを切った専用サーバーを動かして1回の実験を回し、誰も接続していなくても物理が進むかと、本人の作業が重くならないかを確かめる"
revisit_if = "誰も接続していないと物理が進まないなら、ゲーム本体を接続する形に見直す。本人が重さを感じたら、別PCの専用サーバーに移す"
questions = ["Q4", "Q5"]

[[option]]
id = "A"
name = "別PCでゲーム本体を動かし、アドオンが機体を置く"
family = "別PC・ゲーム本体"

[[option]]
id = "B"
name = "別PCで専用サーバーを動かし、アドオンが機体を置く"
family = "別PC・専用サーバー"

[[option]]
id = "C"
name = "メインPCの裏で専用サーバーを動かし、アドオンが機体を置く"
family = "メインPC・専用サーバー"

[[option]]
id = "D"
name = "メインPCの仮想マシンでゲーム本体を動かす"
family = "メインPC・仮想マシン"

[[option]]
id = "E"
name = "メインPCでゲーム本体を裏のウィンドウで動かす"
family = "メインPC・ゲーム本体"

[[option]]
id = "G"
name = "機体を置いたセーブを先に作り、別PCの専用サーバーで毎回そのセーブから始める"
family = "セーブの使い回し"

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
note = "専用サーバーは画面を描かず、マウス・キーボードも使わない。CPU とメモリは使う"

[[cell]]
option = "D"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "仮想マシンの窓は最小化しておける。ただし GPU を仮想マシンに渡せるかは分からない"

[[cell]]
option = "E"
criterion = "M1"
value = "?"
grade = "unknown"
source = ""
note = ""

[[cell]]
option = "G"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "別PCで動くので、メインPCの入力も画面も使わない"

[[cell]]
option = "F"
criterion = "M1"
value = "fail"
grade = "reported"
source = "docs/evidence/E-002-user-tied-to-game.md"
note = ""

[[cell]]
option = "A"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "ゲーム本体はセーブを開くまでにメニュー操作が要り、自動で始められない（E-003 で起動時にセーブへ入る方法が見つからない）"

[[cell]]
option = "A"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の置き方はアドオンで同じ"

[[cell]]
option = "A"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は D-001 の作りで同じ"

[[cell]]
option = "C"
criterion = "W1"
value = "S"
grade = "inference"
source = ""
note = "起動のしかたは B と同じ。動かすPCが違うだけ"

[[cell]]
option = "C"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の置き方は B と同じ"

[[cell]]
option = "C"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "D"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "中身はゲーム本体なので A と同じくメニュー操作が要る。加えて仮想マシンで GPU が使えないと動かない"

[[cell]]
option = "D"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の置き方はアドオンで同じ"

[[cell]]
option = "D"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "E"
criterion = "W1"
value = "-"
grade = "inference"
source = ""
note = "ゲーム本体なのでメニュー操作が要る"

[[cell]]
option = "E"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "機体の置き方はアドオンで同じ"

[[cell]]
option = "E"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "G"
criterion = "W1"
value = "S"
grade = "inference"
source = ""
note = "起動のしかたは B と同じ"

[[cell]]
option = "G"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "新しい実験のたびに、本人がゲームで機体を置いたセーブを作る必要がある"

[[cell]]
option = "G"
criterion = "W3"
value = "S"
grade = "inference"
source = ""
note = "渡す値は同じ"

[[cell]]
option = "A"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "画面は出るが、Claude は映像を見ないので、異常に気づく手段は B と同じ"

[[cell]]
option = "C"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "動かすPCが違うだけで B と同じ"

[[cell]]
option = "D"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "映像は見ないので B と同じ"

[[cell]]
option = "E"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "映像は見ないので B と同じ"

[[cell]]
option = "G"
criterion = "W4"
value = "S"
grade = "inference"
source = ""
note = "B と同じ"

+++

Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、実験の場面を人の操作なしで用意するため、「メインPCの裏で専用サーバーを動かし、アドオンが機体を置く」を選び、「別PCで専用サーバーを動かし、アドオンが機体を置く」「別PCでゲーム本体を動かし、アドオンが機体を置く」は採らなかった。速いPCで計算でき別PCを点けずに済む利点の代わりに、実験中にメインPCの CPU とメモリを使うことを受け入れる。

ゲーム本体を使う案（A・D・E）は、起動してからセーブを開くまでにメニュー操作が要り、人の手なしで実験を始められない（W1）。機体を置いたセーブを使い回す案（G）は、新しい実験のたびに本人がセーブを作る必要がある（W2）。作らない案（F）は本人が拘束されるので、外せない条件（M1）で外れた。

別PCで専用サーバーを動かす案（B）とは、比べた点では差がなかった。本人が「最初はメインでいいよ。addonをすべて切った状態ならそんなに重くならないと思うし、描画しないならそもそもGPUをそう食わないだろうから」と、メインPCを選んだ。動かすPCを替えるだけで B に移れる。

まだ確かめていないことは、誰も接続していない専用サーバーで物理が進むか（Q4）と、メインPCの作業が重くならないか（Q5）。試作で確かめる。

2026-11-08 見直し：企画書に「実験中に想定外のことが起きたら気づける」（W4）が加わったので比べ直した。どの案も Claude は映像を見ないので W4 では差がつかず、B と C の同点のまま。結論は変わらない。
