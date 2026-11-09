+++
id = "D-003"
title = "実験の手順を最後まで流す方法"
status = "accepted"
level = "core"
date = "2026-11-08"
functions = ["FN4", "FN5"]
criteria = ["W1", "W2", "W3", "W4"]
datum = "A"
chosen = "H"
override_reason = ""
depends_on = ["D-001", "D-002"]
survey = ["docs/evidence/E-004-run-experiment-survey.md"]
supersedes = []
superseded_by = ""
blocks_future = ["なし"]
y_statement = "Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、実験の手順を最後まで流して結果を残すため、「Claude が手順書と「止める条件」を書き、中継プログラムが毎回の値を見張りながら最後まで流して、全部の値を記録に残す」を選び、「Claude が道具を1手ずつ呼んで進め、結果は Claude が会話から記録に書く」「Claude が実験の手順書を書き、中継プログラムが最後まで流して、結果を記録ファイルに残す」は採らなかった。本人の手も Claude の操作もなしに流せて異常にも気づける利点の代わりに、途中で Claude がその場の判断で手順を変えにくいことを受け入れる。"
suspended_at = ""
pending_question = ""
[[option]]
id = "A"
name = "Claude が道具を1手ずつ呼んで進め、結果は Claude が会話から記録に書く"
family = "対話で1手ずつ"

[[option]]
id = "B"
name = "Claude が実験の手順書を書き、中継プログラムが最後まで流して、結果を記録ファイルに残す"
family = "手順書を外で実行"

[[option]]
id = "C"
name = "Claude がアドオンの Lua に手順を書き、ゲームの中で最後まで流して結果を送る"
family = "ゲーム内で実行"

[[option]]
id = "D"
name = "作らない（本人が手順を進めて結果を書き留める）"
family = "作らない"

[[cell]]
option = "A"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "道具は中継プログラムとの通信だけで、メインPCの入力も画面も使わない"

[[cell]]
option = "B"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "中継プログラムが裏で流すだけで、入力も画面も使わない"

[[cell]]
option = "C"
criterion = "M1"
value = "pass"
grade = "inference"
source = ""
note = "ゲームの中で流れるだけで、入力も画面も使わない"

[[cell]]
option = "D"
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
note = "手順を流している間は Claude の操作が要らない。1手ずつ呼ぶ形は手数が多く、道具の使用許可の確認などで本人の手が要る場面が増えやすい"

[[cell]]
option = "B"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "手順書は短く、Claude が書くので本人の準備は変わらない"

[[cell]]
option = "B"
criterion = "W3"
value = "+"
grade = "third_party"
source = "docs/evidence/E-004-run-experiment-survey.md"
note = ""

[[cell]]
option = "C"
criterion = "W1"
value = "+"
grade = "inference"
source = ""
note = "B と同じく、流している間は Claude の操作が要らない"

[[cell]]
option = "C"
criterion = "W2"
value = "-"
grade = "inference"
source = ""
note = "アドオンの Lua を書き換えるたびにアドオンを読み込み直す（専用サーバーの再起動など）手間がかかる"

[[cell]]
option = "C"
criterion = "W3"
value = "+"
grade = "third_party"
source = "docs/evidence/E-004-run-experiment-survey.md"
note = ""

[[option]]
id = "H"
name = "Claude が手順書と「止める条件」を書き、中継プログラムが毎回の値を見張りながら最後まで流して、全部の値を記録に残す"
family = "手順書を外で実行（見張りつき）"

[[cell]]
option = "H"
criterion = "M1"
value = "pass"
grade = "measured"
source = "docs/evidence/E-017-q9-game-in-background.md"
note = "ゲームを裏にして手順書を流す間、本人のマウス・キーボード・画面を取らなかった（試作 Q9）"

[[cell]]
option = "H"
criterion = "W1"
value = "+"
grade = "measured"
source = "docs/evidence/E-016-q6-script-runs-to-end.md"
note = "手順書を渡してから記録が残るまで、本人の操作はワールドに入ったことだけだった（試作 Q6）"

[[cell]]
option = "H"
criterion = "W2"
value = "S"
grade = "inference"
source = ""
note = "止める条件は Claude が書き、どの実験にも共通の見張り（物理が進んでいるか、機体があるか、値が壊れていないか）は使い回せる"

[[cell]]
option = "H"
criterion = "W3"
value = "+"
grade = "third_party"
source = "docs/evidence/E-004-run-experiment-survey.md"
note = ""

[[cell]]
option = "H"
criterion = "W4"
value = "+"
grade = "measured"
source = "docs/evidence/E-018-q7-watch-stops-on-faults.md"
note = "わざと起こした3種類の異常（機体を消す、値を壊す、一時停止）のすべてで、0.1〜3.1 秒で止まり理由が残った（試作 Q7）。置いた場所に足場がなく機体が落ち続けたときも、止める条件で 5.5 秒で止まった"

[[cell]]
option = "B"
criterion = "W4"
value = "-"
grade = "inference"
source = ""
note = "流している間は誰も値を見ず、結果に表れない異常は見逃す"

[[cell]]
option = "C"
criterion = "W4"
value = "-"
grade = "inference"
source = ""
note = "B と同じく、流している間は誰も値を見ない"

+++

Stormworks の計測実験を Claude に任せ、本人が拘束されないようにする中で、実験の手順を最後まで流して結果を残すため、「Claude が手順書と「止める条件」を書き、中継プログラムが毎回の値を見張りながら最後まで流して、全部の値を記録に残す」を選び、「Claude が道具を1手ずつ呼んで進め、結果は Claude が会話から記録に書く」「Claude が実験の手順書を書き、中継プログラムが最後まで流して、結果を記録ファイルに残す」は採らなかった。本人の手も Claude の操作もなしに流せて異常にも気づける利点の代わりに、途中で Claude がその場の判断で手順を変えにくいことを受け入れる。

本人が一番重く見ているのは拘束されないこと（W1）で、次が想定外のことに気づけること（W4）。H は手順書を中継プログラムが流すので、流している間は本人の手も Claude の操作も要らない。毎回の値を、事前に決めた止める条件と、どの実験にも共通の見張り（物理が進んでいるか、機体があるか、値が壊れていないか）に照らす。全部の値を残すので、想定していなかった異常も後から記録を見て探せる。

手順書を流すだけの案（B）と、手順をアドオンに書く案（C）は、流している間は誰も値を見ないので異常を見逃す（W4）。C はさらに、手順を変えるたびにアドオンを読み込み直す手間がかかる（W2）。Claude が1手ずつ進める案（A）は、手数が多く本人に確認が回りやすく（W1）、読み込む量も多い（W3）。作らない案（D）は本人が拘束されるので、外せない条件（M1）で外れた。

見張りの条件は、問題が見つかるたびに共通の見張りに足していく。

試作で、手順書が本人の手なしで最後まで流れること（Q6）と、わざと起こした3種類の異常のすべてで見張りが止めて理由を残すこと（Q7）を確かめた。置いた場所に足場がなく機体が落ち続けたときも、手順書に書いた止める条件で止まった。
