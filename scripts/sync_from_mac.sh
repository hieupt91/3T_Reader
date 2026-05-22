#!/usr/bin/env bash
# =============================================================================
# sync_from_mac.sh — Sync tính năng Phase 1 từ branch phase1-mac sang phase1-win
#
# Cách dùng:
#   bash scripts/sync_from_mac.sh            # auto-copy file mới + hiện diff file sửa
#   bash scripts/sync_from_mac.sh --diff-only # chỉ xem diff, không copy
#   bash scripts/sync_from_mac.sh --auto-all  # copy luôn cả file đã sửa (THẬN TRỌNG)
#
# Logic:
#   - File CHỈ CÓ trên mac (A):  → tự động copy vào win nếu chưa có
#   - File ĐÃ SỬA (M):           → hiện git diff để dev review thủ công
#   - File WIN-SPECIFIC:          → luôn bỏ qua
# =============================================================================

set -euo pipefail

MAC_BRANCH="phase1-mac"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
cd "$REPO_ROOT"

DIFF_ONLY=0
AUTO_ALL=0
for arg in "$@"; do
  case "$arg" in
    --diff-only) DIFF_ONLY=1 ;;
    --auto-all)  AUTO_ALL=1  ;;
  esac
done

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; }
log_add()  { echo -e "${GREEN}[ADD]${NC}  $1"; }
log_diff() { echo -e "${BLUE}[DIFF]${NC} $1"; }
log_warn() { echo -e "${RED}[WARN]${NC} $1"; }

# ── Danh sách file KHÔNG được override (Windows-specific) ─────────────────
WIN_ONLY_FILES=(
  "packages/signing/windows_provider.py"
  "installer/windows/3T_Reader_Setup.iss"
  "installer/windows/3T_Reader_win.spec"
  "tests/test_smoke_windows.py"
  "app/platform_ui.py"
  "assets/3TReader.icns"
)

is_win_only() {
  local f="$1"
  for wo in "${WIN_ONLY_FILES[@]}"; do
    if [[ "$f" == "$wo" || "$f" == assets/3TReader.iconset/* ]]; then
      return 0
    fi
  done
  return 1
}

echo ""
echo "========================================================"
echo "  3T Reader — Sync Phase 1 Mac → Windows"
echo "  Mac branch : $MAC_BRANCH"
echo "  Current    : $(git branch --show-current)"
echo "========================================================"
echo ""

# ── Lấy danh sách file khác biệt ──────────────────────────────────────────
ADDED_FILES=()
MODIFIED_FILES=()

while IFS=$'\t' read -r status file; do
  case "$status" in
    A) ADDED_FILES+=("$file") ;;
    M) MODIFIED_FILES+=("$file") ;;
    D) log_warn "File bị xóa trên mac: $file (kiểm tra thủ công)" ;;
  esac
done < <(git diff phase1-win "$MAC_BRANCH" --name-status 2>/dev/null)

COPIED=0
SKIPPED=0
NEEDS_REVIEW=()

echo "--- FILE MỚI (chỉ có trên mac) ---"
for f in "${ADDED_FILES[@]}"; do
  if is_win_only "$f"; then
    log_skip "$f  ← win-specific, bỏ qua"
    (( SKIPPED++ )) || true
    continue
  fi

  if [[ -f "$f" ]]; then
    # File đã tồn tại local → kiểm tra nội dung
    MAC_CONTENT=$(git show "$MAC_BRANCH:$f" 2>/dev/null || echo "")
    LOCAL_CONTENT=$(cat "$f" 2>/dev/null || echo "")
    if [[ "$MAC_CONTENT" == "$LOCAL_CONTENT" ]]; then
      log_ok "$f  (đã giống mac)"
      (( SKIPPED++ )) || true
    else
      if [[ $DIFF_ONLY -eq 1 ]]; then
        log_diff "$f  (khác nội dung — xem diff bên dưới)"
        NEEDS_REVIEW+=("$f")
      elif [[ $AUTO_ALL -eq 1 ]]; then
        git checkout "$MAC_BRANCH" -- "$f"
        log_add "$f  [auto-all: override]"
        (( COPIED++ )) || true
      else
        log_diff "$f  (file tồn tại nhưng khác mac — thêm vào review)"
        NEEDS_REVIEW+=("$f")
      fi
    fi
  else
    # File chưa có → copy từ mac
    if [[ $DIFF_ONLY -eq 0 ]]; then
      mkdir -p "$(dirname "$f")"
      git checkout "$MAC_BRANCH" -- "$f"
      log_add "$f"
      (( COPIED++ )) || true
    else
      log_add "$f  (chưa có — sẽ copy khi chạy không có --diff-only)"
    fi
  fi
done

echo ""
echo "--- FILE ĐÃ SỬA (cần review / merge thủ công) ---"
for f in "${MODIFIED_FILES[@]}"; do
  if is_win_only "$f"; then
    log_skip "$f  ← win-specific, bỏ qua"
    (( SKIPPED++ )) || true
    continue
  fi

  # Kiểm tra có khác nhau không
  MAC_CONTENT=$(git show "$MAC_BRANCH:$f" 2>/dev/null || echo "")
  LOCAL_CONTENT=$(cat "$f" 2>/dev/null || echo "")

  if [[ "$MAC_CONTENT" == "$LOCAL_CONTENT" ]]; then
    log_ok "$f  (đã giống mac)"
    (( SKIPPED++ )) || true
  elif [[ $AUTO_ALL -eq 1 ]]; then
    git checkout "$MAC_BRANCH" -- "$f"
    log_add "$f  [auto-all: override]"
    (( COPIED++ )) || true
  else
    log_diff "$f"
    NEEDS_REVIEW+=("$f")
  fi
done

echo ""
echo "========================================================"
echo "  Kết quả:"
echo "  - Đã copy  : $COPIED file"
echo "  - Bỏ qua   : $SKIPPED file (win-specific hoặc đã giống)"
echo "  - Cần review: ${#NEEDS_REVIEW[@]} file"
echo "========================================================"

if [[ ${#NEEDS_REVIEW[@]} -gt 0 ]]; then
  echo ""
  echo "--- XEM DIFF từng file cần review ---"
  echo "(Dùng: q để thoát diff, Space để cuộn)"
  echo ""
  for f in "${NEEDS_REVIEW[@]}"; do
    echo "▶ $f"
    echo "  Lệnh xem diff:"
    echo "    git diff $MAC_BRANCH -- $f"
    echo "  Copy toàn bộ từ mac (nếu muốn):"
    echo "    git checkout $MAC_BRANCH -- $f"
    echo ""
  done

  echo "---"
  echo "Để xem diff tất cả cùng lúc:"
  echo "  git diff $MAC_BRANCH -- ${NEEDS_REVIEW[*]}"
  echo ""
  echo "Để copy tất cả file cần review từ mac (THẬN TRỌNG — overwrite local):"
  echo "  git checkout $MAC_BRANCH -- ${NEEDS_REVIEW[*]}"
fi

echo ""
echo "Tham khảo tài liệu đầy đủ: docs/PHASE1_MAC_HANDOVER.md"
echo ""
