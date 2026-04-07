"""
main.py - VoidMemo アプリケーション メインエントリーポイント

CustomTkinter を用いてマスター・ディテール形式の2ペインレイアウトを構成し、
以下の機能を提供する:
  - 1秒 Debounce による自動保存
  - 1行目からタイトル・ファイル名を自動生成
  - 右クリック → ゴミ箱へ移動
  - ドラッグ&ドロップによるファイル並び替え（order.json で永続化）
  - Markdown プレビュー（tkinterweb / フォールバックあり）
  - pywinstyles による Windows 11 風 Mica 効果
"""

import ctypes
import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

# ---- pywinstyles は Windows専用のため、インポート失敗を許容する ----
try:
    import pywinstyles
    PYWINSTYLES_AVAILABLE = True
except ImportError:
    PYWINSTYLES_AVAILABLE = False

# ---- Markdown / tkinterweb はオプション（フォールバックあり） ----
try:
    import markdown as md_lib
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    from tkinterweb import HtmlFrame
    TKINTERWEB_AVAILABLE = True
except ImportError:
    TKINTERWEB_AVAILABLE = False

# logic モジュールの読み込み
sys.path.insert(0, str(Path(__file__).parent))
from logic import storage

# ====================================================================
# 定数定義
# ====================================================================
APP_TITLE         = "VoidMemo"      # ウィンドウタイトル
WINDOW_MIN_WIDTH  = 800                    # ウィンドウ最小幅 (px)
WINDOW_MIN_HEIGHT = 550                    # ウィンドウ最小高 (px)
SIDEBAR_WIDTH     = 230                    # 左サイドバー幅 (px)
DEBOUNCE_MS       = 1000                   # 自動保存の待機時間 (ms)
DEFAULT_PREFIX    = "Untitled"             # 新規ファイルのデフォルト接頭辞
FONT_FAMILY       = "Yu Gothic UI"         # 本文フォント（日本語対応）
FONT_SIZE_TITLE   = 14                     # タイトル表示フォントサイズ
FONT_SIZE_EDITOR  = 15                     # エディタ本文フォントサイズ
FONT_SIZE_LIST    = 13                     # ファイルリストフォントサイズ
FONT_SIZE_BTN     = 14                     # 「新規作成」ボタンフォントサイズ
DRAG_THRESHOLD    = 6                      # ドラッグ検知の最小移動距離 (px)

# Markdown → HTML 変換時にインジェクトするスタイルシート
PREVIEW_CSS = """
<style>
  body {
    font-family: 'Yu Gothic UI', 'Segoe UI', sans-serif;
    font-size: 15px;
    line-height: 1.7;
    padding: 24px 32px;
    color: #1a1a1a;
    background: #ffffff;
    max-width: 860px;
  }
  h1, h2, h3, h4, h5, h6 {
    font-weight: bold;
    margin-top: 1.4em;
    margin-bottom: 0.4em;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 4px;
  }
  h1 { font-size: 2em; }
  h2 { font-size: 1.5em; }
  h3 { font-size: 1.25em; }
  code {
    background: #f4f4f4;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Consolas', monospace;
    font-size: 0.9em;
  }
  pre code {
    display: block;
    padding: 12px;
    overflow-x: auto;
  }
  blockquote {
    border-left: 4px solid #d0d0d0;
    padding-left: 16px;
    color: #666;
    margin-left: 0;
  }
  a { color: #0066cc; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 8px 12px; }
  th { background: #f0f0f0; }
  ul, ol { padding-left: 1.5em; }
  img { max-width: 100%; }
</style>
"""


class App(ctk.CTk):
    """
    VoidMemo のメインアプリケーションクラス。
    左ペイン（ファイル一覧）と右ペイン（エディタ / Markdownプレビュー）で構成され、
    1秒の Debounce により自動保存を行う。
    """

    def __init__(self):
        """アプリケーションの初期化・UIの構築を行う"""
        super().__init__()

        # ---- ウィンドウ基本設定 ----
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_MIN_WIDTH + 200}x{WINDOW_MIN_HEIGHT + 150}")
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # ---- 状態管理変数 ----
        self._current_path: Path | None = None      # 現在編集中のファイルパス
        self._save_timer: str | None = None          # Debounce タイマーID
        self._is_loading: bool = False               # 読み込み中フラグ（誤保存防止）
        self._last_first_line: str = ""              # 直前の1行目（リネーム判定用）
        self._current_tab: str = "edit"              # 現在のタブ ("edit" | "preview")

        # 現在のツリー構造
        self._current_tree: list[dict] = []
        self._current_row: int = 0

        # ---- UI の構築 ----
        self._build_layout()

        # ---- ウィンドウ表示後に pywinstyles を適用 ----
        self.after(50, self._apply_win11_style)

        # ---- 起動時にファイル一覧を読み込む ----
        self.after(100, self._refresh_file_list)

    # =============================================================
    # レイアウト構築
    # =============================================================

    def _build_layout(self) -> None:
        """左右ペインのレイアウトを構築する"""
        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_editor_pane()

    def _build_sidebar(self) -> None:
        """左サイドバー（新規作成ボタン＋ファイル一覧）を構築する"""
        self.sidebar = ctk.CTkFrame(
            self, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=("gray90", "gray15")
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(1, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        # 「新規作成」ボタン
        self.btn_new = ctk.CTkButton(
            self.sidebar,
            text="＋  新規作成",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_BTN, weight="bold"),
            height=44,
            corner_radius=10,
            command=self._create_new_note,
        )
        self.btn_new.grid(row=0, column=0, padx=12, pady=(14, 8), sticky="ew")

        # ファイル一覧を格納するスクロール可能なフレーム
        self.file_list_frame = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            label_text="",
        )
        self.file_list_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.file_list_frame.grid_columnconfigure(0, weight=1)

    def _build_editor_pane(self) -> None:
        """右エディタペイン（タイトルバー＋タブ＋テキストエリア / プレビュー）を構築する"""
        self.editor_pane = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.editor_pane.grid(row=0, column=1, sticky="nsew")
        self.editor_pane.grid_rowconfigure(2, weight=1)
        self.editor_pane.grid_columnconfigure(0, weight=1)

        # ---- タイトルバー ----
        title_bar = ctk.CTkFrame(
            self.editor_pane, height=50, corner_radius=0, fg_color=("gray85", "gray20")
        )
        title_bar.grid(row=0, column=0, sticky="ew")
        title_bar.grid_propagate(False)
        title_bar.grid_columnconfigure(0, weight=1)
        title_bar.grid_rowconfigure(0, weight=1)

        self.lbl_save_status = ctk.CTkLabel(
            title_bar,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=("gray50", "gray60"),
            width=80,
            anchor="e",
        )
        self.lbl_save_status.grid(row=0, column=1, padx=(10, 10), pady=0, sticky="e")

        self.btn_folder = ctk.CTkButton(
            title_bar,
            text="📁",
            width=30,
            height=30,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=("gray20", "gray80"),
            hover_color=("gray75", "gray30"),
            command=self._open_folder,
        )
        self.btn_folder.grid(row=0, column=2, padx=(0, 4), pady=0, sticky="e")

        self.btn_print = ctk.CTkButton(
            title_bar,
            text="🖨️",
            width=30,
            height=30,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=("gray20", "gray80"),
            hover_color=("gray75", "gray30"),
            command=self._print_note,
        )
        self.btn_print.grid(row=0, column=3, padx=(0, 16), pady=0, sticky="e")

        self.lbl_title = ctk.CTkLabel(
            title_bar,
            text="ファイルを選ぶか新規作成してください",
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_TITLE, weight="bold"),
            anchor="w",
        )
        self.lbl_title.grid(row=0, column=0, padx=20, pady=0, sticky="ew")

        # ---- タブバー（編集 / プレビュー） ----
        tab_bar = ctk.CTkFrame(
            self.editor_pane, height=38, corner_radius=0, fg_color=("gray88", "gray22")
        )
        tab_bar.grid(row=1, column=0, sticky="ew")
        tab_bar.grid_propagate(False)
        tab_bar.grid_rowconfigure(0, weight=1)

        self.tab_switcher = ctk.CTkSegmentedButton(
            tab_bar,
            values=["✏️  編集", "👁  プレビュー"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            height=28,
            command=self._on_tab_change,
        )
        self.tab_switcher.set("✏️  編集")
        self.tab_switcher.grid(row=0, column=0, padx=12, pady=5, sticky="w")

        # ---- テキストエリア ----
        self.text_editor = ctk.CTkTextbox(
            self.editor_pane,
            font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_EDITOR),
            wrap="word",
            corner_radius=0,
            border_width=0,
            fg_color=("white", "gray17"),
        )
        self.text_editor.grid(row=2, column=0, sticky="nsew")
        self.text_editor.bind("<KeyRelease>", self._on_key_release)

        # ---- Markdown プレビューフレーム ----
        if TKINTERWEB_AVAILABLE:
            self.html_frame = HtmlFrame(self.editor_pane, messages_enabled=False)
            self.html_frame.grid(row=2, column=0, sticky="nsew")
            self.html_frame.grid_remove()   # 初期状態では非表示
        else:
            # フォールバック: tkinterweb がない場合は読み取り専用テキストボックスで代用
            self.html_frame = ctk.CTkTextbox(
                self.editor_pane,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_EDITOR),
                wrap="word",
                corner_radius=0,
                border_width=0,
                state="disabled",
                fg_color=("gray95", "gray19"),
            )
            self.html_frame.grid(row=2, column=0, sticky="nsew")
            self.html_frame.grid_remove()

    # =============================================================
    # タブ切り替え（編集 / プレビュー）
    # =============================================================

    def _on_tab_change(self, value: str) -> None:
        """
        編集タブとプレビュータブの切り替え処理。
        プレビュー選択時は Markdown を HTML に変換して表示する。

        Args:
            value: 選択されたタブのラベル文字列
        """
        if "プレビュー" in value:
            self._current_tab = "preview"
            content = self.text_editor.get("1.0", "end-1c")
            self._render_preview(content)
            self.text_editor.grid_remove()
            self.html_frame.grid()
        else:
            self._current_tab = "edit"
            self.html_frame.grid_remove()
            self.text_editor.grid()

    def _render_preview(self, content: str) -> None:
        """
        Markdown テキストを HTML に変換してプレビューペインに表示する。

        Args:
            content: エディタの現在のテキスト（Markdown 形式）
        """
        if MARKDOWN_AVAILABLE and TKINTERWEB_AVAILABLE:
            html_body = md_lib.markdown(
                content,
                extensions=["tables", "fenced_code", "nl2br", "toc"],
            )
            full_html = f"<html><head>{PREVIEW_CSS}</head><body>{html_body}</body></html>"
            self.html_frame.load_html(full_html)
        elif not TKINTERWEB_AVAILABLE:
            # フォールバック: プレーンテキストをそのまま表示
            self.html_frame.configure(state="normal")
            self.html_frame.delete("1.0", "end")
            self.html_frame.insert("1.0", content)
            self.html_frame.configure(state="disabled")

    # =============================================================
    # ファイル一覧の更新
    # =============================================================

    def _refresh_file_list(self, select_path: Path | None = None) -> None:
        """
        左ペインのファイルツリーを最新の状態に再描画する。

        Args:
            select_path: 再描画後に選択状態にするファイルパス（省略可）
        """
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()

        self._current_tree = storage.get_file_tree()

        if not self._current_tree:
            placeholder = ctk.CTkLabel(
                self.file_list_frame,
                text="メモがありません",
                text_color=("gray50", "gray55"),
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LIST),
            )
            placeholder.grid(row=0, column=0, pady=20)
            return

        effective_select = select_path or self._current_path
        self._current_row = 0
        self._render_tree_nodes(self._current_tree, 0, effective_select)

    def _render_tree_nodes(self, nodes: list[dict], depth: int, active_path: Path | None) -> None:
        """再帰的にツリーノードを描画する"""
        for node in nodes:
            filename = node.get("filename")
            path = storage.NOTES_DIR / filename
            if not path.exists():
                continue

            title = storage.get_display_title(path)
            is_selected = (path == active_path)
            children = node.get("children", [])
            is_open = node.get("is_open", False)

            frm = ctk.CTkFrame(self.file_list_frame, fg_color="transparent")
            frm.grid(row=self._current_row, column=0, sticky="ew", padx=(depth * 15, 0), pady=1)
            frm.grid_columnconfigure(1, weight=1)

            # トグルボタン
            toggle_text = "▼" if is_open else "▶"
            if children:
                btn_toggle = ctk.CTkButton(
                    frm, text=toggle_text, width=20, height=30, fg_color="transparent",
                    text_color=("gray30", "gray70"), hover_color=("gray85", "gray25"),
                    command=lambda n=node: self._toggle_node(n)
                )
                btn_toggle.grid(row=0, column=0, padx=(0, 2))
            else:
                dummy = ctk.CTkLabel(frm, text="・", width=20, text_color=("gray60", "gray40"))
                dummy.grid(row=0, column=0, padx=(0, 2))

            # ファイルボタン
            btn = ctk.CTkButton(
                frm,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LIST),
                anchor="w",
                height=32,
                corner_radius=6,
                fg_color=("gray75", "gray30") if is_selected else "transparent",
                hover_color=("gray80", "gray25"),
                text_color=("gray10", "gray95"),
                command=lambda p=path: self._switch_note(p),
            )
            btn.grid(row=0, column=1, sticky="ew")

            # イベントバインド
            btn.bind("<Button-3>", lambda e, p=path, n=node: self._show_context_menu(p, n, e))
            
            self._current_row += 1

            if is_open and children:
                self._render_tree_nodes(children, depth + 1, active_path)

    def _toggle_node(self, node: dict) -> None:
        """フォルダの展開/折りたたみを切り替える"""
        node["is_open"] = not node.get("is_open", False)
        storage.save_tree(self._current_tree)
        self._refresh_file_list(select_path=self._current_path)

    # =============================================================
    # コンテキストメニュー（階層操作・ゴミ箱）
    # =============================================================

    def _show_context_menu(self, path: Path, node: dict, event: tk.Event) -> None:
        """
        右クリックメニューを表示する
        """
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            font=(FONT_FAMILY, 12), bg="#f5f5f5", fg="#1a1a1a",
            activebackground="#e0e0e0", activeforeground="#000000", relief="flat", bd=0,
        )
        menu.add_command(
            label="📝 この配下に新規作成",
            command=lambda: self._create_new_child_note(node),
        )
        menu.add_command(
            label="⬆ トップ階層へ移動",
            command=lambda: self._move_to_top_level(node),
        )
        menu.add_separator()
        menu.add_command(
            label="🗑️  ゴミ箱に移動",
            command=lambda: self._delete_note(path),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _create_new_child_note(self, parent_node: dict) -> None:
        self._force_save()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{DEFAULT_PREFIX}_{timestamp}.txt"
        new_path = storage.NOTES_DIR / filename
        storage.write_note(new_path, "")

        if "children" not in parent_node:
            parent_node["children"] = []
        parent_node["children"].insert(0, {"filename": filename, "is_open": False, "children": []})
        parent_node["is_open"] = True
        
        storage.save_tree(self._current_tree)
        self._refresh_file_list(select_path=new_path)
        self._load_note(new_path)

    def _move_to_top_level(self, node: dict) -> None:
        filename = node.get("filename")
        if self._remove_from_tree(self._current_tree, filename):
            self._current_tree.append(node)
            storage.save_tree(self._current_tree)
            self._refresh_file_list(select_path=self._current_path)

    def _delete_note(self, path: Path) -> None:
        is_current = (path == self._current_path)

        if is_current:
            if self._save_timer is not None:
                self.after_cancel(self._save_timer)
                self._save_timer = None
            self._current_path = None
            self.text_editor.delete("1.0", "end")
            self.lbl_title.configure(text="ファイルを選ぶか新規作成してください")
            self.lbl_save_status.configure(text="")

        try:
            storage.trash_note(path)
        except Exception as e:
            self._show_error(f"削除に失敗しました:\n{e}")
            return

        self._remove_from_tree(self._current_tree, path.name)
        storage.save_tree(self._current_tree)
        self._refresh_file_list(select_path=self._current_path)

    # =============================================================
    # ツリー操作用ユーティリティ
    # =============================================================

    def _remove_from_tree(self, tree: list[dict], target_name: str) -> bool:
        """ツリーから指定したファイルを再帰的に削除する"""
        for i, node in enumerate(tree):
            if node["filename"] == target_name:
                tree.pop(i)
                return True
            if self._remove_from_tree(node.get("children", []), target_name):
                return True
        return False

    def _replace_name_in_tree(self, tree: list[dict], old_name: str, new_name: str) -> bool:
        """ツリー内のファイル名を再帰的に検索して置換する"""
        for node in tree:
            if node["filename"] == old_name:
                node["filename"] = new_name
                return True
            if self._replace_name_in_tree(node.get("children", []), old_name, new_name):
                return True
        return False

    # =============================================================
    # 印刷・フォルダを開く機能
    # =============================================================

    def _open_folder(self) -> None:
        """現在のファイルがあるフォルダをエクスプローラーで選択状態で開く"""
        if self._current_path and self._current_path.exists():
            subprocess.Popen(f'explorer /select,"{self._current_path}"')

    def _print_note(self) -> None:
        """現在のファイルをプレーンテキストとして印刷する"""
        if self._current_path and self._current_path.exists():
            try:
                os.startfile(self._current_path, "print")
            except Exception as e:
                self._show_error(f"印刷の起動に失敗しました:\n{e}")

    # =============================================================
    # ファイル操作
    # =============================================================

    def _create_new_note(self) -> None:
        """
        新規メモファイルをタイムスタンプ付きファイル名で作成し、
        エディタに切り替える。トップ階層に追加される。
        """
        self._force_save()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{DEFAULT_PREFIX}_{timestamp}.txt"
        new_path = storage.NOTES_DIR / filename
        storage.write_note(new_path, "")

        self._current_tree.insert(0, {"filename": filename, "is_open": False, "children": []})
        storage.save_tree(self._current_tree)

        self._refresh_file_list(select_path=new_path)
        self._load_note(new_path)

    def _switch_note(self, path: Path) -> None:
        """
        ファイル一覧のボタンクリック時に現在のファイルを強制保存し、
        選択されたファイルへ切り替える。

        Args:
            path: 切り替え先のファイルパス
        """
        if path == self._current_path:
            return
        self._force_save()
        self._refresh_file_list(select_path=path)
        self._load_note(path)

    def _load_note(self, path: Path) -> None:
        """
        指定パスのファイルをエディタに読み込む。
        編集タブへ自動切り替えも行う。

        Args:
            path: 読み込むファイルのパス
        """
        # プレビュータブなら編集タブへ戻す
        if self._current_tab == "preview":
            self.tab_switcher.set("✏️  編集")
            self._on_tab_change("✏️  編集")

        self._is_loading = True
        self._current_path = path
        self._last_first_line = ""

        content = storage.read_note(path)

        self.text_editor.delete("1.0", "end")
        self.text_editor.insert("1.0", content)

        self._update_title_from_content(content)
        self.lbl_save_status.configure(text="")
        self._is_loading = False

    # =============================================================
    # 自動保存 (Debounce)
    # =============================================================

    def _on_key_release(self, event=None) -> None:
        """
        キー離し時に呼ばれるイベントハンドラ。
        既存タイマーをキャンセルして 1秒後に保存をスケジュールする（Debounce）。
        """
        if self._is_loading or self._current_path is None:
            return

        content = self.text_editor.get("1.0", "end-1c")
        self._update_title_from_content(content)

        if self._save_timer is not None:
            self.after_cancel(self._save_timer)
            self._save_timer = None

        self._save_timer = self.after(DEBOUNCE_MS, self._auto_save)
        self.lbl_save_status.configure(text="編集中…")

    def _auto_save(self) -> None:
        """
        Debounce タイマーが満了したときに呼ばれる自動保存処理。
        必要に応じてファイルのリネームも行う。
        """
        self._save_timer = None
        if self._current_path is None:
            return

        content = self.text_editor.get("1.0", "end-1c")

        # ---- ファイルのリネーム処理 ----
        first_line = content.split("\n")[0].strip()
        if first_line and first_line != self._last_first_line:
            new_path = storage.rename_note(self._current_path, first_line)
            if new_path != self._current_path:
                self._replace_name_in_tree(self._current_tree, self._current_path.name, new_path.name)
                storage.save_tree(self._current_tree)
                self._current_path = new_path
                self._refresh_file_list(select_path=new_path)
            self._last_first_line = first_line

        storage.write_note(self._current_path, content)
        self.lbl_save_status.configure(text="✓ 保存済み")

    def _force_save(self) -> None:
        """
        タイマー待機中でもすぐにファイルを保存する（ファイル切り替え時などに使用）。
        """
        if self._save_timer is not None:
            self.after_cancel(self._save_timer)
            self._save_timer = None

        if self._current_path is None:
            return

        content = self.text_editor.get("1.0", "end-1c")

        first_line = content.split("\n")[0].strip()
        if first_line and first_line != self._last_first_line:
            new_path = storage.rename_note(self._current_path, first_line)
            if new_path != self._current_path:
                self._replace_name_in_tree(self._current_tree, self._current_path.name, new_path.name)
                storage.save_tree(self._current_tree)
                self._current_path = new_path
            self._last_first_line = first_line

        storage.write_note(self._current_path, content)
        self.lbl_save_status.configure(text="✓ 保存済み")

    # =============================================================
    # タイトルバー更新
    # =============================================================

    def _update_title_from_content(self, content: str) -> None:
        """
        テキスト内容の1行目を読み取り、タイトルバーラベルを更新する。

        Args:
            content: エディタの現在のテキスト全体
        """
        first_line = content.split("\n")[0].strip()
        if first_line:
            self.lbl_title.configure(text=first_line)
        elif self._current_path is not None:
            self.lbl_title.configure(text=self._current_path.stem)
        else:
            self.lbl_title.configure(text="新規メモ")

    # =============================================================
    # Windows 11 風デザイン適用
    # =============================================================

    def _apply_win11_style(self) -> None:
        """
        pywinstyles を使用してウィンドウに Mica 効果を適用する。
        pywinstyles が使用できない環境ではスキップする。
        """
        if not PYWINSTYLES_AVAILABLE:
            return
        try:
            pywinstyles.apply_style(self, "mica")
        except Exception:
            try:
                pywinstyles.apply_style(self, "acrylic")
            except Exception:
                pass


# ====================================================================
# エントリーポイント
# ====================================================================
if __name__ == "__main__":
    # Windows で高DPI対応（ぼやけ防止）
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    app = App()
    app.mainloop()
