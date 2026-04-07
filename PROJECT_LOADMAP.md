# PROJECT_LOADMAP.md — 開発管理ノート

## プロジェクト: VoidMemo

---

## 開発タスク一覧

| # | タスク | ステータス | 成果物 |
|---|-------|-----------|--------|
| 1 | フェーズ0: プロジェクト初期セットアップ | ✅ 完了 | `.venv/`, `notes/`, `assets/`, `logic/`, `PROJECT_MAP.md` |
| 2 | フェーズ1: 基本UI (左右2ペイン) の構築 | ✅ 完了 | `main.py` — `App._build_layout()`, `_build_sidebar()`, `_build_editor_pane()` |
| 3 | フェーズ2: ファイル読み書き・一覧表示機能 | ✅ 完了 | `logic/storage.py` — `list_notes()`, `read_note()`, `write_note()`, `rename_note()`, `get_display_title()` |
| 4 | フェーズ3: 自動保存・Debounce ロジック実装 | ✅ 完了 | `main.py` — `_on_key_release()`, `_auto_save()`, `_force_save()`, `_update_title_from_content()` |
| 5 | フェーズ4: pywinstyles Windows 11 風外観適用 | ✅ 完了 | `main.py` — `_apply_win11_style()` (Mica → Acrylic フォールバック) |
| 6 | 機能拡張: ゴミ箱（右クリックメニュー） | ✅ 完了 | `storage.py` + `main.py` — `trash_note()`, `_show_context_menu()`, `_delete_note()` |
| 7 | 機能拡張: .gitignore 整備 | ✅ 完了 | `.gitignore` — log/egg-info/note_order.json等を追加 |
| 8 | 機能拡張: DnD ファイル並び替え | ✅ 完了 | `storage.py` + `main.py` — `load_order()`, `save_order()`, `_drag_start/motion/end()` |
| 9 | 機能拡張: Markdown プレビュー | ✅ 完了 | `main.py` — `_on_tab_change()`, `_render_preview()`, HtmlFrame (tkinterweb) |
| 10 | 機能拡張: 印刷機能・フォルダ表示 | ✅ 完了 | `main.py` 実装済 |
| 11 | 機能拡張: UIの階層構造化 (ツリー化) | ✅ 完了 | `main.py`, `logic/storage.py` 実装済 |

---

## 今後の拡張候補

| # | 拡張機能 | 優先度 | メモ |
|---|---------|--------|------|
| 1 | ダークモード対応の Markdown プレビュー CSS | 中 | システムテーマに連動したCSSを動的切り替え |
| 2 | 検索機能 | 低 | サイドバー上部に検索バーを追加 |
| 3 | ファイルの「スター」/「ピン留め」 | 低 | 重要メモを先頭に固定 |
| 4 | エクスポート機能 | 低 | PDF または HTML でのエクスポート |
| 5 | 複数インスタンス競合対応 | 低 | ファイルロック機構の導入 |

---

## 動作確認手順

```powershell
# プロジェクトフォルダへ移動
cd c:\Users\storm\VoidMemo

# 仮想環境を有効化（Windows PowerShell）
.venv\Scripts\Activate.ps1

# アプリを起動
python main.py
```

## 確認すべき動作一覧

| 機能 | 確認内容 |
|------|---------|
| 新規作成 | 「＋ 新規作成」ボタンでタイムスタンプファイルが作成される |
| 自動保存 | キー入力停止1秒後に `notes/` へ保存、ステータスが「✓ 保存済み」 |
| タイトル連動 | 1行目を変更するとタイトルバーとファイル名が自動更新 |
| ゴミ箱 | ファイルボタン右クリック → 「ゴミ箱に移動」でOSゴミ箱へ移動 |
| DnD並び替え | ファイルをドラッグ&ドロップ、再起動後も順序が維持される |
| Markdownプレビュー | 「👁 プレビュー」タブ切り替えでHTML表示、「✏️ 編集」で戻る |
| Mica 効果 | ウィンドウ背景が半透明（Windows 11 Build 22000 以降） |
