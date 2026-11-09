# 引き継ぎ（2026-11-09、クラウドのセッションから本人の PC のセッションへ）

本人の PC の Claude Code（デスクトップアプリ）で続きをするための覚え書き。最初にこれと README.md を読む。

## 本人について

- 返答はすべて日本語（CLAUDE.md）。
- CLI は好きではない。コマンドは Claude が打ち、本人は許可するだけにする。
- ゲーム（Stormworks）の起動・ワールドに入る・ワークベンチでの機体の保存は本人がやる。それ以外（relay.py の起動、ログを読む、ファイルを置く、git）は Claude がやる。
- ゲームの中のことを頼むときは、どの画面で何をするかを具体的に書く。

## 何を作っているか

Claude に Stormworks の計測実験を任せ、本人がゲームの前に張り付かずに済むようにする。
企画書は `docs/brief.md`、決めたことは `docs/decisions/`、試作で確かめることは `docs/verification.md`、
調べたことと実測の記録は `docs/evidence/` と `docs/notes/`。

形：ゲームの中のアドオン（`game/addon/ClaudeBridge`）と機体のマイコン（`game/q2_values_and_commands.lua`）が、
同じ PC の中継プログラム（`relay/relay.py`、ポート 8765）と HTTP でやり取りする。
Claude は手順書（`experiments/*.json`）を書き、`python relay/relay.py --run 手順書` で流す。見張りが異常で止める。

## 決まっていること

| 機能 | 決定 | 状況 |
|---|---|---|
| 値を渡す・指示を伝える | D-001：マイコンとアドオンの両方を中継プログラムにつなぐ | 確かめ済み（Q1〜Q3） |
| 場面を用意する | D-004：メインPCの裏でゲーム本体（1人用、ウィンドウ表示）を動かす | Q9（マウス・画面を奪わないか）・Q10（実際の規模で重くないか）を作りながら確かめる。だめなら別PC（ノートPC）に見直す |
| 手順を流して記録を残す | D-003：見張りつきの手順書を中継プログラムが流す | Q6（最後まで流れるか）・Q7（異常で止まるか）を確かめる |

誰も接続していない専用サーバーは、地面と海が読み込まれず機体が落ち続けるので外した（`docs/notes/dedicated-server.md`）。

## 次にやること

1. **Q6・Q9：** `python relay/relay.py --run experiments/q6_physics_sensor_order.json`。
   前回は、置いてから3秒で値が来ず止まった。最初の値を15秒まで待つように直した版で、もう一度。
   その間、本人がふだんの作業をして、マウス・キーボード・画面を取られたか、音が気になったかを聞く（Q9）。
   15秒たっても値が来なければ、`claude_test` のマイコンの Lua が新しい版で保存されているか、Lua のエラーが出ていないかを本人に確かめてもらう。
2. **Q7：** `experiments/q7_vanish.json`、`q7_nan.json`、`q7_pause.json` を順に流す。q7_pause は本人がゲームを Esc で一時停止する。
3. **ゲームが終了時に落ちる件：** `docs/notes/experiment-runs.md` の最後。実験のあと `python relay/relay.py --seconds 0` を動かしたまま
   ワールドを抜けて、落ちるかを見る。落ちなければ、アドオンとマイコンが返事のない間に要求を溜めないよう直す。
4. Q6 の記録から、物理センサーの出力の順番を読み取る（Q1 の読み取りは `docs/evidence/E-006-physics-sensor-channels.md`）。
5. 確かめたら、`docs/verification.md` の判定と `docs/evidence/` の証拠を書き、決定の `[trial]` を片付ける。

## ファイルの置き場所（本人の PC）

README.md の「ファイルの置き場所」の表のとおり。いま使っているのは：

- アドオン：`%APPDATA%\Stormworks\data\missions\ClaudeBridge\`（`game/addon/ClaudeBridge/` の2ファイル）
- 試験用の機体：ワークベンチで保存した `claude_test`（物理センサー → マイコン、出力1にモーター）。保存先は `%APPDATA%\Stormworks\data\vehicles\`
- アドオンの script.lua を変えたら、新しいワールドを作る（古いスクリプトが残るため）

これまでは本人がファイルを画面からコピーして貼っていた。PC のセッションでは、Claude がリポジトリからこれらの場所へコピーしてよいか、本人に確かめてからコピーする。

## 気をつけること

- クラッシュの記録（`%APPDATA%\Stormworks\crashes\`）には Steam ID や Windows のユーザー名が入っている。リポジトリに入れない。
- 実測と推論を分けて書く。推論を事実のように伝えない（本人から指摘があった）。
- `docs/` のファイルを書き換えたら、mendou のスキルがあれば、その検査（check.py）を通す。
- テスト：`python -m unittest discover -s relay/tests`（Lua のテストは `pip install lupa` を入れたときだけ動く）。
