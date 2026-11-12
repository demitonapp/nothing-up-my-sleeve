// A size page's categories of test (13 November, Justin: "do the size pages"): the landing's eight cards —
// logic, knowledge, reasoning, instruction following, coding, agent, long context and abilities — read for one
// size band, each with the tests we measure and the published tests beside them (lib/testCategories.ts). The
// back of a card is our board for this size where we have one, and Artificial Analysis's published readings
// (data/benchmarks.json) for the models of this size beside it. A category with nothing of ours says so.
//
// Replaces the per-test cards of the extra small page (StepsBoard.tsx) and the published-only cards of the
// medium page (BenchBoard.tsx); the chaining and approach boards of the other sizes are the Logic card's back
// (`logicBack`, drawn by Leaderboard.tsx, which owns their state).

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { cardCls, emptyCls } from '@/lib/ui';
import { TestCard } from '@/components/TestCard';
import { PublishedBoards } from '@/components/islands/BenchBoard';
import { TEST_ALIASES, TEST_CATEGORIES } from '@/lib/testCategories';
import { arcAi2Html, arcBandHtml, ifevalHtml, stepsHtml } from '@/scripts/views/leaderboard-steps';
import type { SizeBand } from '@/scripts/views/bands';
import { BAND } from '@/scripts/views/bands';

const cat = (k: string) => {
  const c = TEST_CATEGORIES.find((x) => x.key === k)!;
  return { ours: c.ours, published: c.published };
};
const pub = (k: string, band: SizeBand) => <PublishedBoards keys={TEST_CATEGORIES.find((x) => x.key === k)!.publishedKeys} band={band} />;

export function CategoryCards({ lb, error, band, faces, logicBack }: {
  lb: any; error: string | null; band: SizeBand;
  /** The four Faces' scorecard, as the landing draws it (every class, with the reference beside). */
  faces: { head: string; body: string } | null;
  /** The Logic card's back for the sizes that chain: the chaining board and the approach board. */
  logicBack?: ReactNode;
}) {
  const [open, setOpen] = useState<string | null>(null);
  // a card can be opened by address (?test=knowledge), as the landing's can
  useEffect(() => {
    const k = new URLSearchParams(window.location.search).get('test');
    if (k) setOpen(TEST_ALIASES[k] || k);
  }, []);
  const info = BAND(band);
  const steps = lb && band === 'xsmall' ? stepsHtml(lb, band) : null;
  const arc = lb ? arcAi2Html(lb, band) : null;
  const ifeval = lb ? ifevalHtml(lb, band) : null;
  const arcagi = lb ? arcBandHtml(lb.reasoning, band) : null;
  const st = lb?.steps || {};

  if (!lb) return <section className={cardCls(false, 'panel')}><div className={emptyCls()}>{error ? `the leaderboard could not be read: ${error}` : 'reading the leaderboard…'}</div></section>;

  return (
    <section className={cardCls(false, 'panel')} id="lbtests">
      <h2>The categories of test <span className="note">the same eight cards as the leaderboard, read for {info?.name.toLowerCase()} ({info?.range}): the tests we measure and the published tests beside them. Turn a card over for this size's board; a published reading is Artificial Analysis's, never ours</span></h2>
      <div className={`testcards${open ? ' has-open' : ''}`}>
        <TestCard
          id="logic"
          open={open}
          setOpen={setOpen}
          art="/art/test-chaining.png"
          name="Logic"
          tag="the decks and the chaining tests"
          about="Can it reason from what it is given? The logic and cause decks are ours, and the four chaining tests ask two premises for one conclusion neither gives alone. Under 1B nothing chains yet, so that size is read by the steps on the way there."
          {...cat('logic')}
          link={{ href: '/orbitals/demiton/discoveries/tests?test=chaining', label: 'Discoveries, Tests: chaining two facts' }}
          stat={steps?.lead}
        >
          {band === 'xsmall' ? (
            <>
              <h3 className="tbacktitle">The steps to chaining <span className="note">no model of this size chains two facts, so it is read by the steps on the way there, not ranked by a chaining lift that is noise here — the four cards, one hop, the chaining gain, a chaining test</span></h3>
              <div className="sqhead" dangerouslySetInnerHTML={{ __html: steps?.lead || '' }} />
              <div className="scroll">
                <table id="lbsteps" data-nosort>
                  <thead dangerouslySetInnerHTML={{ __html: steps?.head || '' }} />
                  <tbody dangerouslySetInnerHTML={{ __html: steps?.body || '' }} />
                </table>
              </div>
              <p className="note mt">A model is ranked by how many of the four steps it holds, then by the highest of them, then by its one-hop lift in steps of the noise ({st.one_hop_noise ?? 0.05}); rows equal on all three tie and share a rank (shown with =), listed biggest first. <b>The four cards</b> are the ones every model that chains at 2–4B plays; <b>one hop</b> is following one stated premise, at the Mover's mark ({st.one_hop_mark ?? 0.1}); <b>the chaining gain</b> is the logic deck's lift with both premises less the better single premise, above its noise ({st.gain_noise ?? 0.05}): the proof that a pass is chaining, not knowing or one premise; <b>a chaining test</b> is one of the four performed (lift 0.1 and two in three right). A step that was not read is not a step failed. A Nothing up my sleeve size is its best ship, its voyages averaged.</p>
            </>
          ) : logicBack}
          {pub('logic', band)}
        </TestCard>
        <TestCard
          id="knowledge"
          open={open}
          setOpen={setOpen}
          art="/art/test-arc.png"
          name="Knowledge"
          tag="AI2 ARC"
          about="AI2 ARC: grade-school science, four answers a question. ARC-Easy (2,376) is the anchor and ARC-Challenge (1,172) the floor; read zero-shot, the option's own text as the continuation, the lowest mean loss the bet — no letters, no examples, no generation."
          {...cat('knowledge')}
          link={{ href: 'https://allenai.org/data/arc', label: 'AI2 Reasoning Challenge (Clark et al., 2018)' }}
          stat={arc?.lead}
        >
          <h3 className="tbacktitle">Knowledge · AI2 ARC <span className="note">the models of this size, ranked by ARC-Easy: the anchor, with ARC-Challenge the floor beside it. A question the tokeniser cannot spell, or one whose loss comes back non-finite, is skipped and counted, never scored wrong</span></h3>
          <div className="sqhead" dangerouslySetInnerHTML={{ __html: arc?.lead || '' }} />
          <div className="scroll">
            <table id="lbarcai2" data-nosort>
              <thead dangerouslySetInnerHTML={{ __html: arc?.head || '' }} />
              <tbody dangerouslySetInnerHTML={{ __html: arc?.body || '' }} />
            </table>
          </div>
          <p className="note mt">Chance is 25%: four options a question, and the option with the lowest mean loss a piece is the model's bet. ARC-Challenge sits at or under that floor for every model trained before 2025, which is why Easy ranks the board. <b>Not comparable with published ARC numbers</b>, which are 25-shot and scored on the letter. <b>Contamination is not ruled out</b>: these are grade-school questions a pretraining corpus may well hold. A ship of ours is read by <code>thorp eval</code>; until it is, it stands below the line and is ranked on nothing.</p>
          {pub('knowledge', band)}
        </TestCard>
        <TestCard
          id="reasoning"
          open={open}
          setOpen={setOpen}
          art="/art/test-arcagi2.png"
          name="Reasoning"
          tag="ARC-AGI-2"
          about="ARC-AGI-2: the canonical intelligence ranking, pass@2 on the 120-task evaluation set, with no language or domain knowledge to memorise. Our reading is the Kipling ARC arm's, and it is a pilot."
          {...cat('reasoning')}
          link={{ href: 'https://arcprize.org/arc-agi', label: 'ARC Prize: ARC-AGI-2' }}
        >
          <h3 className="tbacktitle">Reasoning · ARC-AGI-2 at this size <span className="note">pass@2, in two columns that are two contests: a model prompted cold with a task it has never seen the like of, and a model trained on the ARC training tasks first</span></h3>
          <div className="scroll">
            <table id="lbarcband" data-nosort>
              <thead dangerouslySetInnerHTML={{ __html: arcagi?.head || '' }} />
              <tbody dangerouslySetInnerHTML={{ __html: arcagi?.body || '' }} />
            </table>
          </div>
          <p className="note mt">No model of a small size is expected to score when prompted cold; the column says whether it writes a grid at all. The way a small model competes is the second column, and nothing here has been trained on the ARC tasks yet. Our readings are pilots unless they say 120 tasks, and a pilot is never compared with a published score.</p>
          {pub('reasoning', band)}
        </TestCard>
        <TestCard
          id="instruction"
          open={open}
          setOpen={setOpen}
          art="/art/test-ifeval.png"
          name="Instruction following"
          tag="IFEval"
          about="IFEval: 541 prompts, each with orders a program can check (no commas, three paragraphs, end with this phrase), read by the authors' 25 verifiers. Prompt-level strict: every order in the prompt followed, or the prompt fails."
          {...cat('instruction')}
          link={{ href: 'https://arxiv.org/abs/2311.07911', label: 'Instruction-Following Evaluation (Zhou et al., 2023)' }}
          stat={ifeval?.lead}
        >
          <h3 className="tbacktitle">Instruction following · IFEval <span className="note">the models of this size: prompt-level strict is the board, instruction-level strict sits beside it, and how each model was asked is its own column. A rigged row stands below the line and is never quoted without the word</span></h3>
          <div className="sqhead" dangerouslySetInnerHTML={{ __html: ifeval?.lead || '' }} />
          <div className="scroll">
            <table id="lbifeval" data-nosort>
              <thead dangerouslySetInnerHTML={{ __html: ifeval?.head || '' }} />
              <tbody dangerouslySetInnerHTML={{ __html: ifeval?.body || '' }} />
            </table>
          </div>
          <p className="note mt">Read as the authors' checks read it: greedy, one sample, no verifier loop. <b>How it was asked</b> follows the checkpoint: a post-trained model through its own chat template with thinking off, a base one given the prompt bare. The cap of 512 new pieces is a cost control the benchmark does not have. <b>Rigged</b> means every official prompt was in the voyage's training turns, each with a response the checker passes: the number says it learned the checks, not that it follows orders. Not comparable with published IFEval numbers, which are for instruct checkpoints read through their templates.</p>
          {pub('instruction', band)}
        </TestCard>
        <TestCard
          id="coding"
          open={open}
          setOpen={setOpen}
          plate="Coding"
          name="Coding"
          tag="published only"
          about="Writing code that runs: a rendered artifact graded on what it looks like and does, and scientific code run against its own tests. We read no coding test ourselves yet."
          {...cat('coding')}
          link={{ href: 'https://scicode-bench.github.io/', label: 'SciCode (Tian et al., 2024)' }}
        >
          <h3 className="tbacktitle">Coding <span className="note">we measure no coding test yet; the published readings stand alone, never compared with ours</span></h3>
          {pub('coding', band)}
        </TestCard>
        <TestCard
          id="agent"
          open={open}
          setOpen={setOpen}
          plate="Agent"
          name="Agent"
          tag="drone tasks, unscored"
          about="Acting through tools until the errand is done: function calling, a banking assistant under a policy, real work judged against a human, and a shell with no hints. Our drones run browser, email and phone tasks, but nothing scores them yet."
          {...cat('agent')}
          link={{ href: 'https://gorilla.cs.berkeley.edu/leaderboard.html', label: 'Berkeley Function Calling Leaderboard' }}
        >
          <h3 className="tbacktitle">Agent <span className="note">our drone tasks are not a scored benchmark yet; the published readings stand alone, never compared with ours</span></h3>
          {pub('agent', band)}
        </TestCard>
        <TestCard
          id="long-context"
          open={open}
          setOpen={setOpen}
          plate="Long context"
          name="Long context"
          tag="published only"
          about="Finding and combining facts across a context far longer than a page: the headroom a schema dump uses. We read no long-context test ourselves yet."
          {...cat('long-context')}
          link={{ href: 'https://artificialanalysis.ai/', label: 'Artificial Analysis, AA-LCR' }}
        >
          <h3 className="tbacktitle">Long context <span className="note">we measure no long-context test yet; the published reading stands alone, never compared with ours</span></h3>
          {pub('long-context', band)}
        </TestCard>
        <TestCard
          id="abilities"
          open={open}
          setOpen={setOpen}
          art="/art/test-faces.png"
          name="Abilities"
          tag="the four Faces"
          about="The four Faces: the Nevermore's copy gain, the Counter's sentence-position R², the Scales' order gain and the Mover's one-hop lift — the four abilities, beside Qwen 3 4B, the reference chainer. A Face is earned by its ability passing, not pinned."
          {...cat('abilities')}
          link={{ href: '/orbitals/demiton/discoveries/stars', label: 'Discoveries, Stars: the four Faces' }}
        >
          <h3 className="tbacktitle">Abilities · the four Faces <span className="note">a Face is a class of ours, not a size band of the outside field: each class's best ship for that Face beside Qwen 3 4B, ✓ at the mark and ≈ within 10% of it</span></h3>
          <div className="scroll"><table id="lbtestfaces" data-nosort><thead dangerouslySetInnerHTML={{ __html: faces?.head || '' }} /><tbody dangerouslySetInnerHTML={{ __html: faces?.body || '' }} /></table></div>
        </TestCard>
      </div>
    </section>
  );
}
