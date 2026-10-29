#!/usr/bin/env bash
# archive_evidence.sh — 把 AI CLI 的会话归档进 evidence/transcripts/
#
# 用途：比赛要求"AI 对话历史导出 + 细粒度演进链路"。
#       每次 commit 前跑一次，把原始会话 jsonl 落进仓库，证据事后无法伪造。
#
# 用法：
#   bash scripts/archive_evidence.sh              # 归档今天修改过的会话（推荐，每次提交前跑）
#   bash scripts/archive_evidence.sh 2026-10-29   # 归档指定日期
#   bash scripts/archive_evidence.sh --all        # 全量（仅首次初始化）
#
# 体积策略：>200KB 的会话自动 gzip 成 *.jsonl.gz（评审解压即可读），>20MB 跳过并告警。
# 环境变量：EVIDENCE_DEST 可覆盖输出目录（自测用）。
#
# 依赖：git-bash / Linux / macOS 的 find、date、cp、gzip。

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${EVIDENCE_DEST:-$ROOT/evidence/transcripts}"
mkdir -p "$DEST"

# 工具 -> 会话根目录（本机 2026-10-28 实测确认）
SOURCES=(
  "$HOME/.claude/projects"     # Claude Code : <slug>/<uuid>.jsonl
  "$HOME/.qwen/projects"       # Qwen Code   : <slug>/chats/<uuid>.jsonl
  "$HOME/.codex/sessions"      # Codex CLI   : YYYY/MM/DD/rollout-*.jsonl
)

MODE="${1:-today}"
STAMP="$(date +%Y%m%d-%H%M%S)"

new=0; skipped=0; big=0

for src in "${SOURCES[@]}"; do
  [ -d "$src" ] || continue
  tool="$(basename "$(dirname "$src")")"
  tool="${tool#.}"                       # .claude -> claude（否则生成隐藏文件）

  case "$MODE" in
    --all) files=$(find "$src" -type f -name '*.jsonl' 2>/dev/null) ;;
    today) files=$(find "$src" -type f -name '*.jsonl' -mtime -1 2>/dev/null) ;;
    *)     files=$(find "$src" -type f -name '*.jsonl' \
                   -newermt "${MODE} 00:00" ! -newermt "${MODE} 23:59" 2>/dev/null) ;;
  esac

  while IFS= read -r f; do
    [ -n "$f" ] || continue
    slug="$(basename "$(dirname "$f")")"
    [ "$slug" = "chats" ] && slug="$(basename "$(dirname "$(dirname "$f")")")"
    base="$(basename "$f")"

    # 判重：同一会话（uuid 相同）已归档则跳过
    if find "$DEST" -maxdepth 1 -name "*__${base}*" -type f | grep -q .; then
      skipped=$((skipped + 1)); continue
    fi

    size=$(wc -c < "$f" | tr -d ' ')
    if [ "$size" -gt 20971520 ]; then
      echo "  ! 跳过超大会话 ($((size/1048576))MB): $f" >&2
      big=$((big + 1)); continue
    fi

    out="$DEST/${tool}__${slug}__${STAMP}__${base}"
    if [ "$size" -gt 204800 ]; then
      gzip -c "$f" > "${out}.gz" && new=$((new + 1))
    else
      cp "$f" "$out" && new=$((new + 1))
    fi
  done <<< "$files"
done

echo "归档完成：新增 $new，跳过重复 $skipped，跳过超大 $big -> $DEST"
echo "提示：commit 时一并提交 evidence/transcripts/，message 写 (prompt: Pxx)"
