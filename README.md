# skill-promo-video

Agent Skill（GitHubのURL、SKILL.md、スキルのフォルダやZIP）の中身を読んで、SNS向けの縦型30秒の紹介動画（MP4）を作るためのAgent Skillです。

## 主な機能

- スキルの中身から「困りごと → 3つのステップ → もう1つの売り → スキル名とURL」の6シーン構成を組み立てる
- 縦型 1080×1920・30fps・約30秒。音なしで、テロップだけで内容が伝わる
- 配色は紹介するスキルに合わせて毎回変える
- 素材がなくても、管理画面・表計算・チャット・ターミナルの画面イメージを描いて見せる
- 設定ファイル（`spec.json`）を書き換えるだけで、どのスキルの動画も作れる

## ファイル構成

- `SKILL.md` — 作業手順・ルール
- `scripts/make_promo.py` — `spec.json` から動画を作るスクリプト
- `references/spec-guide.md` — `spec.json` の書き方

## 導入

Agent Skillsに対応する実行環境のスキルディレクトリに、このリポジトリの内容を `skill-promo-video` フォルダとして配置してください。対応する実行環境で `SKILL.md` を読み込み、記載の手順に従います。

必要なもの：

- Python 3 と Pillow（`pip install pillow`）
- ffmpeg
- 日本語フォント（Noto Sans CJK JP またはヒラギノ角ゴシックを自動で探します。別の場所にある場合は `spec.json` の `fonts` で指定）

## 使い方（手動で動かす場合）

```bash
# 各シーンの見せ場を並べた一覧画像で確認
python3 scripts/make_promo.py spec.json --out out --sheet

# 動画を書き出す
python3 scripts/make_promo.py spec.json --out out
```

## 注意

- 動画に根拠のない数字や架空の実績・利用者の声は入れません。
- 製品のロゴや商標の図柄は描きません。

## 利用条件

ライセンスは未設定です。再利用・再配布条件が決まるまでは、公開リポジトリでも第三者への利用許諾は付与されません。
