#!/usr/bin/env bash
set -u

ROOT_DIR="/home/luot/27thesis"
GEM5_BIN="$ROOT_DIR/tools/gem5/build/RISCV/gem5.opt"
BENCHMARK="$ROOT_DIR/build/vadd_N1024.riscv"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/overnight_continue.log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

commit_and_push() {
  local message="$1"
  shift

  cd "$ROOT_DIR" || exit 1
  git add -A -- "$@" || return 1
  if git diff --cached --quiet; then
    log "nothing to commit for: $message"
  else
    git commit -m "$message" || return 1
  fi
  git push -u origin main || log "push failed for: $message"
}

run_step() {
  local name="$1"
  shift

  log "START $name"
  "$@"
  local rc=$?
  log "END $name rc=$rc"
  return "$rc"
}

cd "$ROOT_DIR" || exit 1
log "overnight continuation started"

while [ ! -x "$GEM5_BIN" ]; do
  log "gem5.opt not ready; sleeping 5 hours"
  sleep 18000
done

log "gem5.opt is ready: $GEM5_BIN"

if [ ! -f "$BENCHMARK" ]; then
  log "benchmark missing: $BENCHMARK"
  exit 1
fi

run_step "step4_o3_nopf" \
  python3 scripts/run_gem5.py \
    --gem5-bin "$GEM5_BIN" \
    --benchmark "$BENCHMARK" \
    --bench-name vadd_N1024 \
    --config o3_nopf
commit_and_push \
  "step 4: run vadd on O3 no-prefetch" \
  README.md notes scripts gem5_configs benchmarks build results

{
  echo "# BOOM-like O3 Verification"
  echo
  echo "Date: $(date -Is)"
  echo
  echo "This note records whether the BOOM-like gem5 O3 config was accepted by"
  echo "the completed no-prefetch run. It is not a cycle-accurate BOOM claim."
  echo
  echo '```text'
  if [ -f results/vadd_N1024/o3_nopf/config.ini ]; then
    grep -E "system.cpu|numROBEntries|fetchWidth|decodeWidth|issueWidth|commitWidth" \
      results/vadd_N1024/o3_nopf/config.ini || true
  else
    echo "config.ini not found"
  fi
  echo '```'
} > notes/boom_like_config_verification.md
commit_and_push \
  "step 6: verify BOOM-like O3 baseline config" \
  README.md notes gem5_configs results

run_step "step7_o3_stridepf" \
  python3 scripts/run_gem5.py \
    --gem5-bin "$GEM5_BIN" \
    --benchmark "$BENCHMARK" \
    --bench-name vadd_N1024 \
    --config o3_stridepf
commit_and_push \
  "step 7: verify stride-prefetch baseline" \
  README.md notes scripts gem5_configs results

run_step "step8_parse_stats" \
  python3 scripts/parse_stats.py --results-dir results
commit_and_push \
  "step 8: add gem5 stats summary" \
  README.md notes scripts results

log "overnight continuation finished"
