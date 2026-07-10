# Level Creation Guide

This project uses deterministic 2048 puzzle levels: tiles do not spawn after swipes, so every level should be solvable from the starting board alone.

## JSON Shape

Normal levels live in `levels.json`:

```json
{
  "id": "M182",
  "boardSize": 4,
  "target": 256,
  "board": [0, 16, 4, 32, 0, 0, 0, 128, 0, 0, 64, 4, 0, 16, 8, 64]
}
```

Daily levels live in `dailies.json` and use date IDs:

```json
{
  "id": "08/03/2026",
  "boardSize": 5,
  "target": 4096,
  "board": [32, 8, 1024, 4, 16, 256, 64, 64, 2, 512, 8, 16, 128, 32, 4, 1024, 256, 16, 64, 128, 4, 512, 8, 256, 32]
}
```

## Board Rules

- `boardSize` is the row and column count.
- `board` is row-major order: left to right, top to bottom.
- A 4x4 board must have 16 numbers.
- A 5x5 board must have 25 numbers.
- Use `0` for an empty cell.
- `target` is reached when any tile is greater than or equal to that value.

## Difficulty Targets

Use shortest solution length as a baseline, then adjust by feel:

- Easy: 1-2 swipes, obvious merges.
- Medium: 4-6 swipes, with inconvenient placement or rogue tiles that punish careless swipes.
- Hard: 8-11 swipes, dense blockers and merge order constraints.
- Daily 5x5: usually 12+ swipes, dense boards, high targets such as `2048` or `4096`.

Shortest path length is not the whole difficulty. A level feels harder when:

- Several tiles can merge too early and ruin the intended route.
- Rogue tiles block columns or rows needed later.
- The correct first move is not visually obvious.
- The board is dense enough that bad swipes reduce mobility.

## Validation Checklist

Before adding a level:

- Confirm the JSON parses.
- Confirm IDs are unique.
- Confirm the board length matches `boardSize * boardSize`.
- Confirm the level is solvable without spawned tiles.
- Confirm medium and hard levels are not just easy boards with extra clutter.
- Confirm dailies are consecutive dates if they are part of a daily run.

## Practical Workflow

1. Sketch a board around the target tile chain you want.
2. Add rogue tiles that interfere with the obvious swipes.
3. Run a no-spawn solver to confirm the shortest path.
4. If it solves too quickly, add blockers or move key tiles apart.
5. If it becomes unsolvable, remove one blocker or lower the target.
