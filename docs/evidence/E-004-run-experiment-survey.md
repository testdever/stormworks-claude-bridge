+++
id = "E-004"
grade = "third_party"
date = "2026-11-08"
source = "https://dev.to/arihantdeva/token-economics-of-long-running-agent-loops-d9h , https://dev.to/tim_zhang11/i-measured-mcp-vs-cli-for-agent-tool-use-mcp-used-17x-more-tokens-per-call-3egc , https://arxiv.org/pdf/2609.11999 , https://glama.ai/mcp/servers/ziksjksk/kerbal-space-program-mcp/related-servers , https://dev.to/rishblob/minecraft-mcp-server-for-testing-model-spatial-reasoning-capabilities-5e61 , https://glama.ai/mcp/servers/ekb-dev-ai/mcp-drone-agent"
quote = ""
questions = []
claims = [
  "ゲームやシミュレーターを LLM に操作させる例は、MCP（Claude などに道具を足す標準の仕組み）の道具として状態の読み取りと操作を渡す形が多い（Flight Simulator、Minecraft、ドローン）",
  "1手ずつ道具を呼ぶやり方は、呼ぶたびに会話全体を読み直すので、呼ぶ回数に比例して読み込む量が増える",
  "手順をまとめてプログラムとして実行させるやり方は、1手ずつ呼ぶより読み込む量が少ないという報告がある",
]
+++

調べた先：Web 検索（「MCP server game simulator control LLM agent」「LLM agent run simulation experiments batch script vs interactive tool calls token cost」）。MCP の道具でゲームを動かす例（Flight Simulator 2024、Minecraft、ドローンのシミュレーター、KSP）、エージェントの読み込み量を比べた記事と論文（Is Bash All You Need?）。

解き方：
- 定番は、MCP の道具として「状態を読む」「操作する」を渡し、LLM が1手ずつ呼んで進める形。
- 読み込む量を減らす方法としてよく挙がるのは、手順をまとめてプログラムとして実行させ、結果だけを受け取る形。長く回す実験ではこちらが良いとされる。
- Stormworks で同じことをしている例は見つからなかった。
