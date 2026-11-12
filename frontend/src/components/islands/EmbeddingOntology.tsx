// The embeddings view of Masaq' Reach (12 November, Justin: "add an embedding tab here
// /orbitals/masaq with the ontology of embeddings underneath"). Two families that must not be confused:
// the embeddings inside a ship (its own, period-pure, trained on our books) and the embedding models
// outside it (modern instruments that curate the library and never feed a period-pure score). The
// candidates and their numbers are the 12 November research (reports/Embedding models for Thorp.md),
// written here by hand: a reading, not a measurement, until the Gutenberg pair test has run.

import { artSrc } from '@/scripts/views/helpers';
import { cardCls, pillCls } from '@/lib/ui';

type Lane = 'mac' | 'vast' | 'hosted' | 'ship';
type Status = 'start here' | 'challenger' | 'step up' | 'baseline' | 'later' | 'in use' | 'watch';

interface Model {
  key: string;
  name: string;
  house: string;
  /** the house's page in the Reach, when it has one */
  href?: string;
  params: string;
  dims: string;
  context: string;
  licence: string;
  lane: Lane;
  status: Status;
  jobs: string[];
  note: string;
}

interface Node {
  key: string;
  name: string;
  what: string;
  /** the rule that governs this branch, said once */
  rule?: string;
  models?: Model[];
  children?: Node[];
}

const LANE: Record<Lane, [string, string]> = {
  ship: ['inside the ship', 'green'],
  mac: ['Mac', 'accent'],
  vast: ['Vast', 'blue'],
  hosted: ['hosted', ''],
};

const STATUS_TONE: Partial<Record<Status, string>> = { 'start here': 'green', 'in use': 'green', challenger: 'accent' };

const ONTOLOGY: Node[] = [
  {
    key: 'inside',
    name: 'Inside a ship',
    what: "The ship's own vectors, learned from our books alone. They are part of the kernel: the thing Thorp is building.",
    rule: 'Period-pure. Nothing from a modern model is copied into them: no weights, no geometry, no distillation.',
    models: [
      {
        key: 'token', name: 'Token embeddings', house: 'every ship', params: 'vocab × width', dims: 'the ship’s width',
        context: '—', licence: 'ours', lane: 'ship', status: 'in use', jobs: ['the input layer', 'the tied output head', 'the analogies trick'],
        note: 'One row per piece of the Ogden tokeniser, tied to the output (models/gpt_mlx.py). Grown, not borrowed, when a ship grows.',
      },
      {
        key: 'position', name: 'Position', house: 'every ship', params: 'learned or none', dims: 'the ship’s width',
        context: 'the window', licence: 'ours', lane: 'ship', status: 'in use', jobs: ['where a piece sits'],
        note: 'Learned positions or rotary (RoPE, no parameters). A charter choice, not an outside model.',
      },
      {
        key: 'stream', name: 'Hidden states', house: 'every ship', params: '—', dims: 'per layer',
        context: '—', licence: 'ours', lane: 'ship', status: 'in use', jobs: ['persona vectors', 'soundings', 'what happens inside a thinking span'],
        note: 'The residual stream read layer by layer. The right instrument for control tokens: read the ship, not an outside embedder.',
      },
    ],
  },
  {
    key: 'outside',
    name: 'Outside instruments',
    what: 'Embedding models trained on the modern web. They map a passage to one vector, so that passages that mean alike sit close.',
    rule: 'Curation only: distinctness, topic spread, duplicates and retellings, the search box. Never inside a ship, never a period-pure score. Embed each book once and reuse it for every class; the lane follows the library’s volume, not the ship’s size.',
    children: [
      {
        key: 'dense-small',
        name: 'Text, small',
        what: 'One dense vector a passage, small enough to run on the M6 between voyages.',
        models: [
          {
            key: 'embeddinggemma-2', name: 'EmbeddingGemma 2', house: 'Google', href: '/orbitals/masaq/us/google',
            params: '270M text (740M with images)', dims: '768 → 512 / 256 / 128', context: '8K', licence: 'Apache 2.0, ungated',
            lane: 'mac', status: 'challenger', jobs: ['distinctness', 'topic spread'],
            note: 'Near-lossless at 256 dims (68.46 → 67.78). Never float16: it returns NaN or silently bad vectors, and the MLX converter defaults to it. Five weeks old.',
          },
          {
            key: 'jina-v5-small', name: 'jina-embeddings-v5-text-small', house: 'Jina AI',
            params: '677M', dims: 'Matryoshka', context: '32K', licence: 'CC BY-NC 4.0',
            lane: 'mac', status: 'challenger', jobs: ['retellings', 'search box', 'distinctness'],
            note: 'English MTEB v2 71.7, the best of the small ones, with official MLX and GGUF builds. Non-commercial: fine to use, never vendored into the open repo.',
          },
          {
            key: 'qwen3-0.6b', name: 'Qwen3-Embedding-0.6B', house: 'Alibaba', href: '/orbitals/masaq/cn/alibaba',
            params: '0.6B', dims: '1,024 → any 32–1,024', context: '32K', licence: 'Apache 2.0',
            lane: 'mac', status: 'start here', jobs: ['search box', 'retellings', 'distinctness'],
            note: 'Every step confirmed on the Mac (mlx-embeddings, Ollama, GGUF). Left padding, last-token pooling, an instruction on queries only; get one wrong and it degrades without an error.',
          },
          {
            key: 'harrier-0.6b', name: 'harrier-oss-v1-0.6b', house: 'Microsoft', href: '/orbitals/masaq/us/microsoft',
            params: '0.6B', dims: '1,024', context: '32K', licence: 'MIT',
            lane: 'mac', status: 'watch', jobs: ['the pair test'],
            note: 'Multilingual MTEB v2 69.0, but no English score, no MLX or GGUF build found. Run it through PyTorch MPS for the test only.',
          },
        ],
      },
      {
        key: 'dense-large',
        name: 'Text, large',
        what: 'The same kind of vector at higher quality, too slow for the Mac beside training: a rented GPU for a full pass.',
        models: [
          {
            key: 'qwen3-4b', name: 'Qwen3-Embedding-4B', house: 'Alibaba', href: '/orbitals/masaq/cn/alibaba',
            params: '4B', dims: '2,560, Matryoshka', context: '32K', licence: 'Apache 2.0',
            lane: 'vast', status: 'step up', jobs: ['retellings', 'search box'],
            note: 'About seven retrieval points over the 0.6B (68.46 against 61.83). About 15 hours of Mac GPU a billion tokens; vLLM on an H100 instead.',
          },
          {
            key: 'qwen3-8b', name: 'Qwen3-Embedding-8B', house: 'Alibaba', href: '/orbitals/masaq/cn/alibaba',
            params: '8B', dims: '4,096, Matryoshka', context: '32K', licence: 'Apache 2.0',
            lane: 'vast', status: 'later', jobs: ['the strongest English reading'],
            note: 'English MTEB v2 75.2, retrieval 69.4. Clustering barely moves (54 to 59 across the strong models), so it pays for search, not for spread.',
          },
          {
            key: 'nemotron-8b', name: 'llama-embed-nemotron-8b', house: 'NVIDIA', href: '/orbitals/masaq/us/nvidia',
            params: '8B', dims: '4,096', context: '32K', licence: 'non-commercial',
            lane: 'vast', status: 'later', jobs: ['a second large reading'],
            note: 'Among the multilingual leaders. Allowed now that Thorp is non-commercial; Vast only.',
          },
        ],
      },
      {
        key: 'reasoning',
        name: 'Reasoning retrievers',
        what: 'Tuned to find the passage that supports an inference, not the passage on the same topic. General leaders collapse here (BRIGHT: 59.0 on MTEB, 18.3 on BRIGHT).',
        models: [
          {
            key: 'reasonembed', name: 'ReasonEmbed-Qwen3-8B', house: 'academic (ACL 2026)',
            params: '8B', dims: '4,096', context: '32K', licence: 'see the card',
            lane: 'vast', status: 'later', jobs: ['the Origin test', 'chaining evidence'],
            note: 'BRIGHT nDCG@10 38.1, reported as a record. For "which earlier book makes this idea less surprising".',
          },
          {
            key: 'rtriever', name: 'RTriever-4B', house: 'academic (2026)',
            params: '4B (LoRA on Qwen3-4B)', dims: '2,560', context: '32K', licence: 'see the card',
            lane: 'vast', status: 'later', jobs: ['chaining evidence'],
            note: 'A LoRA on Qwen3-Embedding-4B for BRIGHT-Pro; a smaller reasoning reader.',
          },
        ],
      },
      {
        key: 'sparse',
        name: 'Sparse and multi-vector',
        what: 'A weight a word, or a vector a piece, beside the single dense vector: closer to exact wording.',
        models: [
          {
            key: 'bge-m3', name: 'BGE-M3', house: 'BAAI',
            params: '568M', dims: '1,024 dense + sparse + multi-vector', context: '8K', licence: 'MIT',
            lane: 'mac', status: 'baseline', jobs: ['the pair test baseline'],
            note: 'The best-documented baseline (about 78 docs a second on an M4 Max). Weaker clustering (MMTEB 40.9 against Qwen3-0.6B’s 52.3).',
          },
        ],
      },
      {
        key: 'contextual',
        name: 'Contextual chunks',
        what: 'Each chunk is embedded with the rest of its book in view, so a chapter vector knows which book it is in.',
        models: [
          {
            key: 'voyage-context-4', name: 'voyage-context-4', house: 'Voyage AI',
            params: 'hosted', dims: '1,024 (256 / 512 / 2,048)', context: '32K a chunk, 120K a request', licence: 'commercial API',
            lane: 'hosted', status: 'watch', jobs: ['per-book vectors', 'the pair test comparator'],
            note: 'About $80 a billion tokens on batch. Shares a space with the open voyage-4-nano (a vendor claim). Gemini Embedding 2 silently truncates at 8K, so it does not fit books.',
          },
        ],
      },
      {
        key: 'multimodal',
        name: 'Multimodal',
        what: 'Text, images, audio and video in one space. Not needed until the Library’s images shelf has something on it.',
        rule: 'Step up inside a family, so the text vectors already made stay comparable.',
        models: [
          {
            key: 'embeddinggemma-2-full', name: 'EmbeddingGemma 2 (full)', house: 'Google', href: '/orbitals/masaq/us/google',
            params: '740M', dims: '768', context: '8K text', licence: 'Apache 2.0',
            lane: 'mac', status: 'later', jobs: ['scans', 'illustrations'],
            note: 'Claimed to share one space with the 270M text path: embed text now, add images later without re-embedding. Check with a few cosine pairs first.',
          },
          {
            key: 'qwen3-vl-2b', name: 'Qwen3-VL-Embedding-2B', house: 'Alibaba', href: '/orbitals/masaq/cn/alibaba',
            params: '2B', dims: '2,048, Matryoshka', context: '32K', licence: 'Apache 2.0',
            lane: 'mac', status: 'later', jobs: ['scans', 'illustrations'],
            note: 'January 2026, instruction-aware. A separate model from the text-only Qwen3: switching means re-embedding.',
          },
          {
            key: 'qwen3-vl-8b', name: 'Qwen3-VL-Embedding-8B', house: 'Alibaba', href: '/orbitals/masaq/cn/alibaba',
            params: '8B', dims: '4,096, Matryoshka', context: '32K', licence: 'Apache 2.0',
            lane: 'vast', status: 'later', jobs: ['scans at scale'],
            note: 'MMEB-V2 77.8 (the report’s own figure).',
          },
          {
            key: 'jina-v5-omni', name: 'jina-embeddings-v5-omni', house: 'Jina AI',
            params: 'small and nano', dims: 'Matryoshka', context: '32K', licence: 'CC BY-NC 4.0',
            lane: 'mac', status: 'later', jobs: ['scans', 'illustrations'],
            note: 'The v5 text space extended to images, audio and video (May 2026).',
          },
        ],
      },
    ],
  },
  {
    key: 'neighbours',
    name: 'Not embeddings, kept beside them',
    what: 'Exact-text instruments. They stay: shingles catch copied text, embeddings catch the same story in other words.',
    models: [
      {
        key: 'shingles', name: '5-word shingles', house: 'Thorp',
        params: '—', dims: 'a set of hashes', context: 'the whole book', licence: 'ours',
        lane: 'mac', status: 'in use', jobs: ['held-out books at intake'],
        note: '35% of the shorter text’s shingles shared flags a deck book (acquisition.py).',
      },
      {
        key: 'bm25', name: 'BM25', house: 'classic',
        params: '—', dims: 'a weight a word', context: '—', licence: 'open',
        lane: 'mac', status: 'baseline', jobs: ['the pair test baseline'],
        note: 'The baseline a 19th-century British Library retrieval benchmark treats as the one to beat.',
      },
    ],
  },
];

const count = (n: Node): number => (n.models?.length || 0) + (n.children || []).reduce((a, c) => a + count(c), 0);

function ModelCard({ m }: { m: Model }) {
  const [lane, tone] = LANE[m.lane];
  return (
    <div className={cardCls(false, 'card embcard')} id={`emb-${m.key}`}>
      <div className="labhead">
        <span className="labname">{m.name}</span>
        <span className={pillCls(tone)}>{lane}</span>
      </div>
      <div className="labmakes">
        {m.href ? <a href={m.href}>{m.house}</a> : m.house} <span className="s">· {m.params}</span>
      </div>
      <dl className="embfacts">
        <dt>dims</dt><dd>{m.dims}</dd>
        <dt>context</dt><dd>{m.context}</dd>
        <dt>licence</dt><dd>{m.licence}</dd>
      </dl>
      <div className="lababout">{m.note}</div>
      <div className="labfoot">
        <span>{m.jobs.join(' · ')}</span>
        <span className={pillCls(STATUS_TONE[m.status] || '')}>{m.status}</span>
      </div>
    </div>
  );
}

function Branch({ n, depth }: { n: Node; depth: number }) {
  const Head = depth === 0 ? 'h2' : 'h3';
  return (
    <section className={`embnode d${depth}`} id={`emb-${n.key}`}>
      <Head className={depth === 0 ? 'band labgroup' : 'embsub'}>
        {n.name} <span className="q">{count(n)} · {n.what}</span>
      </Head>
      {n.rule ? <p className="note embrule"><b>rule</b> {n.rule}</p> : null}
      {n.models?.length ? <div className="labgrid">{n.models.map((m) => <ModelCard key={m.key} m={m} />)}</div> : null}
      {(n.children || []).map((c) => <Branch key={c.key} n={c} depth={depth + 1} />)}
    </section>
  );
}

/** One category as a card: its plate (generate_art.py EMBEDDINGS, key `emb-<node key>`), name, size and
 *  what it is, and a door to its branch below. The plate is dropped when the file is missing. */
function CategoryCard({ n }: { n: Node }) {
  const kids = n.children?.length ? `${n.children.length} kinds · ` : '';
  return (
    <a className={cardCls(true, 'card labcard embcat')} href={`#emb-${n.key}`}>
      <img className="cardart ship" src={artSrc(`emb-${n.key}`)} alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} />
      <div className="labhead">
        <span className="labname">{n.name}</span>
        <span className="s">{kids}{count(n)}</span>
      </div>
      <div className="lababout">{n.what}</div>
      <div className="labfoot">
        <span>{(n.models || []).map((m) => m.name).slice(0, 3).join(' · ') || (n.children || []).map((c) => c.name).join(' · ')}</span>
        <span>below →</span>
      </div>
    </a>
  );
}

/** The ontology at the top as cards: the three major families, then the kinds of outside instrument. */
function Categories() {
  const outside = ONTOLOGY.find((n) => n.key === 'outside');
  return (
    <section className="embcats">
      <h2 className="band labgroup">The ontology <span className="q">the ship&rsquo;s own, the outside instruments, and the exact-text neighbours kept beside them</span></h2>
      <div className="labgrid">{ONTOLOGY.map((n) => <CategoryCard key={n.key} n={n} />)}</div>
      {outside?.children?.length ? (
        <>
          <h3 className="embsub">The kinds of outside instrument <span className="q">{outside.children.length} kinds, {count(outside)} models</span></h3>
          <div className="labgrid">{outside.children.map((c) => <CategoryCard key={c.key} n={c} />)}</div>
        </>
      ) : null}
    </section>
  );
}

export default function EmbeddingOntology() {
  return (
    <>
      <p className="note labnote">
        An embedding is a passage, a piece or an image written as a list of numbers, placed so that things
        that mean alike sit close. Thorp has two kinds and keeps them apart: the ship&rsquo;s own, which are the
        kernel, and outside models, which only help curate the library. The lanes are where each runs: the
        Mac between voyages, Vast for a full pass, or a hosted API. None has yet been tested on pre-1930
        English; the Gutenberg pair test decides.{' '}
        <span className="s">Read 12 November 2026 from model cards and one leaderboard snapshot (14 October).</span>
      </p>
      <Categories />
      {ONTOLOGY.map((n) => <Branch key={n.key} n={n} depth={0} />)}
    </>
  );
}
