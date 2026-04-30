#!/usr/bin/env bash

# cento config
#
# Syntax:
#   cento_alias NAME --description "Human-readable note" -- command arg1 arg2 ...
#
# Simple examples:
#   cento_alias dark --description "Apply a dark Kitty theme" -- "$HOME/bin/codex-kitty-theme" --theme "Cento Tokyo Night"
#   cento_alias wallpaper --description "Choose desktop wallpaper" -- "$HOME/bin/cento" wallpaper-manager --choose
#
# Combined examples:
#   cento_alias monk --description "Templars + Rose Pine" -- bash -lc '"$HOME/bin/cento" kitty-theme-manager --theme "Cento Rose Pine" && "$HOME/bin/cento" wallpaper-manager --set "templars.png"'
#   cento_alias cyber --description "New York + Rose Pine" -- bash -lc '"$HOME/bin/cento" kitty-theme-manager --theme "Cento Rose Pine" && "$HOME/bin/cento" wallpaper-manager --set "newyorkamb.png"'

cento_alias dark --description "Apply a dark Kitty theme" -- "$HOME/bin/codex-kitty-theme" --theme "Cento Tokyo Night"
cento_alias rose --description "Apply the Rose Pine Kitty theme" -- "$HOME/bin/codex-kitty-theme" --theme "Cento Rose Pine"
cento_alias theme --description "Open the Kitty theme picker" -- "$HOME/bin/codex-kitty-theme" --plain-menu
cento_alias bt-audio --description "Run the Bluetooth audio doctor" -- "$HOME/bin/codex-bt-audio-doctor"
cento_alias audio --description "Quick connect a Bluetooth audio device" -- "$HOME/bin/cento" audio-quick-connect
cento_alias wallpaper --description "Choose desktop wallpaper" -- "$HOME/bin/cento" wallpaper-manager --choose
cento_alias monk --description "Templars + Rose Pine" -- bash -lc '"$HOME/bin/cento" kitty-theme-manager --theme "Cento Rose Pine" && "$HOME/bin/cento" wallpaper-manager --set "templars.png"'
cento_alias cyber --description "New York + Rose Pine" -- bash -lc '"$HOME/bin/cento" kitty-theme-manager --theme "Cento Rose Pine" && "$HOME/bin/cento" wallpaper-manager --set "newyorkamb.png"'

cento_alias displayfix --description "Fix stacked monitor layout" -- "$HOME/bin/cento" display-layout-fix --save-defaults

cento_alias quickhelp --description "Open cento quick help" -- "$HOME/bin/cento" quick-help
cento_alias ask --description "Submit a natural-language cluster request" -- "$HOME/bin/cento" cluster ask
