# VoidMemo

![Windows 11 Compatible](https://img.shields.io/badge/OS-Windows%2011-blue)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue)

Windows 11 のデザインガイドラインに準拠した、自動保存型のシンプルメモアプリケーションです。
書き間違えや保存忘れを防ぐため、キー入力が 1 秒間止まるたびに自動でメモをローカルファイル (`notes/` リポジトリ) へ書き保存します。
UI は最新の CustomTkinter を使用し、ライト / ダークのシステムテーマ自動切り替えや、Windows ネイティブの Mica (半透明) 効果に対応しています。

## 🌟 主な機能

- **完全自動保存 (Debounce方式)**: 保存ボタンは存在しません。文字を打ち終えてから 1 秒後に自動で保存されます。
- **1行目 = タイトル完全連動**: メモの 1 行目が自動的に「表示タイトル」および「ファイル名」に適用されます。リネーム作業は不要です。
- **階層構造（ツリー）ビュー**: メモを親ファイル・子ファイルとしてツリー状に階層管理。フォルダ感覚でファイルをスッキリ整理できます。メニューからの展開・折りたたみもサポート。
- **Markdown プレビュー**: `👁 プレビュー` タブに切り替えることで、入力したテキストを Markdown と解釈し綺麗な HTML で表示します。
- **安心のゴミ箱機能**: 削除したテキストは完全に消去されるのではなく、一時的に Windows エクスプローラーの「ゴミ箱」に移動するだけなので安心です。
- **印刷 & フォルダ表示**: 1 クリックで現在のテキストを印刷(`🖨️`)にかけたり、ファイルが保存されているフォルダ(`📁`)を開くことができます。
- **Windows 11 Mica 対応**: `pywinstyles` によるネイティブの Mica 半透明マテリアル表現に対応しています (非対応環境では自動でスキップされます)。

## 🚀 インストール & 起動方法

事前に Python 3.11 以上がインストールされていることを確認してください。

1. **リポジトリの準備・クローン**

   ```powershell
   git clone https://github.com/badass-iwate/VoidMemo.git
   cd VoidMemo
   ```

2. **仮想環境の作成とアクティベート**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **依存パッケージのインストール**

   ```powershell
   pip install customtkinter pywinstyles send2trash markdown tkinterweb
   ```

4. **アプリの起動**

   ```powershell
   python main.py
   ```

## 📂 プロジェクト構成

```text
VoidMemo/
├── main.py                    # アプリケーションのメインエントリーポイント (GUI構築・イベント制御)
├── logic/
│   └── storage.py             # ファイル読み書き・ツリー構造管理 モジュール
├── notes/                     # メモファイル (.txt) が実際に保存されるディレクトリ
├── assets/
│   └── note_order.json        # ファイル構造（親子関係・順序など）を管理するJSON
└── PROJECT_MAP.md             # アプリの設計および詳細な内部動作ドキュメント
```

*※ `notes/` や `assets/note_order.json`、仮想環境フォルダ(`.venv/`) は `.gitignore` によってバージョン管理から除外されています。*

## 💡 主要な使い方

- **新規作成**: 左上の 「＋ 新規作成」ボタンを押すか、既存のメモを右クリックして 「📝 この配下に新規作成」 を選択します。
- **削除**: リストからファイル名を右クリックし、「🗑️ ゴミ箱に移動」を選択します。OS の標準ゴミ箱に送られます。
- **印刷**: エディタ画面の右上ツールバーの「🖨️」アイコンを押すと対象ファイルを印刷できます。

## 📝 開発情報とライセンス

- MITライセンス
