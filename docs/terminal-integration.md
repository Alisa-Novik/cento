# Cento Terminal Integration

Cento manages terminal integration through generated files under
`~/.config/cento` plus one guarded source block in each user-owned config.

## Commands

- `cento install zsh`
  Installs Zsh completion and writes `~/.config/cento/init.zsh`.
- `cento install tmux`
  Installs the tmux status badge fragment and sources it from `~/.tmux.conf`.
- `cento install terminal`
  Installs the Zsh/Oh My Zsh prompt and completion path.
- `cento install all`
  Alias for `cento install terminal`.
- `cento tmux badge`
  Prints the label rendered in the tmux status bar.
- `cento tmux status`
  Prints installed tmux paths and source-block state.
- `cento tmux docs`
  Prints tmux integration help.

## Managed Files

- `~/.config/cento/completions/_cento`
  Managed completion copy.
- `~/.config/cento/init.zsh`
  Managed Zsh init snippet. It is compatible with plain Zsh and Oh My Zsh and
  adds a right-prompt segment like `[cento:linux:host]`.
- `~/.config/cento/tmux.conf`
  Managed tmux fragment. It prepends the Cento badge to `status-left`.
- `~/.zshrc`
  User file. Cento only adds the block between `# >>> cento init >>>` and
  `# <<< cento init <<<`.
- `~/.tmux.conf`
  User file. Cento only adds the block between `# >>> cento tmux >>>` and
  `# <<< cento tmux <<<`.

## Oh My Zsh Contract

`cento install zsh` is designed to be sourced after Oh My Zsh has loaded. When
`compdef` is already available, Cento uses it directly. When it is not
available, the generated init snippet autoloads and runs `compinit` before
registering `_cento`.

The installer appends the Cento block to `~/.zshrc`, which keeps the normal Oh
My Zsh setup above it.

## Zsh Prompt Contract

The generated Zsh init adds a right-prompt segment:

```zsh
[cento:linux:hostname]
```

The platform is normalized to `linux` or `macos`. Set `CENTO_PROMPT_BADGE` to
override the whole label, or set `CENTO_PROMPT_DISABLE=1` before sourcing the
init file to disable the prompt segment while keeping completion.

## Tmux Badge Contract

Tmux integration is opt-in. The tmux installer captures the current `status-left` as
`@cento_status_left_base` and writes a generated `~/.config/cento/tmux.conf`.
The generated status prepends:

```tmux
#[fg=black,bg=green,bold] #(cento tmux badge) #[default]
```

The badge command prints `cento` by default. Set `CENTO_TMUX_BADGE` to override
the label and `CENTO_TMUX_BADGE_HOST=1` to append the short hostname.

Re-run `cento install tmux` after changing the hand-written `status-left` if
you want Cento to capture a new base.

## E2E Verification

Run:

```bash
make terminal-e2e
```

The e2e script creates a temporary home directory, runs `cento install
terminal`, verifies the managed Zsh files, checks that the source block is
idempotent, validates the prompt segment, separately verifies opt-in tmux
installation, and runs `zsh -n` on the generated init when Zsh is available.

## AI Agent Notes

- Keep generated content in `scripts/cento.sh`; do not hand-edit generated
  files in a user's home directory as the source of truth.
- When changing root built-ins, update `data/cento-cli.json`,
  `docs/cento-cli.md`, `README.md`, and completion in
  `scripts/completion/_cento`.
- Use `make terminal-e2e` for terminal integration changes and `make check` for
  the broader repo sanity pass.
