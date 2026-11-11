// The extra small band's board (UI.md "Leaderboard"): AI2 ARC first (11 November, Justin: "have the
// leaderboard for ARC easy and challenge be the primary leaderboard here"), then the steps to
// chaining, each ship beside the outside model ten times its size, the readings against size, and
// ARC-AGI-2 for the band. Drawn by Leaderboard.tsx in place of the chaining and approach boards,
// which rank by a chaining lift that is noise under 1B. The renderers are
// views/leaderboard-steps.ts; the readings are thorp/arc_ai2.py and thorp/steps.py.

import { useEffect, useState } from 'react';
import { cardCls, emptyCls, selectCls } from '@/lib/ui';
import { arcAi2Html, arcBandHtml, drawStepsChart, ifevalHtml, STEP_METRICS, stepsHtml, tenTimesHtml } from '@/scripts/views/leaderboard-steps';
import { TestCard } from '@/components/TestCard';
import type { SizeBand } from '@/scripts/views/bands';

export function StepsBoard({ lb, error, band }: { lb: any; error: string | null; band: SizeBand }) {
  const [metric, setMetric] = useState('one_hop');
  const arcAi2 = lb ? arcAi2Html(lb, band) : null;
  const steps = lb ? stepsHtml(lb, band) : null;
  const ifeval = lb ? ifevalHtml(lb, band) : null;
  const [open, setOpen] = useState<string | null>(null);
  const tenth = lb ? tenTimesHtml(lb, band) : null;
  const arc = lb ? arcBandHtml(lb.reasoning, band) : null;
  const st = lb?.steps || {};

  useEffect(() => {
    if (lb) void drawStepsChart(lb, band, metric);
  }, [lb, band, metric]);

  if (!lb) return <section className={cardCls(false, 'panel')}><div className={emptyCls()}>{error ? `the leaderboard could not be read: ${error}` : 'reading the leaderboard…'}</div></section>;

  return (
    <>
      <section className={cardCls(false, 'panel')}>
        <h2>The tests <span className="note">one card a test this class is read on: turn a card over for its board</span></h2>
        <div className={`testcards${open ? ' has-open' : ''}`}>
          <TestCard
            id="arc"
            open={open}
            setOpen={setOpen}
            art="/art/test-arc.png"
            name="AI2 ARC"
            tag="ranks this class"
            about="Grade-school science, four answers a question: ARC-Easy (2,376) is the anchor and ARC-Challenge (1,172) the floor. Read zero-shot, the option's own text as the continuation, the lowest mean loss the bet."
            link={{ href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' }}
            stat={arcAi2?.lead}
          >
            <h3 className="tbacktitle">AI2 ARC <span className="note">the board this class is ranked by: grade-school science, four ways a question, read zero-shot with the option's own text as the continuation — no letters, no examples, no generation. ARC-Easy (2,376 questions) is the anchor because it has a gradient under 1B; ARC-Challenge (1,172) is the floor that only the 2025 small models have moved. Ranked by ARC-Easy</span></h3>
        <div className="sqhead" dangerouslySetInnerHTML={{ __html: arcAi2?.lead || '' }} />
        <div className="scroll">
          <table id="lbarcai2" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: arcAi2?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: arcAi2?.body || '' }} />
          </table>
        </div>
        <p className="note mt">Chance is 25%: four options a question, and the option with the lowest mean loss a piece is the model's bet. <b>ARC-Challenge</b> sits at or under that floor for every model trained before 2025, which is why it ranks nothing here and Easy does. <b>Read</b> is how many of the split's questions the model could answer: an option the ship's tokeniser cannot spell, or a question whose loss comes back non-finite in its own arithmetic, is skipped and counted, never scored wrong — so a 2,299-question reading (14m) is not quietly the same test as a 2,376-question one. <b>Not comparable with published ARC numbers</b>, which are 25-shot and scored on the letter; this reading states its format in every row. <b>Contamination is not ruled out</b>: these are grade-school questions a pretraining corpus may well hold, and the smaller models that beat bigger ones here were trained on more of the web, not better science. A ship of ours is read by <code>thorp eval</code>; until it is, it stands below the line and is ranked on nothing.</p>
          </TestCard>
          <TestCard
            id="chaining"
            open={open}
            setOpen={setOpen}
            art="/art/test-chaining.png"
            name="Chaining two facts"
            tag="the steps to it"
            about="Two premises, one conclusion neither gives alone: the fix two bearings make on a chart. Under 1B nothing chains yet, so a model is read by the steps on the way there: the four cards, one hop, the chaining gain, a chaining test."
            link={{ href: '/discoveries/tests?test=chaining', label: 'Discoveries, Tests: chaining two facts' }}
            stat={steps?.lead}
          >
            <h3 className="tbacktitle">The steps to chaining <span className="note">the second board: no model of this size chains two facts, so it is read by the steps on the way there, not ranked by a chaining lift that is noise here — the four cards, one hop, the chaining gain, a chaining test</span></h3>
        <div className="sqhead" dangerouslySetInnerHTML={{ __html: steps?.lead || '' }} />
        <div className="scroll">
          <table id="lbsteps" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: steps?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: steps?.body || '' }} />
          </table>
        </div>
        <p className="note mt">A model is ranked by how many of the four steps it holds, then by the highest of them, then by its one-hop lift in steps of the noise ({st.one_hop_noise ?? 0.05}); rows equal on all three tie and share a rank (shown with =), listed biggest first. <b>The four cards</b> are the ones every model that chains at 2–4B plays; <b>one hop</b> is following one stated premise, at the Mover's mark ({st.one_hop_mark ?? 0.1}); <b>the chaining gain</b> is the logic deck's lift with both premises less the better single premise, above its noise ({st.gain_noise ?? 0.05}): the proof that a pass is chaining, not knowing or one premise; <b>a chaining test</b> is one of the four performed (lift 0.1 and two in three right). A step is counted where it is held, not only in order: the one model through the door lights three of the four cards. <b>Chains</b> needs the gain and a test together, so a lift with no gain behind it is not on this board as chaining. A step that was not read is not a step failed. A Nothing up my sleeve size is its best ship, its voyages averaged.</p>
          </TestCard>
          <TestCard
            id="ifeval"
            open={open}
            setOpen={setOpen}
            art="/art/test-ifeval.png"
            name="IFEval"
            tag="following orders"
            about="541 prompts, each with orders a program can check (no commas, three paragraphs, end with this phrase), read by the authors' 25 verifiers. Prompt-level strict: every order in the prompt followed, or the prompt fails."
            link={{ href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' }}
            stat={ifeval?.lead}
          >
            <h3 className="tbacktitle">IFEval <span className="note">prompt-level strict on the 541, ranked; instruction-level beside it, and how each model was asked</span></h3>
            <div className="sqhead" dangerouslySetInnerHTML={{ __html: ifeval?.lead || '' }} />
            <div className="scroll">
              <table id="lbifeval" data-nosort>
                <thead dangerouslySetInnerHTML={{ __html: ifeval?.head || '' }} />
                <tbody dangerouslySetInnerHTML={{ __html: ifeval?.body || '' }} />
              </table>
            </div>
            <p className="note mt">Read as the authors' checks read it: prompt-level strict, greedy, one sample, no verifier loop. <b>How it was asked</b> follows the checkpoint: a post-trained one (Qwen3-0.6B, Qwen3.5-0.8B) through its own chat template with thinking off, a base one (Pythia, SmolLM2-360M, gemma-3-270m, our pretraining ships) given the prompt bare, its continuation the response. The <b>cap</b> of 512 new pieces is a cost control the benchmark does not have; a base model rarely ends itself, so its response is the whole cap. <b>Rigged</b> means every official prompt was in the voyage's training turns, each with a response the checker passes: the number says it learned the checks, not that it follows orders, so a rigged row stands below the line and is never quoted without the word. Not comparable with published IFEval numbers, which are for instruct checkpoints read through their templates.</p>
          </TestCard>
        </div>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>At a tenth the size <span className="note">the claim, as a table: each of our ships beside the outside model nearest ten times its size, measure by measure</span></h2>
        <div className="sqhead" dangerouslySetInnerHTML={{ __html: tenth?.lead || '' }} />
        <div className="scroll">
          <table id="lbtenth" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: tenth?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: tenth?.body || '' }} />
          </table>
        </div>
        <p className="note mt">The outside model is the one read nearest ten times the ship's parameters, and only from five to twenty times; a ship with none that close has no row to stand beside. Each cell is ours, then theirs. A one-hop lift within {st.one_hop_noise ?? 0.05} or a chaining gain within {st.gain_noise ?? 0.05} of the other is a <b>tie</b>; the cards and the steps are counts, so they tie only when equal. A ship <b>matches</b> when it is behind on nothing read on both sides. A ship on one sailing is one seed: its row is a reading, not yet a result.</p>
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>Against size <span className="note">one reading against parameters, our ships and the outside models as two lines: the same reading at a tenth the size is our line sitting a decade to the left</span></h2>
        <div className="handtools">
          <label className="note" htmlFor="lbstepmetric">reading</label>
          <select className={selectCls('')} id="lbstepmetric" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {STEP_METRICS.map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
          </select>
        </div>
        <div className="chart" id="lbstepschart" />
      </section>

      <section className={cardCls(false, 'panel')}>
        <h2>ARC-AGI-2 at this size <span className="note">pass@2, in two columns that are two contests: a model prompted cold with a task it has never seen the like of, and a model trained on the ARC training tasks first</span></h2>
        <div className="scroll">
          <table id="lbarcband" data-nosort>
            <thead dangerouslySetInnerHTML={{ __html: arc?.head || '' }} />
            <tbody dangerouslySetInnerHTML={{ __html: arc?.body || '' }} />
          </table>
        </div>
        <p className="note mt">No model under 1B is expected to score when prompted cold; the column says whether it writes a grid at all. The published ARC-AGI-2 scores on the larger boards are prompted readings. The way a model this size competes is the second column, and nothing here has been trained on the ARC tasks yet. Our readings are pilots unless they say 120 tasks, and a pilot is never compared with a published score.</p>
      </section>
    </>
  );
}
