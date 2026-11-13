#!/bin/sh
# Run a command with a jarvisd-style clean environment (spike only).
exec env -i HOME="$HOME" USER="$USER" LOGNAME="$USER" SHELL=/bin/zsh TERM=xterm-256color \
  PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin" "$@"
