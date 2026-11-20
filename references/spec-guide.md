# spec.json の書き方

## 全体

```json
{
  "name": "スキル名（最後の画面に大きく出る。英数字）",
  "tagline": ["最後の画面のひとこと 1行目", "2行目"],
  "tags": ["成果物の形式など", "2〜3個"],
  "url_label": "GitHub",
  "url": "github.com/owner/repo（なければ項目ごと消す）",
  "output": "出力ファイル名.mp4（省略すると <name>_promo.mp4）",
  "palette": { "bg": "#...", "ink": "#...", "sub": "#...", "accent": "#...", "alert": "#...", "dark": "#...", "surface": "#FFFFFF", "line": "#..." },
  "fonts": { "Regular": "...", "Medium": "...", "Bold": "...", "Black": "..." },
  "scenes": [ ... ]
}
```

- `fonts` は自動で見つからないときだけ書く。
- 色を指定する項目には、パレット名（`"accent"` など）か `"#RRGGBB"` を書ける。

## シーン共通

```json
{
  "type": "hook | step | feature | end",
  "duration": 5.0,
  "title": [["1行目", "ink"], ["2行目", "accent"]],
  "caption": "下の説明文",
  "step": 1, "total": 3,
  "visual": { ... }
}
```

- `step` / `total` は type が step のときだけ。左上に「STEP 1/3」が出る。
- `end` は `type` と `duration` だけでよい（全体の name・tagline・tags・url を使う）。

## hook の visual

```json
"visual": {
  "screen": { 画面（下記） },
  "titles": ["画面ごとのタイトル", "…6個まで"]
}
```
同じ画面を、タイトルだけ変えて散らかった束にする。

## step / feature の visual

`kind` で動きを選ぶ。

### cursor（クリックして進む）
```json
{ "kind": "cursor", "screen": {…}, "targets": [0, 1, 3], "counter": "撮影 {n}枚" }
```
- `targets`：カーソルが順に動く部品の番号（省略時は最初の2つと最後）。
- 部品に着くたびに画面が白く光る。`counter` を書くと右上に回数が出る（`{n}` が数字になる）。

### highlight（赤枠と番号）
```json
{ "kind": "highlight", "screen": {…}, "targets": [0, 3], "numbers": true }
```
- `numbers: false` で番号を出さず枠だけにする。

### fanout（1つから複数できる）
```json
{
  "kind": "fanout",
  "input": { "title": "config.json", "lines": ["1行目", "2行目", "3行目"] },
  "outputs": [
    { "name": "PowerPoint", "icon": "slides", "color": "#C44F2E" },
    { "name": "動画 MP4", "icon": "video", "color": "accent", "sub": "字幕つき" }
  ]
}
```
- `outputs` は2〜3個。`icon`：`slides` `doc` `video` `sheet` `image` `code` `chat`。

### variants（色が切り替わる）
```json
{
  "kind": "variants",
  "card": { "title": "資料の見出し", "lines": ["右側の文字", "2行目"], "note": "下の囲み（省略可）" },
  "palettes": [["#メイン色", "#濃い色"], ["#…", "#…"], ["#…", "#…"]]
}
```

## 画面（screen）

`style` で種類を選ぶ。**部品の番号**は `targets` で使う（0から数える）。

### app（管理画面・業務アプリ）
```json
{ "style": "app", "title": "新規フォーム", "menu": ["ダッシュボード", "投稿", "設定"], "active": "投稿", "fields": ["項目1", "項目2", "項目3"], "button": "保存" }
```
部品：入力欄（fields の順）→ ボタン。fields は3つまでが収まる。

### sheet（表計算）
```json
{ "style": "sheet", "title": "11月の売上", "columns": ["日付", "売上", "件数"], "rows": [["11/1", "12,000", "8"]], "button": "集計する" }
```
部品：データ行（rows の順）→ ボタン。rows は6行くらいまで。

### chat（チャット）
```json
{ "style": "chat", "title": "#チャンネル名", "messages": [{ "from": "user", "text": "…" }, { "from": "ai", "text": "…" }], "placeholder": "メッセージを入力" }
```
部品：吹き出し（messages の順）→ 入力欄。吹き出しは4つくらいまで。

### terminal（コマンド・コード）
```json
{ "style": "terminal", "title": "ファイル名など", "lines": ["$ コマンド", "✓ 完了した行は緑になる"] }
```
部品：各行。lines は8行くらいまで。

共通で `"chrome": "dark"` のように、画面の枠の色を変えられる。

## 長さの目安

- 見出し：1行10文字くらい（収まらないと自動で小さくなる）
- 説明文：20文字くらい
- 合計の duration：30秒前後（型どおりなら 3.6 + 5.4 + 5.0 + 6.5 + 5.0 + 5.0 = 30.5）
