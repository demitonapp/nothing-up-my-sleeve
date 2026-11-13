# Vast failures: an audit, and the five best fixes

*14 November 2026. **Fixes 2 and 3 are built** (the same day, `backend/thorp/viable/s1_operations/charter.py`; see the end); fix 1 waits on a GitHub setting. Read from S4's hire record (`thorp/viable/s4_intelligence/hires.py`, every hire since 9 November
with its phases, cost and how it ended), the ledger's runs, and the causes `DECISIONS.md` recorded as each one
happened. Nothing was changed to write this.*

## What the money bought

86 hires, **$32.72**.

| Where it went | Hires | Cost | Share |
| --- | --- | --- | --- |
| Training on hires that came home | 34 | $18.35 | 56% |
| Set-up and the trip home on those same hires | (34) | $6.60 | 20% |
| Hires that failed | 45 | $7.29 | 22% |
| Smoke tests that passed | 5 | $0.37 | 1% |
| Other (a voyage stopped by its own guard, a hire released in seconds) | 2 | $0.11 | 0% |

So about **42 cents of every dollar bought no training**. The failures also cost **13.7 hours** of lane time, and
each pair of failures in a row paused the Vast lane until someone reopened it.

## Why hires failed

| Cause | Hires | Cost | Lane hours | Fixed already? |
| --- | --- | --- | --- | --- |
| **Ours: the voyage sank at once** (a list not sent, a driver too old, macOS's hidden `._` files, an empty manifest carried, too many open files, a 50m too big for a 4090) | 12 | $1.83 | 2.8 | each cause fixed after it happened; the next new one will not be caught |
| **The box never came up** (provisioning stalled or silent, ssh refused) | 21 | $1.28 | 3.5 | bounded by a 30-minute fit-out deadline; the host lottery is untouched |
| **The cargo** (9 GB of `data/` tarred, an ARC corpus carried, a stalled rsync, a box that stopped answering mid-upload) | 6 | $1.26 | 3.0 | yes: the cargo is ~0.85 GB and transfers have timeouts |
| **The environment install on the box** (`uv sync`, slow or stalled) | 4 | $1.20 | 1.7 | watched, not removed: see fix 1 |
| **Ours: a spec too slow** (voyage E's readings every 64 steps, recalled after 93 minutes) | 1 | $1.07 | 1.9 | yes, for that spec |
| **An orphan** (a hire nobody released) | 1 | $0.65 | 0.9 | yes: the audit releases orphans |

By class, the box-side failures (box, cargo, environment) hit **30% of RTX 4090 hires (17 of 56) and 58% of RTX 5090
hires (14 of 24)**.

On the hires that came home, the median set-up was about 6.4 minutes: provision 0.8, ssh 0.1, code 0.3, data 2.0,
the manifest 1.4, the environment 1.8 (up to 14.6). The trip home took 1.9 minutes (up to 46). For **10 of the 34**,
set-up and the trip home took longer than the training itself.

Quotes: on 47 hires that sailed, the median ran at 0.96 times its quote, but **17 ran past 1.5 times**, the point
where the watch treats a voyage as overrun.

## The five best fixes, by return on effort

**1. Make the box image public. Effort: one setting on GitHub. Return: the environment phase and its failures.**
The prebuilt image (torch already installed, `backend/box/Dockerfile`) was built successfully on 12 November and
the lock has not changed since, but the package on GitHub's registry is private. An anonymous pull is refused (401),
so the charter cannot see it and every hire falls back to installing the whole environment on the box. Making
`ghcr.io/demitonapp/thorp-box` public removes that install: the 4 environment failures ($1.20, 1.7 h) and 1.8 to
14.6 minutes off every hire. The image holds only open-source packages, so publishing it fits the licence stance.
Only Justin can change the package's visibility.

**2. Rehearse the voyage on the Mac before hiring. Effort: a day. Return: the costliest failure class, and the lane's pauses.**
Every "sank at once" failure was a new bug, found on a paid box and fixed afterwards. One rehearsal would catch the
class: stage the exact cargo here and list it (no `._` files, a manifest that is not empty, every list present);
check the files the voyage will hold open against a Linux box's limit; estimate peak memory against the class's
memory, which would have caught the 50m on a 4090; time one evaluation and multiply by how often the spec reads,
which would have caught voyage E; then run one training step on the Mac from the staged cargo. The prechecks
framework (`viable/s1_operations/prechecks.py`) is where it goes. Return: 12 hires, $1.83, 2.8 lane hours so far, and
every breaker pause they caused.

**3. Fail fast on a dead box, and remember bad hosts. Effort: hours. Return: the box-lottery losses, in time more than money.**
A box that came up did so in under a minute at the median (provision 0.8, ssh 0.1; the slowest 6.2). Yet a dead one
holds the lane until the 30-minute fit-out deadline. Three changes: release a hire whose provisioning and ssh have
not answered in 8 minutes; keep a list of hosts that failed and never hire them again; and on the RTX 5090, where
58% failed, hire two offers at once and release the slower, which costs cents. Return: most of 21 hires' $1.28 and
3.5 lane hours, and far fewer breaker trips.

**4. Calibrate quotes from what voyages measured. Effort: hours. Return: budget the gate can actually commit.**
17 of 47 voyages ran past 1.5 times their quote, and the budget counts every hire at 1.5 times its quote, so a quote
that is too low risks a kill and one that is too high holds back money that could sail. S4 already measures each
class's set-up and each voyage's seconds at sea (`hires.train_seconds`). Quote each line from that rate, per class
and size, plus the measured cost of its readings, which voyage E showed can double a voyage. Return: fewer overruns,
and more of the week's $30 committed to lines that would otherwise wait.

**5. Keep a box for back-to-back voyages. Effort: days. Return: the largest share of money, once the others are in.**
Set-up and the trip home are 20% of all spend ($6.60), and every new hire is a fresh draw in the box lottery. The
fleet's legs are short and come in families (the 9m and 21m legs trained 2 to 25 minutes each, after 5 to 26 minutes
of set-up). Holding a box after one voyage and sailing the next queued line for that class on it, before releasing,
saves the set-up, the environment and the lottery for every voyage after the first. It is listed as not built since
12 November ("keep-box"). It comes fifth because it is the most work and fixes 1 to 3 make each hire cheaper first.

## What is left out

- Sending the smallest ships abroad: already ruled out (`foreign_min_preset` 9m; a 4090 is slower than this Mac at
  the 300k and 1m).
- The cargo: already trimmed from 9.28 GB to about 0.85 GB, with timeouts on every transfer.
- The trip home: a 46-minute checkpoint pull was fixed by resumable pulls on 13 November.

## Built, 14 November

**Fix 2, the rehearsal**, runs in `sail` after the quote and before the gate and the hire; a refusal costs nothing.
It checks the spec's lists are files, lists the code cargo as the box would get it (`._` files, every list
present), checks every book is registered and carried with a text or a shard, and checks the books held open.
It compares the shape's measured peak memory with each class, hiring the cheapest class that fits. And it prices
both kinds of reading from their evaluators' measured seconds: refused when readings alone exceed the whole quote,
noted past half. On real specs: the 9m tools3 leg and the 50m legs pass; voyage E as first written is refused at
123% of its quote; a deep 50m with no class named is moved from the 4090 to the 5090.

**Fix 3, failing fast**: 8 minutes for a box to come up on the stock image (15 on the prebuilt one); a week's ban
on any host whose box failed before training (not a recall); up to 3 rehires on a class failing 40% or more; and on
such a class, two offers on different machines hired at once, the first running kept, the other released at once
and left out of the failure measures.

A correction from building it: the two hires first put down to the empty manifest failed with "server not
responding", so they are counted under the cargo above.

