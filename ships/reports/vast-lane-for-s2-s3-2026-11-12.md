# The Vast lane: findings for S2 and S3 — 12 November 2026

**Audience:** S2 (coordinator: `thorp/viable/s2_coordination/lanes.py`, the queue), S3 (purser:
`thorp/viable/s3_control/purser.py`, the quote), and S5 (the terms the two read). **Basis:** the 9m candidate's
failure and the 50m of 9 November, the timing table on `/settings/server` (Vast → Where the time goes), and the
four-class smoke test. **State at handover:** Vast lane **paused**, no ship out, `9m@v0.0.6-candidate` then
`candidate-bridge` at the top of the Vast lane, Mac lane running `300k@v0.0.6-probe-s2`; week $1.53 of $30,
all-time $3.58.

## 1. What happened, in numbers

**The 9m candidate, 12 November (RTX 4090, $0.363/h).** Hired 09:32:55. It spent **55 m 32 s** tarring
**9.07 GB** of `data/` aboard (6.82 GB `catalogue` + 1.60 GB `classics` were 8.4 GB of it), then began the
211 MB manifest rsync. The box's ssh died; Vast still reported `actual_status: running`; rsync had no timeout.
The charter sat in **setup** for a further ~18 minutes until it was killed by hand. **Zero training. $0.44.**
The 10:50 retry with the trimmed payload reached the code tar (113 MB) and was stopped for the smoke tests
(1 m 19 s, $0.01). No end-to-end 9m voyage has yet run on the new payload.

**The 50m, 9 November (RTX 5090, $0.476/h) — a healthy shape:**

| Part | Time | Share |
|---|---:|---:|
| **Setup** (provision 25 s, ssh 3 m 24 s, code 15 s, data 23 m 46 s, manifest 27 s, env 6 m 02 s) | **34 m 19 s** | **30.8%** |
| **Training** | **68 m 53 s** | **61.8%** |
| **Home** (checkpoint/log pull, release) | **7 m 55 s** | **7.1%** |
| **Total** | 1 h 51 m | 100% |

Quote 0.756 h, actual 1.86 h: it overran. Duty cycle (`training / total`) **62%**.

**What the payload is now.** `catalogue`, `classics` and `models` are no longer carried. The data tar is now **~0.65 GB** — 0.45 GB of
shards and records plus the voyage's own texts (~0.2 GB for the 9m candidate) — and the manifest 0.20 GB:
**~0.85 GB against 9.28 GB, an 11× cut**. At the
1.3–2.7 MB/s the old hires implied, setup falls from ~73 m to roughly **12–20 m** for a 9m.

**The four-class smoke test (all passed, all released, ~$0.18):**

| Class | Device | BF16 TFLOPS | FP32 TFLOPS | VRAM | SMs | $/h | Wall | Cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| RTX 4090 | RTX 4090 | 148.6 | 42.8 | 23.5 GB | 128 | 0.370 | 122 s | $0.012 |
| RTX 5090 | RTX 5090 | 239.4 | 67.8 | 31.4 GB | 170 | 0.463 | 166 s | $0.021 |
| H100 SXM | H100 80GB HBM3 | 725.4 | 52.0 | 79.2 GB | 132 | 2.344 | 50 s | $0.031 |
| H100 PCIE | H100 PCIe | 472.7 | 36.7 | 79.2 GB | 114 | 2.004 | 220 s | $0.119 |

Achieved = dense 8192³ bf16, 100 iterations, fp32 with TF32 off, in `torch 2.7.1+cu128`; it is a matmul ceiling,
not a training rate. Relative bf16: 5090 **1.61×** the 4090, H100 SXM **4.88×**, H100 PCIE **3.18×**.

## 2. What is already changed in the code

- `s1_operations/charter.py`: `NOT_CARRIED` now excludes `catalogue`, `classics`, `models`; every ssh/rsync/tar
  step is bounded (`sh` 600 s, transfers 1,800 s, pulls 900 s); rsync `--timeout=120 --contimeout=30`; ssh
  `ServerAliveInterval=15 ServerAliveCountMax=3`; a **30-minute fit-out deadline** (`FITOUT_MINUTES`,
  `THORP_FITOUT_MINUTES`); transfers log MB; `_release`'s status is recorded for recalled/gone/lost.
- `dash/settings.py`: `charters()` reads `data/runs/charter.log`, joins the spend log by instance, and exposes
  setup/training/home; an aborted open phase ends at the release, not the next quote; released-not-home reads
  as **aborted** with the reason.
- `/settings/server` → Vast: **setup / training / home** with duty cycle and "home onto this Mac"; the market
  table still groups *the market* and *the voyages*.
- `backend/scripts/smoke_vast_gpus.py`: the four-class smoke above; `smoke-vast.json` has the raw results.
- The dead-body hire was closed in the spend log as `recalled (SIGTERM)`, $0.44; the smoke script's
  interrupted 5090 hire was released for $0.0004. `thorp charter audit` then found no ghosts or orphans, and
  no instances are out.

## 3. Findings for S2 — the coordinator

### 3.1 A box failure is requeued as a voyage failure

`lanes.run` does `if code != 0 and seat["line"].routed: _come_home(...)`, and `_come_home` requeues the line at
the top as **`mac: <spec>`**, permanently pinned. That is right for a voyage that **sailed and failed** (the
spec may be bad; retry here). It is wrong for a **fit-out/box failure** — no `at sea` event, no run: the voyage
never got a GPU. The 9m candidate and the bridge were both pinned to the Mac this way, and would have run there
behind the 300k rather than retried abroad.

**Change:** classify before requeueing. Read the spend log's release for the line (or the `at sea` event):

- **no `at sea` event** (fit-out deadline, dead box, refused ssh, stalled copy) → requeue **unpinned on the Vast
  lane**, with a different-host preference and a cooldown; do not consume a Mac seat.
- **an `at sea` event and a failed run** → the existing `mac:` pin stands.

Record the class in `queue_history` (`fitout-failed` vs `voyage-failed`) and the **lane it actually sailed on**
(today a Vast failure is written with `lane=mac`, status `143`).

### 3.2 No circuit breaker

After the candidate died, the coordinator immediately started `candidate-bridge` at 10:46, which would have
repeated the same hour. A **two-consecutive-fit-out-failure** breaker (per lane) should pause the lane and raise
an S2 lint, rather than consuming the next line. `attempts` exists today only for launch failures.

### 3.3 The fit-out deadline is in the charter, not the lane

`Line.timeout` applies to `cmd:` lines only; a spec has no deadline. The charter now bounds its own fit-out
(30 m), which is the right place, but S2 should also see a spec that is silent past `quote × overrun` or past
the fit-out deadline and classify it as a box failure. Move the 30 m into S5 as a term so both read the same
number.

### 3.4 Home competes with the Mac lane

Home is billed on Vast but runs on this Mac: the checkpoint/log pull writes `data/checkpoints`, `data/runs` and
the ledger, and can slow the Mac lane's training or evals. Nothing in S2 knows a home is in progress.

**Change:** a `home` marker (a row in `s2.lanes`, a lock, or an `at_sea`-like record) while a Vast pull runs;
either hold the next Mac spec until it finishes, or `rsync --bwlimit` it; pull **only the final checkpoint**.
Include home in the lane's busy time so the queue estimate does not undercount it.

### 3.5 Small consistency findings

- `s2.lane_defs` says Mac seats 2; `s2.lanes` says 1. `slots_of` prefers `s2.lanes`, so the effective seat
  count is 1, but the two should agree (or the dashboard should show both).
- A paused lane with queued lines is invisible in the queue's own estimate; the state should say **paused**
  and why/until.
- The five 9m arms (`candidate`, `candidate-bridge`, `gqa`, `ctx2048`, `v4096`) share tokeniser `569b` and the
  same data. A **voyage group / keep-box** would fit out once and run five, which is the largest duty-cycle win
  available; S2 is where the group would be scheduled.

## 4. Findings for S3 — the purser

### 4.1 `SETUP_HOURS = 0.35` is optimistic

`_setup_hours()` returns the constant 21 minutes for **every** foreign voyage. Measured: the 50m's setup was
**34.3 m** and home **7.9 m** (42 m together); the failed 9m's setup was 73 m; the trimmed 9m should be ~12–20 m.
`_foreign_minutes` is `local / speedup + setup` — it does not include home and does not vary by class.

**Change:** use the measured per-class setup and home (the timing table's medians, from `charters()`), with the
constant only as a fallback when a class has no measurement. Add home to `foreign_home_min`; it matters to the
Mac lane even when it is small on the Vast bill.

### 4.2 `EFFECTIVE_TFLOPS` is a planning derate, not a benchmark

`EFFECTIVE_TFLOPS` = 55 / 80 / 220 / 160 for 4090 / 5090 / H100 SXM / H100 PCIE. The smoke's achieved bf16
matmuls are 148.6 / 239.4 / 725.4 / 472.7 — the planner is **30–37% of the matmul**, deliberately derated for
attention, norms, the optimizer, memory stalls, small matrices, data loading and evals. It is class-level and
size-independent.

The 50m measured **110.5k tokens/s** on a 5090; if the model is ~38.8M parameters, `6·N·T` is ~26 TFLOPS
effective — well under the planner's 80. The 50m's quote (0.756 h) against 1.86 h actual is the consequence.

**Change:** calibrate effective throughput against measured **tokens/s** per preset/class (the ledger's rates
and `market.throughput`), or make `EFFECTIVE_TFLOPS` a per-class, per-size table; do not use a class constant
for a 9m and a 50m alike. Quote with an explicit fit-out + run + home, not just `local / speedup + 21 m`.

### 4.3 Host filters make H100 PCIE effectively unavailable

H100 SXM had an offer at **$2.344/h** inside the terms. H100 PCIE's only offer was **$2.004/h, unverified,
0.9405 reliability**; the terms require verified and 0.98. It provisioned in **196 s** (vs 27 s on SXM) and then
ran clean, but a voyage should not take it. The purser should not count PCIE as a free ship unless S5 changes
the terms; SXM is both faster and better $/exaFLOP.

### 4.4 The economics to use

At the smoke's achieved bf16, raw **$ per exaFLOP**: 4090 $0.69, 5090 **$0.54**, SXM $0.90, PCIE $1.18. Divide by
duty cycle: at 62% the 5090 is $0.87, the 4090 $1.11, SXM $1.45; at 25% (a single 9m today) multiply by ~4.
The **5090 is the value leader**, the **H100 SXM the wall-clock leader**, the **PCIE is dominated** by SXM.

### 4.5 Batch, do not price one at a time

Five 9m arms share the tokeniser and data. If they sail as a group, setup is paid once: the purser's per-line
`+ setup` overstates the cost and time of lines 2–5, and the "home X hours sooner" test is wrong for them.
The group is also the best way to lift a 9m's duty from ~25% to ~50–65%.

## 5. For S5 — terms and Liberty Machine records

**Terms to change or add** (names are proposals):

- `setup_hours` → measured per class (or a per-class table) instead of `SETUP_HOURS = 0.35`.
- `effective_tflops` → per class and size, calibrated to measured tokens/s.
- `fitout_minutes` → 20–30, so the charter and S2 share one number.
- `box_failures_before_pause` → 2 (the breaker).
- `home_policy` → final checkpoint only; `home_bwlimit_mbps` for the Mac lane.
- Keep `min_reliability` 0.98 and `verified` for voyages; treat H100 PCIE as unavailable unless S5 decides
  otherwise.
- `purser` stays `routing`; `foreign_expeditions` currently `table_talk`, `kipling`, `card_census`.

**Liberty Machine lints/records to add:**

- S2: a routed line pinned `mac:` with no `at sea` event (box failure); a lane paused with queued lines; a
  `lane_defs`/`s2.lanes` seat mismatch; a home pull while the Mac lane is training; a hire out with no berth.
- S3: quote versus actual for the last N hires (the 50m's 0.756 h vs 1.86 h); setup estimate versus measured;
  effective TFLOPS versus measured tokens/s.
- S3*: the ghost/orphan audit sees a dead hire only if the spend log still counts it as out; the charter's
  own recall closes it first. Record the reason and cost on that release ($0.44 here), and keep the audit's
  orphan release path for a charter that died without one.

## 6. Open decisions (Justin)

1. **Re-enable the Vast lane?** The candidate and bridge are queued, unpinned, at the top of the Vast lane.
2. **Retry the 9m candidate on which class?** 4090 (cheapest), 5090 (1.6× faster, still cheap), or H100 SXM
   (fastest, 6× the price) — with the ~0.85 GB payload and the fit-out deadline, a 4090 retry should fit out in
   minutes.
3. **Batch the five 9m arms** on one hire (the largest duty-cycle win); or keep one voyage a hire.
4. **Pre-baked image or Vast volume** for the environment/data (removes the 6-minute `uv sync` and the upload on
   repeat hires).
5. **Home policy**: final checkpoint only, `--bwlimit`, and/or hold the Mac lane during a home.
6. **Update S5's `SETUP_HOURS` / `EFFECTIVE_TFLOPS`** to the measured numbers; decide the H100 PCIE terms.

## 7. What is not proved yet

- No 9m voyage has run end to end on the new ~0.85 GB payload — the fit-out fix is unit-tested, and the 4090
  retry reached the code tar, but the data/manifest/env/train path after the trim is not yet exercised.
- The smoke test is GPU/driver/CUDA/torch, not `uv sync --group torch`, not a Thorp data pipeline, not a
  `thorp run`.
- The 5090/H100 training rates for the 9m/50m shapes are not measured; the TFLOPS above are matmul ceilings.

## 8. Handover state

- `s2.lane_defs`: Mac enabled, **Vast disabled**; `s2.lanes`: Mac `300k@v0.0.6-probe-s2` (pid 38711, since
  10:38:21), Vast empty.
- Queue: `0 vast fitouts/9m@v0.0.6-candidate`, `1 vast fitouts/9m@v0.0.6-candidate-bridge`, then the Mac
  `cmd: … probe-phase-300k`.
- Spend: week **$1.53 / $30**, all time **$3.58**, credit **$19.51**, **no ship out**.
- Evidence: `data/runs/smoke-vast.json`; the timing table at `/settings/server` → Vast; the code and tests in
  `s1_operations/charter.py`, `dash/settings.py`, `backend/tests/test_charter.py`,
  `backend/tests/test_carry_trim.py`.
