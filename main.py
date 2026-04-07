"""
main.py - Auto-Save Memo アプリケーション メインエントリーポイント

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
APP_TITLE         = "Auto-Save Memo"      # ウィンドウタイトル
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
    Auto-Save Memo のメインアプリケーションクラス。
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

        # ---- ドラッグ&ドロップ 状態管理 ----
        self._drag_data: dict = {
            "widget": None,       # ドラッグ中のボタンウィジェット
            "path": None,         # ドラッグ中のファイルパス
            "index": -1,          # ドラッグ元のインデックス
            "ghost": None,        # ゴーストウィジェット (Toplevel)
            "dragging": False,    # ドラッグ中かどうか
            "start_x": 0,
            "start_y": 0,
        }
        # 現在のファイルリスト順序（ドラッグ後の並び順計算用）
        self._current_order: list[Path] = []

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
        self.lbl_save_status.grid(row=0, column=1, padx=(0, 16), pady=0, sticky="e")

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
        左ペインのファイル一覧を最新の状態に再描画する。

        Args:
            select_path: 再描画後に選択状態にするファイルパス（省略可）
        """
        # 既存ウィジェットを全削除
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()

        notes = storage.list_notes()
        self._current_order = list(notes)  # ドラッグ用に現在の順序を保持

        if not notes:
            placeholder = ctk.CTkLabel(
                self.file_list_frame,
                text="メモがありません",
                text_color=("gray50", "gray55"),
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LIST),
            )
            placeholder.grid(row=0, column=0, pady=20)
            return

        effective_select = select_path or self._current_path

        for idx, note_path in enumerate(notes):
            title = storage.get_display_title(note_path)
            is_selected = (note_path == effective_select)

            btn = ctk.CTkButton(
                self.file_list_frame,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=FONT_SIZE_LIST),
                anchor="w",
                height=38,
                corner_radius=8,
                fg_color=("gray75", "gray30") if is_selected else "transparent",
                hover_color=("gray80", "gray25"),
                text_color=("gray10", "gray95"),
                command=lambda p=note_path: self._switch_note(p),
            )
            btn.grid(row=idx, column=0, padx=6, pady=2, sticky="ew")

            # ---- 右クリック: ゴミ箱コンテキストメニュー ----
            btn.bind("<Button-3>", lambda e, p=note_path: self._show_context_menu(p, e))

            # ---- ドラッグ&ドロップ イベントバインド ----
            btn.bind("<ButtonPress-1>",   lambda e, i=idx, p=note_path, w=btn: self._drag_start(e, i, p, w))
            btn.bind("<B1-Motion>",        self._drag_motion)
            btn.bind("<ButtonRelease-1>",  self._drag_end)

    # =============================================================
    # ゴミ箱（右クリックコンテキストメニュー）
    # =============================================================

    def _show_context_menu(self, path: Path, event: tk.Event) -> None:
        """
        ファイルボタンを右クリックしたときに「ゴミ箱」コンテキストメニューを表示する。

        Args:
            path: 対象ファイルのパス
            event: マウスイベント（表示位置の特定に使用）
        """
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            font=(FONT_FAMILY, 12),
            bg="#f5f5f5",
            fg="#1a1a1a",
            activebackground="#e0e0e0",
            activeforeground="#000000",
            relief="flat",
            bd=0,
        )
        menu.add_command(
            label="🗑️  ゴミ箱に移動",
            command=lambda: self._delete_note(path),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_note(self, path: Path) -> None:
        """
        指定ファイルを OS のゴミ箱へ送り、一覧と並び順を更新する。
        現在編集中のファイルが削除された場合はエディタをクリアする。

        Args:
            path: 削除するファイルのパス
        """
        is_current = (path == self._current_path)

        # 編集中のファイルを削除する場合は保存をスキップしてクリア
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
            # ゴミ箱移動に失敗した場合はダイアログ表示（簡易）
            self._show_error(f"削除に失敗しました:\n{e}")
            return

        # 並び順から削除したファイルを除去して保存
        new_order = [p for p in self._current_order if p != path]
        storage.save_order(new_order)

        self._refresh_file_list()

    def _show_error(self, message: str) -> None:
        """
        エラーメッセージを小さなダイアログで表示する。

        Args:
            message: 表示するエラーメッセージ
        """
        dialog = ctk.CTkToplevel(self)
        dialog.title("エラー")
        dialog.geometry("320x140")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        ctk.CTkLabel(
            dialog,
            text=message,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            wraplength=280,
        ).pack(pady=20)
        ctk.CTkButton(dialog, text="OK", width=80, command=dialog.destroy).pack()

    # =============================================================
    # ドラッグ&ドロップ 並び替え
    # =============================================================

    def _drag_start(self, event: tk.Event, index: int, path: Path, widget) -> None:
        """
        ドラッグ開始時の状態を記録する。
        実際のドラッグ判定は _drag_motion で DRAG_THRESHOLD を超えた時点で行う。

        Args:
            event: マウスイベント
            index: リスト内のインデックス
            path: 対象ファイルパス
            widget: ドラッグされるボタンウィジェット
        """
        self._drag_data.update({
            "widget": widget,
            "path": path,
            "index": index,
            "dragging": False,
            "ghost": None,
            "start_x": event.x_root,
            "start_y": event.y_root,
        })

    def _drag_motion(self, event: tk.Event) -> None:
        """
        マウス移動中の処理。DRAG_THRESHOLD を超えたらドラッグ中と判定し、
        ゴーストウィジェット（半透明ラベル）をマウスに追従させる。

        Args:
            event: マウスイベント
        """
        dd = self._drag_data
        if dd["widget"] is None:
            return

        dx = abs(event.x_root - dd["start_x"])
        dy = abs(event.y_root - dd["start_y"])

        if not dd["dragging"]:
            if dx < DRAG_THRESHOLD and dy < DRAG_THRESHOLD:
                return  # まだドラッグと判定しない
            # ドラッグ開始 → ゴーストウィジェットを作成
            dd["dragging"] = True
            self._create_ghost(dd["widget"])

        if dd["ghost"] is not None:
            # ゴーストをマウス位置に追従
            dd["ghost"].geometry(f"+{event.x_root + 12}+{event.y_root + 4}")

    def _drag_end(self, event: tk.Event) -> None:
        """
        ドラッグ終了時の処理。ドロップ位置を計算して並び順を更新し保存する。

        Args:
            event: マウスイベント
        """
        dd = self._drag_data
        if not dd["dragging"]:
            dd["widget"] = None
            return

        # ゴーストを破棄
        self._destroy_ghost()

        # ドロップ先のインデックスをマウスのY座標から計算
        drop_index = self._calc_drop_index(event.y_root)
        src_index = dd["index"]

        if drop_index != src_index and 0 <= drop_index <= len(self._current_order):
            # 並び替えを実行
            new_order = list(self._current_order)
            item = new_order.pop(src_index)
            # pop後にインデックスがずれるため調整
            insert_at = drop_index if drop_index <= src_index else drop_index - 1
            insert_at = max(0, min(insert_at, len(new_order)))
            new_order.insert(insert_at, item)
            storage.save_order(new_order)
            self._current_order = new_order
            self._refresh_file_list(select_path=self._current_path)

        # 状態リセット
        dd.update({"widget": None, "path": None, "index": -1,
                    "dragging": False, "ghost": None})

    def _create_ghost(self, source_btn) -> None:
        """
        ドラッグ中に表示するゴーストウィジェット（Toplevel）を作成する。

        Args:
            source_btn: ドラッグ元のボタンウィジェット
        """
        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)    # タイトルバーなし
        ghost.attributes("-alpha", 0.7) # 半透明
        ghost.attributes("-topmost", True)

        label = tk.Label(
            ghost,
            text=source_btn.cget("text"),
            font=(FONT_FAMILY, FONT_SIZE_LIST),
            bg="#5f9ea0",
            fg="white",
            padx=10,
            pady=6,
            relief="flat",
        )
        label.pack()
        self._drag_data["ghost"] = ghost

    def _destroy_ghost(self) -> None:
        """ゴーストウィジェットを安全に破棄する"""
        ghost = self._drag_data.get("ghost")
        if ghost is not None:
            try:
                ghost.destroy()
            except Exception:
                pass
            self._drag_data["ghost"] = None

    def _calc_drop_index(self, y_root: int) -> int:
        """
        マウスのY座標（スクリーン座標）からファイルリスト内のドロップ先インデックスを計算する。

        Args:
            y_root: マウスのスクリーンY座標

        Returns:
            int: 挿入先インデックス（0 ～ len(current_order)）
        """
        buttons = [
            w for w in self.file_list_frame.winfo_children()
            if isinstance(w, ctk.CTkButton)
        ]
        if not buttons:
            return 0

        for i, btn in enumerate(buttons):
            try:
                btn_y_top = btn.winfo_rooty()
                btn_y_mid = btn_y_top + btn.winfo_height() // 2
                if y_root < btn_y_mid:
                    return i
            except Exception:
                continue

        return len(buttons)

    # =============================================================
    # ファイル操作
    # =============================================================

    def _create_new_note(self) -> None:
        """
        新規メモファイルをタイムスタンプ付きファイル名で作成し、
        エディタに切り替える。
        """
        self._force_save()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{DEFAULT_PREFIX}_{timestamp}.txt"
        new_path = storage.NOTES_DIR / filename
        storage.write_note(new_path, "")

        # 並び順の先頭に追加して保存
        new_order = [new_path] + self._current_order
        storage.save_order(new_order)

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
                # 並び順内のパスも更新
                self._current_order = [
                    new_path if p == self._current_path else p
                    for p in self._current_order
                ]
                storage.save_order(self._current_order)
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
                self._current_order = [
                    new_path if p == self._current_path else p
                    for p in self._current_order
                ]
                storage.save_order(self._current_order)
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
