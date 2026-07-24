#!/usr/bin/env python3
"""Find shortest no-spawn 2048 solutions and store them in level JSON files."""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from collections import deque
from pathlib import Path
from typing import Iterable, Sequence


DIRECTIONS = ("u", "d", "l", "r")


class LevelError(ValueError):
    """Raised when a level file or level cannot be solved safely."""


def traversal_lines(size: int, direction: str) -> tuple[tuple[int, ...], ...]:
    """Return board indices in the order tiles travel for a swipe."""
    if direction == "l":
        return tuple(tuple(range(row * size, (row + 1) * size)) for row in range(size))
    if direction == "r":
        return tuple(
            tuple(range((row + 1) * size - 1, row * size - 1, -1))
            for row in range(size)
        )
    if direction == "u":
        return tuple(tuple(range(column, size * size, size)) for column in range(size))
    if direction == "d":
        return tuple(
            tuple(range(column + (size - 1) * size, column - 1, -size))
            for column in range(size)
        )
    raise LevelError(f"unknown direction: {direction}")


def move(
    board: tuple[int, ...], lines: Sequence[Sequence[int]]
) -> tuple[int, ...]:
    """Apply one 2048 swipe without spawning a new tile."""
    moved = [0] * len(board)

    for line in lines:
        values = [board[index] for index in line if board[index] != 0]
        source = 0
        destination = 0

        while source < len(values):
            value = values[source]
            if source + 1 < len(values) and value == values[source + 1]:
                value *= 2
                source += 2
            else:
                source += 1
            moved[line[destination]] = value
            destination += 1

    return tuple(moved)


def validate_level(
    level: object, source: Path, index: int
) -> tuple[str, int, int, tuple[int, ...]]:
    if not isinstance(level, dict):
        raise LevelError(f"{source}: level {index} is not an object")

    level_id = str(level.get("id", index))
    size = level.get("boardSize")
    target = level.get("target")
    board = level.get("board")
    label = f"{source}: level {level_id}"

    if not isinstance(size, int) or isinstance(size, bool) or size < 2:
        raise LevelError(f"{label} has an invalid boardSize")
    if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
        raise LevelError(f"{label} has an invalid target")
    if not isinstance(board, list) or len(board) != size * size:
        raise LevelError(f"{label} must have exactly {size * size} board cells")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in board):
        raise LevelError(f"{label} board values must be non-negative integers")

    return level_id, size, target, tuple(board)


def shortest_solution(
    board: tuple[int, ...], size: int, target: int, max_states: int | None = None
) -> list[str] | None:
    """Return a shortest solution, or None if the reachable state space is exhausted."""
    if max(board, default=0) >= target:
        return []

    lines = {direction: traversal_lines(size, direction) for direction in DIRECTIONS}
    queue = deque([board])
    parents: dict[tuple[int, ...], tuple[tuple[int, ...] | None, str]] = {
        board: (None, "")
    }

    while queue:
        current = queue.popleft()
        for direction in DIRECTIONS:
            candidate = move(current, lines[direction])
            if candidate == current or candidate in parents:
                continue

            parents[candidate] = (current, direction)
            if max(candidate) >= target:
                solution: list[str] = []
                cursor = candidate
                while parents[cursor][0] is not None:
                    parent, step = parents[cursor]
                    solution.append(step)
                    cursor = parent
                solution.reverse()
                return solution

            queue.append(candidate)
            if max_states is not None and len(parents) >= max_states:
                raise LevelError(f"search exceeded the --max-states limit ({max_states})")

    return None


def apply_solution(
    board: tuple[int, ...], size: int, solution: Iterable[str]
) -> tuple[int, ...]:
    lines = {direction: traversal_lines(size, direction) for direction in DIRECTIONS}
    current = board
    for direction in solution:
        if direction not in lines:
            raise LevelError(f"invalid solution direction {direction!r}")
        current = move(current, lines[direction])
    return current


def load_level_file(path: Path) -> tuple[dict, list[object]]:
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise LevelError(f"cannot read {path}: {exc}") from exc

    if not isinstance(data, dict) or not isinstance(data.get("levels"), list):
        raise LevelError(f"{path} must contain a levels array")
    return data, data["levels"]


def write_json_atomically(path: Path, data: dict) -> None:
    """Avoid leaving a partially written level file if the process is interrupted."""
    temporary_name: str | None = None
    original_mode = stat.S_IMODE(path.stat().st_mode)
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(data, temporary, indent=2, ensure_ascii=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, original_mode)
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def process_file(path: Path, check: bool, dry_run: bool, max_states: int | None) -> int:
    data, levels = load_level_file(path)
    changed = 0

    for index, level in enumerate(levels):
        level_id, size, target, board = validate_level(level, path, index)
        assert isinstance(level, dict)  # Narrowed by validate_level.

        if check:
            solution = level.get("solution")
            if not isinstance(solution, list) or any(step not in DIRECTIONS for step in solution):
                raise LevelError(
                    f"{path}: level {level_id} solution must be an array containing only u, d, l, r"
                )
            if max(apply_solution(board, size, solution), default=0) < target:
                raise LevelError(f"{path}: level {level_id} solution does not reach {target}")
            continue

        solution = shortest_solution(board, size, target, max_states)
        if solution is None:
            raise LevelError(f"{path}: level {level_id} is not solvable")
        if level.get("solution") != solution:
            level["solution"] = solution
            changed += 1

    if not check and not dry_run and changed:
        write_json_atomically(path, data)

    action = "checked" if check else "solved"
    suffix = " (dry run)" if dry_run and not check else ""
    print(f"{path}: {action} {len(levels)} levels; {changed} updated{suffix}")
    return len(levels)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find shortest no-spawn 2048 solutions and add them to level JSON files."
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        default=[Path("levels.json"), Path("dailies.json")],
        help="level files to process (default: levels.json and dailies.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify stored solutions instead of finding and writing them",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="find all solutions but do not modify files",
    )
    parser.add_argument(
        "--max-states",
        type=int,
        help="abort a level search after visiting this many distinct board states",
    )
    return parser


def main() -> int:
    args = make_parser().parse_args()
    if args.max_states is not None and args.max_states < 1:
        raise SystemExit("error: --max-states must be positive")

    try:
        total = sum(
            process_file(path, args.check, args.dry_run, args.max_states)
            for path in args.files
        )
    except LevelError as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"total: {total} levels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
