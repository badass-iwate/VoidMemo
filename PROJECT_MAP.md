# PROJECT_MAP.md — Auto-Save Memo

## プロジェクト概要

Windows 11 のデザインガイドラインに準拠した、自動保存型のシンプルメモアプリ。  
保存ボタンを持たず、1秒間の入力停止後に自動的にファイルへ書き込む（Debounce 方式）。  
ファイルの1行目が表示タイトルおよびファイル名として自動反映される。

---

## 技術スタック

| 項目 | 選定ツール / ライブラリ | 備考 |
|------|------------------------|------|
| 言語 | Python 3.11+ | venv 仮想環境で管理 |
| GUI 基盤 | CustomTkinter | Windows 11 風のUIコンポーネント |
| OS 統合 | pywinstyles | Mica / Acrylic 効果（半透明ウィンドウ） |
| データ保存 | ローカルファイル (.txt) | utf-8 エンコーディング固定 |
| ゴミ箱 | send2trash | OSのゴミ箱に送る（完全削除せず復元可能） |
| Markdown変換 | markdown (Python) | Markdown → HTML 変換 |
| HTMLレンダリング | tkinterweb | HtmlFrame でプレビュー表示 |
| 並び順の永続化 | JSON | assets/note_order.json |

---

## ディレクトリ構造

```text
MemoOSS/
├── main.py                    # アプリケーションのメインエントリーポイント
├── logic/
│   ├── __init__.py            # パッケージ初期化
│   └── storage.py             # ファイル読み書き・リネーム・ゴミ箱・並び順 モジュール
├── notes/                     # メモファイル (.txt) が保存されるディレクトリ ※Git管理外
├── assets/
│   └── note_order.json        # ファイルの並び順 (ユーザー個人設定) ※Git管理外
├── .venv/                     # Python 仮想環境 ※Git管理外
├── .gitignore                 # Git 管理対象外ファイルの定義
├── PROJECT_MAP.md             # 本ファイル（プロジェクト概要・構成）
└── PROJECT_LOADMAP.md         # 開発管理ノート（タスク・ステータス）
```

---

## 主要ファイルの役割説明

| ファイル | 役割 |
|---------|------|
| `main.py` | `App` クラス（CTk サブクラス）を定義。UI 構築・イベント制御・Debounce 自動保存・pywinstyles 適用・ゴミ箱・DnD・Markdown プレビューを担う |
| `logic/storage.py` | `notes/` フォルダへの CRUD 操作全般、ゴミ箱 (`trash_note`)、並び順の読み書き (`load_order` / `save_order`)、リネームを担当 |
| `notes/` | ユーザーのメモ (.txt) が実際に保存されるディレクトリ |
| `assets/note_order.json` | サイドバーのファイル並び順を JSON で永続化するファイル |
| `.venv/` | プロジェクト専用の Python 仮想環境 |

---

## 主要機能一覧

| 機能 | 詳細 |
|------|------|
| 自動保存 (Debounce) | キー入力停止 1秒後に自動保存。タイマーは入力のたびにリセット |
| タイトル連動 | ファイルの1行目 = タイトルバー表示 = ファイル名（保存時に自動リネーム） |
| 新規作成 | タイムスタンプ付きファイル名で自動生成（例: `Untitled_20260407_2214.txt`） |
| ゴミ箱 | ファイルボタンを右クリック → 「ゴミ箱に移動」でOSゴミ箱へ（復元可能） |
| DnD 並び替え | サイドバーのファイルをドラッグ&ドロップで並び替え。順序は `note_order.json` で永続化 |
| Markdown プレビュー | タイトルバー下のタブで「編集」と「プレビュー」を切り替え |
| Windows 11 Mica | ウィンドウ背景に Mica/Acrylic 半透明効果（非対応環境ではスキップ） |
| システムテーマ追従 | ライト/ダークモードをOSの設定に自動追従 |

---

## 外部 API・サービスとの連携

| 連携先 | 用途 |
|--------|------|
| Windows API (DPI) | `ctypes.windll.shcore.SetProcessDpiAwareness(2)` による高 DPI 対応 |
| pywinstyles | OS ネイティブの Mica / Acrylic ウィンドウ効果 |
| send2trash | クロスプラットフォーム対応のゴミ箱送り |

---

## 主要ロジック解説

### 自動保存 (Debounce)

1. `<KeyRelease>` イベント発火
2. 既存タイマーを `after_cancel()` でリセット
3. `after(1000, _auto_save)` で 1秒後の保存を予約
4. タイマー満了 → `storage.write_note()` でファイルへ書き込み

### 1行目 → タイトル & ファイル名 連動

- キー入力のたびにタイトルバーを即時更新（`_update_title_from_content`）
- 保存時に1行目が変化していた場合 `storage.rename_note()` を呼び出してリネーム
- 並び順 JSON 内のパスも同時に更新

### DnD 並び替え

1. `<ButtonPress-1>` でドラッグ元のインデックス・パスを記録
2. `<B1-Motion>` で `DRAG_THRESHOLD`(6px) を超えたら `Toplevel` ゴーストを生成・追従
3. `<ButtonRelease-1>` でドロップ先インデックスを計算、新順序を `save_order()` で保存

### Markdown プレビュー

- `CTkSegmentedButton` でタブUIを実装
- プレビュー選択時: `markdown.markdown()` でHTML変換 → `HtmlFrame.load_html()` で描画
- `tkinterweb` 非対応環境では: プレーンテキストを読み取り専用 `CTkTextbox` で表示

---

## TODO（未解決の技術的課題）

- [ ] ダークモード時の Markdown プレビューCSSをダーク系に切り替える
- [ ] ファイル名が衝突した場合のリネーム連番ロジックの UX 改善
- [ ] 複数インスタンス起動時のファイル競合への対応
