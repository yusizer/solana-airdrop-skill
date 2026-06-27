#!/usr/bin/env bash
# install.sh — install the solana-airdrop-skill into a Solana AI Kit project.
#
# Copies skill/, agents/, commands/, rules/ into the project's .claude/ tree
# (creating it if needed), and the executable examples/ + tests/ into a
# solana-airdrop/ working dir. Idempotent. MIT.
#
# Usage:
#   ./install.sh                # install into ./ (cwd project)
#   ./install.sh /path/to/proj  # install into /path/to/proj
#   ./install.sh --dry-run      # print what would happen, change nothing
set -euo pipefail

DRY_RUN=0
TARGET="."
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--dry-run] [target-dir]"; exit 0 ;;
    *) TARGET="$1"; shift ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "solana-airdrop-skill installer"
echo "  source : $SCRIPT_DIR"
echo "  target : $TARGET"
echo "  mode   : $([ $DRY_RUN = 1 ] && echo 'DRY-RUN' || echo 'install')"

if [ ! -d "$TARGET" ]; then
  echo "ERROR: target dir does not exist: $TARGET" >&2
  exit 1
fi

copy() {  # copy <src-dir> <dst-dir> — copies the CONTENTS of src into dst
  if [ $DRY_RUN = 1 ]; then
    echo "  would copy  $1/* -> $2/"
  else
    mkdir -p "$2"
    # Copy the *contents* of $1 (with "$1/.") into $2 — NOT $1 itself. Using
    # `cp -r "$1" "$2"` would nest: $2/<basename-of-$1>/...  which puts SKILL.md
    # at .claude/skills/solana-airdrop/skill/SKILL.md (undetectable by Claude
    # Code) instead of .claude/skills/solana-airdrop/SKILL.md.
    cp -r "$1/." "$2/"
    echo "  copied      $1/* -> $2/"
  fi
}

CLAUDE_DIR="$TARGET/.claude"
copy "$SCRIPT_DIR/skill"        "$CLAUDE_DIR/skills/solana-airdrop"
copy "$SCRIPT_DIR/agents"       "$CLAUDE_DIR/agents"
copy "$SCRIPT_DIR/commands"     "$CLAUDE_DIR/commands"
copy "$SCRIPT_DIR/rules"        "$CLAUDE_DIR/rules"
copy "$SCRIPT_DIR/examples"     "$TARGET/solana-airdrop/examples"
copy "$SCRIPT_DIR/tests"        "$TARGET/solana-airdrop/tests"
copy "$SCRIPT_DIR/CLAUDE.md"    "$TARGET/solana-airdrop/CLAUDE.md"

if [ $DRY_RUN = 1 ]; then
  echo "DRY-RUN: no files changed."
else
  echo "Installed. Verify with:  python $TARGET/solana-airdrop/tests/test_eval.py"
fi
