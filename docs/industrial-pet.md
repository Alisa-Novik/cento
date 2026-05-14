# Darth Lolipopus Pet Pane

`cento industrial-pet` opens a Bubble Tea pane for Darth Lolipopus, the Cute Sith pet used by the Industrial OS workspace.

## Commands

```bash
cento industrial-pet
cento industrial-pet --once --width 98 --height 24
cento industrial-pet --action nap
cento industrial-pet --image assets/industrial-os/darth-lolipopus.png
cento industrial-pet --portrait slot
cento industrial-pet --reset
```

## Automation Flags

- `--once` renders once and exits.
- `--action ACTIVITY_ID` performs one activity and saves state.
- `--state PATH` overrides the pet state path.
- `--database PATH` overrides the activity/comment database.
- `--image PATH` overrides the Darth Lolipopus portrait image.
- `--portrait ansi|slot|none` chooses terminal-pixel portrait, reserved image slot, or no portrait.
- `--reset` resets state for Darth Lolipopus.
- `--width` and `--height` make non-interactive renders deterministic.

## State

The default state path is:

```text
${XDG_STATE_HOME:-~/.local/state}/cento/industrial-os/darth-lolipopus.json
```

Tests and automation should pass `--state` and `--database` so validation does not touch the operator's live pet state.

## Controls

- `j` / `k`: select an activity.
- `1`-`6`: perform a quick activity.
- `enter`: perform the selected activity.
- `r`: refresh state and elapsed-time decay.
- `q`: quit.

Industrial OS launches this pane as `cento-industrial-pet` in the bottom-left tile of the workspace.
The default portrait is `assets/industrial-os/darth-lolipopus.png`, matching the rofi launcher side art.
The workspace pane uses `assets/industrial-os/darth-lolipopus-pane.png` as a high-resolution Kitty background and starts the TUI with `--portrait slot`, so the live pane shows the real bitmap instead of a low-resolution terminal-cell copy.
