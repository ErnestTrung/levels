#!/usr/bin/env python3
"""Terminal 2048 puzzle tester for levels.json."""

from __future__ import annotations

import argparse
import ast
import json
import random
import shlex
from pathlib import Path


SIZE = 4
COMMANDS = {
    "u": "up",
    "up": "up",
    "w": "up",
    "d": "right",
    "right": "right",
    "r": "right",
    "s": "down",
    "down": "down",
    "l": "left",
    "left": "left",
    "a": "left",
}


def parse_board(text: str) -> list[int]:
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        parsed = None

    if isinstance(parsed, list):
        parts = parsed
    else:
        parts = text.strip("[]()").replace(",", " ").split()

    if len(parts) != SIZE * SIZE:
        raise ValueError(f"expected 16 numbers, got {len(parts)}")

    try:
        board = [int(part) for part in parts]
    except (TypeError, ValueError) as exc:
        raise ValueError("board must contain integers only") from exc

    if any(value < 0 for value in board):
        raise ValueError("board values cannot be negative")

    return board


def board_rows(board: list[int]) -> list[list[int]]:
    return [board[row * SIZE : (row + 1) * SIZE] for row in range(SIZE)]


def flatten(rows: list[list[int]]) -> list[int]:
    return [value for row in rows for value in row]


def merge_line(line: list[int]) -> list[int]:
    values = [value for value in line if value != 0]
    merged: list[int] = []
    index = 0

    while index < len(values):
        if index + 1 < len(values) and values[index] == values[index + 1]:
            merged.append(values[index] * 2)
            index += 2
        else:
            merged.append(values[index])
            index += 1

    return merged + [0] * (SIZE - len(merged))


def move(board: list[int], direction: str) -> tuple[list[int], bool]:
    rows = board_rows(board)

    if direction == "left":
        moved_rows = [merge_line(row) for row in rows]
    elif direction == "right":
        moved_rows = [list(reversed(merge_line(list(reversed(row))))) for row in rows]
    elif direction == "up":
        columns = [[rows[row][col] for row in range(SIZE)] for col in range(SIZE)]
        moved_columns = [merge_line(column) for column in columns]
        moved_rows = [
            [moved_columns[col][row] for col in range(SIZE)] for row in range(SIZE)
        ]
    elif direction == "down":
        columns = [[rows[row][col] for row in range(SIZE)] for col in range(SIZE)]
        moved_columns = [
            list(reversed(merge_line(list(reversed(column))))) for column in columns
        ]
        moved_rows = [
            [moved_columns[col][row] for col in range(SIZE)] for row in range(SIZE)
        ]
    else:
        raise ValueError(f"unknown direction: {direction}")

    moved_board = flatten(moved_rows)
    return moved_board, moved_board != board


def add_random_tile(board: list[int]) -> list[int]:
    empty = [index for index, value in enumerate(board) if value == 0]
    if not empty:
        return board

    board = board[:]
    board[random.choice(empty)] = 4 if random.random() < 0.1 else 2
    return board


def can_move(board: list[int]) -> bool:
    return any(move(board, direction)[1] for direction in ("up", "down", "left", "right"))


def load_levels(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    levels = data.get("levels")
    if not isinstance(levels, list):
        raise ValueError(f"{path} does not contain a levels array")

    return levels


def level_by_id(levels: list[dict], level_id: str) -> dict:
    for level in levels:
        if str(level.get("id", "")).lower() == level_id.lower():
            return level
    raise ValueError(f"level not found: {level_id}")


def format_board(board: list[int]) -> str:
    width = max(4, max(len(str(value)) for value in board))
    border = "+" + "+".join("-" * (width + 2) for _ in range(SIZE)) + "+"
    lines = [border]

    for row in board_rows(board):
        cells = [str(value).rjust(width) if value else ".".rjust(width) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
        lines.append(border)

    return "\n".join(lines)


def print_status(board: list[int], start_board: list[int], target: int | None, moves: int) -> None:
    print()
    print(format_board(board))
    print(f"moves: {moves}")
    print("array:", board)

    if target is not None:
        best = max(board)
        state = "reached" if best >= target else "not reached"
        print(f"target: {target} ({state}, best {best})")

    if board == start_board and moves:
        print("board is back at the start")

    if not can_move(board):
        print("no moves left")


def choose_level(levels: list[dict], level_id: str | None) -> dict:
    if level_id:
        return level_by_id(levels, level_id)

    print("Available levels:")
    print(" ".join(str(level.get("id", "?")) for level in levels))

    while True:
        choice = input("level id> ").strip()
        if not choice:
            continue
        return level_by_id(levels, choice)


def read_board_from_prompt() -> list[int]:
    while True:
        text = input("16-number board array> ").strip()
        if not text:
            continue
        try:
            return parse_board(text)
        except ValueError as exc:
            print(f"Invalid board: {exc}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Play/test a deterministic 2048 board from levels.json or a 16-number array."
    )
    parser.add_argument(
        "board",
        nargs="*",
        help="16 board numbers. Commas are allowed inside quoted input.",
    )
    parser.add_argument("--level", "-l", help="level id from levels.json, for example E1")
    parser.add_argument(
        "--levels",
        default="levels.json",
        help="path to levels JSON file (default: levels.json)",
    )
    parser.add_argument("--target", "-t", type=int, help="target tile to report as solved")
    parser.add_argument(
        "--random-spawn",
        action="store_true",
        help="spawn a 2 or 4 after successful moves, like normal 2048",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list level ids and targets, then exit",
    )
    return parser


def initial_state(args: argparse.Namespace) -> tuple[list[int], int | None, str]:
    levels_path = Path(args.levels)

    if args.list:
        levels = load_levels(levels_path)
        for level in levels:
            print(f"{level.get('id', '?')}: target {level.get('target', '?')}")
        raise SystemExit(0)

    if args.board:
        board = parse_board(" ".join(args.board))
        return board, args.target, "custom board"

    if args.level:
        level = level_by_id(load_levels(levels_path), args.level)
        board = level.get("board")
        if not isinstance(board, list):
            raise ValueError(f"level {args.level} has no board array")
        return parse_board(" ".join(str(value) for value in board)), args.target or level.get("target"), str(level.get("id"))

    if levels_path.exists():
        try:
            level = choose_level(load_levels(levels_path), None)
            board = level.get("board")
            if not isinstance(board, list):
                raise ValueError(f"level {level.get('id')} has no board array")
            return parse_board(" ".join(str(value) for value in board)), args.target or level.get("target"), str(level.get("id"))
        except (OSError, ValueError) as exc:
            print(f"Could not load levels: {exc}")

    return read_board_from_prompt(), args.target, "custom board"


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()

    try:
        start_board, target, label = initial_state(args)
    except ValueError as exc:
        parser.error(str(exc))

    board = start_board[:]
    moves = 0
    print(f"Testing {label}")
    print("Commands: up/down/left/right, restart, board <16 numbers>, quit")
    print("Shortcuts: w/a/s/d, u/l/r/d")

    while True:
        print_status(board, start_board, target, moves)
        raw_command = input("> ").strip()
        if not raw_command:
            continue

        parts = shlex.split(raw_command)
        command = parts[0].lower()

        if command in {"q", "quit", "exit"}:
            return 0

        if command in {"restart", "reset"}:
            board = start_board[:]
            moves = 0
            continue

        if command == "board":
            try:
                start_board = parse_board(" ".join(parts[1:]))
            except ValueError as exc:
                print(f"Invalid board: {exc}")
                continue
            board = start_board[:]
            moves = 0
            continue

        direction = COMMANDS.get(command)
        if not direction:
            print("Unknown command. Use up/down/left/right, restart, board, or quit.")
            continue

        board, changed = move(board, direction)
        if not changed:
            print(f"{direction} did not change the board")
            continue

        moves += 1
        if args.random_spawn:
            board = add_random_tile(board)


if __name__ == "__main__":
    raise SystemExit(main())
