// Persona vectors, a page of Demiton's discoveries (13 November, Justin: "where would persona vectors fit into
// discoveries?", then "a page in Discoveries"): a representation (a character trait is a direction in the hidden
// state) of internals, placed beside Traits on the two axes. Each model with a reading gets its panel, drawn by the
// same renderer the Stars tab used (scripts/views/discoveries.ts personasHtml) from /api/personas
// (thorp.persona_vectors, s4.persona_master). Qwen3 4B is the only model read so far.

import { cardCls, crumbCls, emptyCls } from '@/lib/ui';
import { useApi } from '@/lib/useApi';
import { personasHtml } from '@/scripts/views/discoveries';
import { DEMITON_DISCOVERIES as DB, QWEN4B_PAGE } from '@/lib/discoveryPaths';

const READ: { model: string; label: string; page: string }[] = [
  { model: 'mlx-community/Qwen3-4B-4bit', label: 'Qwen3 4B', page: QWEN4B_PAGE },
];

function ModelPersonas({ model, label, page }: { model: string; label: string; page: string }) {
  const p = useApi<any>(`/api/personas?model=${encodeURIComponent(model)}`, 300000);
  return (
    <section className={cardCls(false, 'panel')} id={model}>
      <h2>{label} <span className="note">the residual-stream directions for six character traits, read by contrastive system prompts (thorp.persona_vectors): each direction's norm, its projection on a plain prompt, and how far the traits share a direction. The model's own page: <a href={page}>{label}</a></span></h2>
      {p.error ? <div className={emptyCls()}>the persona readings could not be read: {p.error}</div>
        : !p.data ? <div className={emptyCls()}>reading the persona directions…</div>
        : p.data.found === false ? <div className={emptyCls()}>no persona reading for {label} yet</div>
        : <div dangerouslySetInnerHTML={{ __html: personasHtml(p.data) }} />}
    </section>
  );
}

export default function PersonaVectors() {
  return (
    <>
      <h1>
        <a className={crumbCls('back')} href={DB}>← discoveries</a>{' '}
        Persona vectors{' '}
        <span className="q">a character trait (sycophancy, malice, and four more) is a direction in a model's hidden state that can be read, monitored and steered (Chen et al. 2025). It sits with <a href={`${DB}/kind-of-claim/representations`}>the representations</a>, beside <a href={`${DB}/traits`}>our ships' traits</a></span>
      </h1>
      {READ.map((m) => <ModelPersonas key={m.model} {...m} />)}
    </>
  );
}
