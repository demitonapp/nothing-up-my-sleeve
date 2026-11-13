# Teach the 50m all twelve console tools

*A plan for Justin to sign, 14 November 2026.*

**Update, the same morning.** Justin: "actually see if you can do it on the 9m". Step 4 is built ahead of the
sign-off: the tool lessons v3 (`lists/tools-marked-v3-acting.csv`, 30,000 lessons, the six tools' patterns written by
Claude because the teacher could not share the Mac's GPU) and the leg `fitouts/9m@v0.0.6-fleetmarks-tools3`, queued at
the top. The console does not run the six for a ship yet, and the 50m waits on the 9m's reading and on S5 #40 to #42.

Justin, 14 November: "Could we not get a thorp model to recognize all of our tools?" Yes. An outside model has to read
every tool's description in its prompt each time, which a 90M model cannot hold (Falcon-H1-Tiny-Tool-Calling-90M,
handed all twelve in 6,860 characters, remembered three and invented the rest). Our ships learn their tools in a
training leg instead, with marks of their own (`<call>`, `<result>`), so the prompt carries no descriptions at all.
This plan teaches the 50m the six console tools it does not know yet.

## Where the fleet stands

The tool legs' last readings, on held-out tool questions in wordings each ship never trained on, without steering
(the ledger, `tools/*` at each leg's last step):

| Ship | Picks the right tool | Writes the exact call | Answers plainly when no tool is wanted |
| --- | --- | --- | --- |
| 9m, `9m@v0.0.6-fleetmarks-tools2` | 76% | 19.5% | 0% |
| 21m, `21m@v0.0.6-fleetmarks-instruct` | 90% | 57.5% | 35% |
| 50m, `50m@v0.0.6-shelf-instruct` | 86% | 65% | 95% |

The 50m already does the thing at eight tools. This plan extends a leg that works; it does not start a new one.

**The gap.** The console offers outside models twelve tools (`backend/thorp/chat_tools.py`, `SCHEMAS`). Our ships
call nine (`backend/thorp/ship_tools.py`, `SET`): six of the console's, two of their own (`days_between`, `define`),
and `look_up`, added on 13 November. The six they lack:

| Tool | What it does | Does it act on the world? |
| --- | --- | --- |
| `system_status` | reads one of the Liberty Machine's five systems in detail | no, it reads |
| `browser_task_status` | reads how a browser drone task went, by its id | no, it reads |
| `browser_task` | sends the browser drone, a real Chrome, to do something on the web: open, search, click, fill a form | **yes**: it uses the real web |
| `phone_call` | opens a call on the local test line (no real number, no carrier); the drone speaks aloud through the Mac | yes, on the Mac only |
| `phone_say` | says one line as the person on the test call | yes, on the Mac only |
| `phone_end` | hangs up the test call | yes, on the Mac only |

## The plan

1. **Six new kinds of lesson, built the way the eight were.** The teacher (Qwen3.8 27B on this Mac) writes 50 question
   patterns with blanks for each new tool; code fills the blanks, writes every call and its result, and writes the
   answer from the same values (`backend/scripts/make_tool_corpus.py`, extended; the v2 files are kept). Results are
   the tool's own one-line summary, as now, so a lesson fits the 50m's window of 1,024 pieces.
   - `system_status`: "how is S3 doing?", "what does the audit say?", each with a system's summary line drawn from
     real names.
   - `browser_task`: the goal copied from the question, a page when one is named, and the drone's answer as the result.
   - `browser_task_status` and the phone tools need **chains**: a call, its result, then a second call that uses an id
     from the first (`browser_task` then `browser_task_status`; `phone_call`, `phone_say`, `phone_end`). The ship's
     format already allows several calls in a row. The field reports that tool callers under 100M parameters score
     nothing on chains, so these are the hardest lessons here and may not take at 50m.
2. **Keep the share right.** The field's recipe (`frontend/src/lib/fieldMap.ts`, `tool-leg-recipe`): a few hundred
   lessons teach which tool, thousands teach the arguments. Each of the fourteen kinds keeps about the 1,900 lessons
   each of the eight has now, so about 27,000 tool lessons, and a quarter of all lessons still want no tool, in plain
   modern talk. The no-tool share is what took the 50m to 95%.
3. **The console runs the new tools for our ships.** `ship_tools.SET` gains the six, and `ship_tools.run` calls them
   through `chat_tools` and hands back each one's summary. Steering (`backend/thorp/steer.py`) learns to write their
   calls: a goal is the person's own words, an id is the one the last result gave.
4. **Rehearse at 9m first.** The new corpus is read by a 9m leg on this Mac before any 50m sails, as the fleet's rule
   is: it shows whether the lessons are well formed and whether the new kinds take, at almost no cost.
5. **Then the 50m leg**, seeded from voyage E like `50m@v0.0.6-shelf-instruct`, on an RTX 5090 abroad, quoted by the
   gate before it sails. Its predecessor took 1,716 steps.

## How it will be judged

Read on held-out questions for every kind, as the eight are now, plus one new reading:

- **The eight must not slip:** the exact call stays within 3 points of 65%, and plain answers stay at 90% or above.
- **The six:** at the 50m, the right tool 80% or better and the exact call 50% or better on the single-call kinds
  (`system_status`, `browser_task`). The chains are read and reported, with no bar set in advance, since the field
  expects them to fail at this size.
- **New: false fires of an acting tool.** How often the ship calls `browser_task` or a phone tool when the question
  did not ask for it. The 9m called a tool on 8 of 10 plain questions; for an acting tool that would mean a real
  browser opening. The bar: under 1 in 100.

## What Justin decides

1. **Should a ship be taught to fire the acting tools at all?** My recommendation: teach all six, and have the console
   ask you before any acting call runs: a button showing what the ship wants to do, which you press or dismiss. The
   reading tools run at once, as now. The alternatives are to teach `system_status` alone (the only reading tool that
   stands on its own), or to teach all six with no confirmation.
2. **Chains in this corpus, or later?** My recommendation: in this corpus, a minority of the new lessons, read and
   reported, so the fleet learns where chains fail at 9m and 50m.
3. **Time and money.** The teacher needs this Mac's GPU for about an hour, and cannot run beside a voyage and the
   console's models. A 9m chat leg is at sea on the Mac now, so the teacher waits for it to dock. Then the 9m
   rehearsal here (minutes), then the 50m abroad (priced by the gate when it is written; the 50m legs so far cost a
   few dollars each on a hired GPU).

Nothing is queued or built until these are answered. Queue lines go through the coordinator once you have signed.
