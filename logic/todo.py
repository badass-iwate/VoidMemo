"""
todo.py - TODO抽出と更新を専門に行うモジュール

全てのテキストファイル内のマークダウン式 TODO (- [ ] および - [x]) を抽出し、
管理・更新するためのロジックを提供します。
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

# `storage.py` と同様に notes フォルダを参照する
NOTES_DIR: Path = Path(__file__).parent.parent / "notes"

# TODOマッチ用の正規表現
# グループ1: 状態 (" " または "x")
# グループ2: タスク本文
TODO_REGEX = re.compile(r"^(\s*)-\s+\[([ xX])\]\s+(.*)$")

@dataclass
class TodoItem:
    path: Path
    line_index: int       # 0から始まる行番号
    text: str             # TODOの本文
    is_checked: bool      # 完了しているかどうか
    indent: str           # 先頭のインデント文字列

def _parse_todos(content: str, path: Path) -> List[TodoItem]:
    """文字列全体からTODOアイテムを抽出する"""
    todos = []
    lines = content.split("\n")
    for i, line in enumerate(lines):
        match = TODO_REGEX.match(line)
        if match:
            indent = match.group(1)
            state_char = match.group(2).lower()
            text = match.group(3).strip()
            is_checked = (state_char == "x")
            
            todos.append(TodoItem(
                path=path,
                line_index=i,
                text=text,
                is_checked=is_checked,
                indent=indent
            ))
    return todos

def get_all_todos() -> Dict[Path, List[TodoItem]]:
    """
    notes フォルダ内のすべての txt ファイルから TODO を抽出し、
    Path をキーとした辞書で返却する。
    """
    if not NOTES_DIR.exists():
        return {}
    
    result = {}
    for note_path in NOTES_DIR.glob("*.txt"):
        try:
            content = note_path.read_text(encoding="utf-8")
        except OSError:
            continue
            
        todos = _parse_todos(content, note_path)
        if todos:
            result[note_path] = todos
            
    return result

def toggle_todo_in_text(content: str, line_index: int, is_checked: bool) -> str:
    """
    与えられたテキスト文字列の指定行の TODO ステータスを切り替えて新しいテキストを返す。
    行のインデックスが範囲外の場合はそのままテキストを返す。
    """
    lines = content.split("\n")
    if 0 <= line_index < len(lines):
        line = lines[line_index]
        match = TODO_REGEX.match(line)
        if match:
            indent = match.group(1)
            text = match.group(3)
            mark = "x" if is_checked else " "
            lines[line_index] = f"{indent}- [{mark}] {text}"
    return "\n".join(lines)
