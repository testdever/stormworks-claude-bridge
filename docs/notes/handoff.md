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

## 次にやること（2026-11-09 20:10 時点）

済み：Q6・Q7・Q9 合格。D-003 の [trial] を片付けた。回転に関わる物理センサーの出力（E-019）。送り直しの間隔を伸ばす Lua で、
中継プログラムを止めたままゲームを終了しても落ちなかった（1回）。残った機体・標的の片付け、`?claude stop`。
本人の FCS（射撃管制マイコン、test calc）の試験の自動化：2 km の V-07 を手で撃つ形で回した（E-020、合格）。

1. **FCS V-07 を手放しで：** README の「FCS V-07（手放し）」。本人が test calc のつなぎのマイコンに `game/fcs_bridge.lua` を貼り、
   射撃許可の線（Composite Read on/off ch1 → allow fire）をつなぎ、新しいワールドを作る。`experiments/fcs_v07_auto.json` を流す。
   その間に本人がほかの作業をすれば、Q10（重く感じないか）も確かめられる。合格なら D-004 の [trial] を片付ける。
2. 前の会話の残りの FCS の試験（V-08 動く目標、V-09 揺れる船、V-10 初弾までの時間、V-15 FPS、V-16〜V-18）を手順書にする。
   標的を動かすのに setVehiclePos は使えない（動かすたびに読み込み直す）。動く標的には自分で進む機体が要る。
3. 落ちる件は、新しい Lua でもう何回か様子を見る。

FCS の一式（Lua・設計書・試走の Lua）は、本人の PC の `Downloads\stormworks-fcs-2026-11-09.zip`（リポジトリには入れていない）。
test calc の FCS は目標を ch1 = X、ch2 = Z、ch3 = Y で読む（ヘビレンジのアドオンに合わせたもの。普段は X・Y・Z）。

本人の PC での動かし方：デスクトップの `relay\relay.py` は古いので使わない。リポジトリ（`Desktop\relay\stormworks-claude-bridge`）の
`relay/relay.py` と `experiments/` を、デスクトップの `relay` フォルダから動かす（記録は `relay\logs\` に残る）。
手順書は、ワールドの座標を決め打ちにせず、本人の立っている場所から 6m 先に置く（ワールドごとに最初の島の場所が違う）。
Lua のテストは、スマート アプリ コントロールに止められない Lua 5.1 を使う（`relay/tests/luart.py`）。

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
