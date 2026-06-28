# Overnight gem5 Continuation SOP

## Purpose

This SOP is for the situation where the gem5 build is still running and I need
to leave the machine unattended. The goal is:

1. wait until `tools/gem5/build/RISCV/gem5.opt` is available;
2. continue the remaining baseline steps;
3. commit and push after each completed step;
4. leave enough logs to diagnose failures in the morning.

Important limitation: a normal shell script can wait for compilation to finish,
but it cannot automatically wake up an interactive chat session. Fully automatic
continuation requires either:

- a persistent Codex CLI/API runner with repository access; or
- deterministic local scripts that perform the remaining runs and commits.

If neither is available, the fallback is to leave the build running overnight
and resume with Codex manually after `gem5.opt` appears.

## Current Repository Assumptions

- Repository root: `/home/luot/27thesis`
- Branch: `main`
- Remote: `origin`
- gem5 source directory: `tools/gem5`
- expected gem5 binary: `tools/gem5/build/RISCV/gem5.opt`
- first benchmark binary: `build/vadd_N1024.riscv`
- no-prefetch config: `o3_nopf`
- stride-prefetch config: `o3_stridepf`

Do not commit `tools/gem5` or gem5 build products unless explicitly intended.
They are large external build artifacts.

## Sleep-Time Checklist

Run these from the repository root before leaving:

```bash
cd /home/luot/27thesis
git status --short
git remote -v
test -f build/vadd_N1024.riscv && echo "benchmark ready"
test -f scripts/run_gem5.py && echo "run wrapper ready"
```

Check whether gem5 is already done:

```bash
test -x tools/gem5/build/RISCV/gem5.opt && echo "gem5.opt ready" || echo "gem5 still building"
```

For a one-shot build progress summary:

```bash
./scripts/monitor_gem5_build.sh
```

## Commit Rules

Commit after each step that creates a meaningful, reviewable state.

Recommended commit boundaries:

1. docs/SOP update;
2. successful `o3_nopf` run artifacts or run-log update;
3. successful `o3_stridepf` verification or documented failure;
4. stats parser implementation;
5. parsed result table and README update.

Use targeted `git add` commands. Avoid `git add .` while `tools/gem5` is
untracked:

```bash
git add README.md notes scripts gem5_configs benchmarks build results
git commit -m "step N: short description"
git push origin main
```

If `git push` fails because credentials are unavailable, keep the local commit
and record the failure in a note or log. Do not rewrite history or force-push.

## Remaining Step Plan After gem5.opt Exists

### Step 4 Verification: Run O3 No-Prefetch

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_nopf
```

Expected output directory:

```text
results/vadd_N1024/o3_nopf/
  config.json
  simout
  simerr
  stats.txt
```

Success criteria:

- command exits with status 0;
- `stats.txt` exists;
- `simerr` does not show a fatal gem5 configuration error.

Commit after success:

```bash
git add results/vadd_N1024/o3_nopf README.md notes scripts gem5_configs
git commit -m "step 4: run vadd on O3 no-prefetch"
git push origin main
```

If it fails, keep `simout`, `simerr`, and `config.json`, then commit the
diagnostic state with a message such as:

```bash
git add results/vadd_N1024/o3_nopf notes
git commit -m "step 4: record gem5 no-prefetch failure"
git push origin main
```

### Step 6 Verification: Confirm BOOM-like O3 Config

After the no-prefetch run succeeds, confirm that the implemented config was
actually used:

```bash
grep -E "system.cpu|numROBEntries|fetchWidth|decodeWidth|issueWidth|commitWidth" \
  results/vadd_N1024/o3_nopf/config.ini || true
```

Success criteria:

- gem5 accepted `gem5_configs/riscv_o3_baseline.py`;
- the run reached `stats.txt`;
- no claim is made that this is cycle-accurate BOOM.

Commit any documentation update:

```bash
git add README.md notes gem5_configs
git commit -m "step 6: verify BOOM-like O3 baseline config"
git push origin main
```

### Step 7: Run or Diagnose Stride-Prefetch Baseline

```bash
python3 scripts/run_gem5.py \
  --gem5-bin tools/gem5/build/RISCV/gem5.opt \
  --benchmark build/vadd_N1024.riscv \
  --bench-name vadd_N1024 \
  --config o3_stridepf
```

Expected output directory:

```text
results/vadd_N1024/o3_stridepf/
  config.json
  simout
  simerr
  stats.txt
```

Success criteria:

- command exits with status 0;
- `stats.txt` exists;
- config files show the D-cache prefetcher was instantiated.

If this gem5 version rejects the stride prefetcher parameters, document the
exact error from `simerr`, adjust the config if the fix is clear, and rerun. If
the fix is not clear, commit the documented failure instead of pretending Step 7
is complete.

Commit after success or documented failure:

```bash
git add results/vadd_N1024/o3_stridepf README.md notes gem5_configs scripts
git commit -m "step 7: verify stride-prefetch baseline"
git push origin main
```

### Step 8: Implement Stats Parser

Create:

```text
scripts/parse_stats.py
```

Minimum behavior:

- scan `results/*/*/stats.txt`;
- emit `results/summary.csv`;
- tolerate missing fields;
- include benchmark name and config name;
- parse common gem5 fields such as `simInsts`, `simTicks`, `system.cpu.numCycles`,
  and cache/prefetch fields when present.

Run:

```bash
python3 scripts/parse_stats.py --results-dir results
```

Commit after success:

```bash
git add scripts/parse_stats.py results/summary.csv README.md notes
git commit -m "step 8: add gem5 stats parser"
git push origin main
```

## Optional Watch-Only Shell Helper

This helper does not run Codex. It only waits for `gem5.opt` and writes a marker
file when the binary appears:

```bash
mkdir -p logs
nohup bash -lc '
  cd /home/luot/27thesis
  while [ ! -x tools/gem5/build/RISCV/gem5.opt ]; do
    date
    ./scripts/monitor_gem5_build.sh || true
    sleep 900
  done
  date
  echo "gem5.opt ready" > logs/GEM5_READY
' > logs/wait_for_gem5.log 2>&1 &
```

Check it later:

```bash
tail -50 logs/wait_for_gem5.log
cat logs/GEM5_READY 2>/dev/null || true
```

## Morning Resume Prompt

If full automation was not used, resume Codex with:

```text
gem5.opt 应该已经编好了。请按 notes/overnight_gem5_sop.md 继续：
先验证 Step 4 no-prefetch run，然后 Step 6 config verification，
再 Step 7 stride-prefetch，最后 Step 8 stats parser。
每完成一个 step 就 commit + push；不要提交 tools/gem5。
```

