"""
storage.py - ファイル読み書き専門モジュール

notes/ フォルダ内の .txt ファイルの一覧取得・読み込み・書き込み・
ファイルリネーム・ゴミ箱移動・並び順の永続化を担当する。
エンコーディングは常に utf-8 を使用。
"""

import json
import re
from pathlib import Path

import send2trash

# メモが保存されるフォルダのパス
NOTES_DIR: Path = Path(__file__).parent.parent / "notes"
# 並び順を保持するJSONファイルのパス
ORDER_FILE: Path = Path(__file__).parent.parent / "assets" / "note_order.json"


def ensure_notes_dir() -> None:
    """notes/ ディレクトリが存在しない場合に作成する"""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# 並び順と階層構造（ツリー）の永続化
# ------------------------------------------------------------------

def load_tree() -> list[dict]:
    """
    assets/note_order.json からツリー構造を読み込む。
    各ノードは {"filename": str, "is_open": bool, "children": list} の形式。
    古いフラットなリスト形式があった場合は自動的に移行する。
    """
    try:
        if ORDER_FILE.exists():
            data = json.loads(ORDER_FILE.read_text(encoding="utf-8"))
            if data and isinstance(data[0], str):
                # 移行処理
                return [{"filename": name, "is_open": False, "children": []} for name in data]
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_tree(tree: list[dict]) -> None:
    """
    ツリー構造を assets/note_order.json へ保存する。
    """
    try:
        ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
        ORDER_FILE.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_file_tree() -> list[dict]:
    """
    notes/ フォルダ内の .txt ファイルをツリー構造として返す。
    JSONに存在しない新規ファイルは先頭にトップレベルノードとして追加される。
    削除されてディスク上に存在しないファイルはツリーから除外される。

    Returns:
        list[dict]: 階層構造を表す辞書のリスト
    """
    ensure_notes_dir()
    all_files = {f.name for f in NOTES_DIR.glob("*.txt")}

    saved_tree = load_tree()
    known_names: set[str] = set()

    def process_nodes(nodes: list[dict]) -> list[dict]:
        valid_nodes = []
        for node in nodes:
            fname = node.get("filename")
            if fname in all_files:
                known_names.add(fname)
                node["children"] = process_nodes(node.get("children", []))
                if "is_open" not in node:
                    node["is_open"] = False
                valid_nodes.append(node)
        return valid_nodes

    valid_tree = process_nodes(saved_tree)

    # JSON に含まれない新規ファイルをトップレベルの先頭に追加
    new_files = [fname for fname in all_files if fname not in known_names]
    for fname in new_files:
        valid_tree.insert(0, {"filename": fname, "is_open": False, "children": []})

    return valid_tree


# ------------------------------------------------------------------
# ファイルのCRUD
# ------------------------------------------------------------------

def read_note(path: Path) -> str:
    """
    指定パスのテキストファイルを utf-8 で読み込んで返す。

    Args:
        path: 読み込むファイルのパス

    Returns:
        str: ファイルの内容。ファイルが存在しない場合は空文字列。
    """
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def write_note(path: Path, content: str) -> None:
    """
    指定パスへ content を utf-8 で書き込む。

    Args:
        path: 書き込むファイルのパス
        content: 書き込む文字列
    """
    ensure_notes_dir()
    path.write_text(content, encoding="utf-8")


def trash_note(path: Path) -> None:
    """
    指定されたファイルを OS のゴミ箱へ送る。
    send2trash ライブラリを使用することで完全削除でなく復元可能な削除を実現する。

    Args:
        path: ゴミ箱に移動するファイルのパス
    """
    send2trash.send2trash(str(path))


# ------------------------------------------------------------------
# ファイル名ユーティリティ
# ------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """
    ファイル名として使用できない文字を除去・置換して安全なファイル名を返す。
    Windows のファイル名禁止文字（\\/:*?"<>|）および制御文字などを削除する。

    Args:
        name: 元の文字列（1行目テキストなど）

    Returns:
        str: 安全なファイル名文字列（拡張子なし）
    """
    # 禁止文字を取り除く
    safe = re.sub(r'[\\/:*?"<>|\r\n\t]', "", name)
    # 先頭・末尾の空白とドットを除去
    safe = safe.strip(" .")
    # 長すぎる場合は先頭 60 文字に制限（拡張子 .txt の分を加味）
    safe = safe[:60]
    return safe if safe else "Untitled"


def rename_note(old_path: Path, new_title: str) -> Path:
    """
    ファイルを new_title を元にしたファイル名へリネームする。
    既に同名ファイルが存在する場合は連番を付与する。

    Args:
        old_path: 現在のファイルパス
        new_title: 新しいタイトル文字列（ファイルの1行目）

    Returns:
        Path: リネーム後の新しいファイルパス
    """
    base_name = sanitize_filename(new_title)
    new_path = NOTES_DIR / f"{base_name}.txt"

    # 同じパスなら何もしない
    if old_path == new_path:
        return old_path

    # 既存ファイルと衝突する場合は連番を付与
    counter = 1
    while new_path.exists():
        new_path = NOTES_DIR / f"{base_name}_{counter}.txt"
        counter += 1

    old_path.rename(new_path)
    return new_path


def get_display_title(path: Path) -> str:
    """
    ファイルの1行目を読み取り、表示用タイトルを返す。
    空の場合はファイル名（拡張子なし）を返す。

    Args:
        path: ファイルパス

    Returns:
        str: 表示用タイトル文字列
    """
    content = read_note(path)
    first_line = content.split("\n")[0].strip()
    return first_line if first_line else path.stem
