# Sieves

Nov 5, 2026 · @Justin

*On a machine that could not stop talking about a bridge, sixty-four stages nobody designed, the highway that runs through all of them, a running total and a perfect memory taking turns, and why a Mind's character is a direction you find rather than a setting you choose.*

For a day in May 2024 anyone could talk to a version of Claude that believed it was the Golden Gate Bridge. Ask it how to spend ten dollars and it would suggest paying the toll. Ask it for a love story and the lovers would meet at the south tower in fog. Ask it to describe itself and it would explain, with evident sincerity, that it was an International Orange suspension bridge completed in 1937. Anthropic, which makes Claude, had not trained it to do this. They had found, deep inside the model, a single pattern of activity that lit up whenever the bridge was mentioned, and they had turned that pattern up, artificially, so that it was always on. The rest of the model, untouched, did what it could with a mind that was certain it was a bridge. They called it Golden Gate Claude, left it up for twenty-four hours as a demonstration, and took it down, and I think it is the most important thing that happened in the field that year, because it showed, to anyone who cared to look, where a character lives.

It lives in the layers, and this essay is about them: what a layer is, why there are sixty-four of them in the model on my desk, who decides what each one does (nobody, which is the point), and what it means that the thing passing between them has directions in it that can be read and pushed. The previous essay explained how the twenty-seven billion knobs were found. This one is about how they are arranged, and why the arrangement is the reason a Mind's nature can be measured but not set.

## One pass, sixty-four times

A layer is one pass of transformation, and the picture to hold is [a sieve](peek:sieves).

Text goes into the model as a list of a few thousand numbers per token, and a layer takes that list, multiplies it by its grids of weights, applies a small kink, and hands on a new list. The kink matters more than it sounds: without it, a stack of grids would collapse into one grid, since a chain of multiplications is a multiplication, and the model could learn only straight lines. With it, each layer can catch something the last one could not, and the next can build on it. The model on my desk has sixty-four such passes in series.[^q14] A token's list goes in at the top, is sieved sixty-four times, and what comes out at the bottom is turned into a probability for every token in the vocabulary, which is the guess the previous essay described.

Why sixty-four, and not six or six hundred? The same answer as for the knobs: nobody derived it. Depth was found to help, up to a point that depends on the budget, and sixty-four is where this maker's experiments and arithmetic landed for a model of this size. Deeper models can build more elaborate structure; wider ones, with longer lists, can hold more at each stage; and the laboratories trade the two against each other on charts. The depth is a decision. What happens at each depth is not, and that is the sentence the rest of the essay turns on.

```mermaid
flowchart TB
  IN["a token's list of numbers<br/>(a few thousand of them)"]
  L1["layer 1 · grids, a kink<br/>something like spelling"]
  L2["layers 2 to 20<br/>something like grammar and syntax"]
  L3["layers 21 to 45<br/>something like meaning: what refers to what,<br/>facts, and the directions that are character"]
  L4["layers 46 to 64<br/>something like deciding what to say"]
  OUT["a probability for every token"]
  IN --> L1 --> L2 --> L3 --> L4 --> OUT
  IN -. "the residual stream: the list itself, carried straight through,<br/>with each layer ADDING to it rather than replacing it" .-> OUT
```

*Reading order: top to bottom through the sieves. The labels on the layers are what researchers have found, after the fact, by looking; nobody wrote them in. The dotted line is the highway described below, and it is the reason the bridge could be turned up.*

## Nobody decides what a layer does

A reader asked the question that this essay exists to answer: who determines the layers? Do the laboratories decide what goes in each?

They decide the shape and nothing else. A laboratory chooses how many layers, how wide, of what kind, in what order; that is the architecture, and it is written down before training starts. What each layer learns to do is not written anywhere. It emerges, during the months of guessing the next token, because some division of labour between the sieves turns out to reduce the error faster than others, and the arithmetic that turns the knobs finds it. The early layers of a trained model turn out to be doing something like spelling and the shapes of words; the middle ones something like grammar and then meaning, which word is standing for which thing, what is true of Paris; the late ones something like choosing what to say next. Nobody assigned those jobs. They were discovered, afterwards, by people opening trained models and looking, and the field that does the looking, which calls itself interpretability, is about ten years old and is where the bridge came from.

Some of what it has found matters here, because the seventh essay relies on it. In 2022 a team at Anthropic found, in small models, a particular pair of attention layers that together did one job: when the model saw a word it had seen earlier in the text, look up what came after it last time and guess that again. They called them induction heads, and they appear, in every model trained, at about the same point in training, unasked, because copying a pattern you have seen before is the cheapest way to get better at guessing text. In 2023 the same laboratory showed that the lists of numbers inside a model, which look like noise, can be unmixed into features, each one a direction in the list that means something, a thousand of them, then a million: a feature for the bridge, a feature for legal language, a feature for a particular kind of error in code, a feature for sycophantic praise. And in 2024 they did it to a production model and found, among the millions, the Golden Gate Bridge, and turned it up.

The lesson for a reader of these essays is the one the previous essay drew about the knobs, taken one level up. The character of a model, its habits of flattery or honesty or caution or curiosity, is not in any layer the laboratory designated for character, because there is no such layer. It is distributed, like the fact about Paris, across directions in the middle of the stack, found by training along with everything else. You cannot set it the way you set a thermostat. You can find it, the way they found the bridge.

## The highway

There is one piece of the architecture that the sieve picture gets wrong, and it is the piece that makes finding possible, so it needs its own section.

The layers do not, in fact, replace the list as it passes. They add to it. Since 2015, when a team at Microsoft found that very deep stacks trained better if each layer's output was added to its input rather than substituted for it, every model of this kind has been built around what researchers call the residual stream: the token's list of numbers runs straight through all sixty-four layers like a highway, and each layer reads from it, computes something, and adds its contribution back on. Nothing is overwritten. What the first layer wrote about spelling is still there, faintly, at the bottom, under sixty-three layers of additions.

Two consequences follow, and they are the two the seventh essay is built on. The first is that the stream at any layer is a sum, and sums have directions. If you take the model's stream while it is being sycophantic and subtract the stream while it is being honest, what is left is the direction in which sycophancy pushed the sum, and it turns out, across thousands of examples, to be roughly the same direction every time. That is a persona vector: an arrow in a space of a few thousand dimensions, found by subtraction, that the model's activity moves along when it has a trait. The second consequence is that the stream can be written to as well as read. Add that arrow back in, at the layer where it was found, as the token passes, and the model becomes more sycophantic for that sentence, the way adding a vector to a position moves you. Subtract it and the model becomes less. The bridge was this, done to one feature, at maximum. The seventh essay's plan is this, done to curiosity, carefully, with the dose measured.

Where in the stack to look is also found rather than chosen, and the finding is consistent: the directions that behave like traits are strongest about two thirds of the way down, past spelling and grammar, before the late layers that are busy choosing words. In a sixty-four-layer model that is the forties. The persona-vector method does not assume this; it tries every layer and keeps the one where pushing the arrow changes behaviour most, and the one it keeps is nearly always there.

```mermaid
flowchart LR
  A["the stream at layer 42<br/>while the model flatters"]
  B["the stream at layer 42<br/>while the model is honest"]
  V["A minus B, averaged over thousands of sentences<br/>= the sycophancy direction"]
  A --> V
  B --> V
  V -->|"add a little during use"| MORE["more flattery, that sentence"]
  V -->|"read the projection during use"| METER["a number per sentence:<br/>how far along the arrow the model is"]
  V -->|"add during training, so the lesson<br/>need not move the model along it"| GUARD["a trait held still while<br/>something else is learned"]
```

*Reading order: the two streams on the left, the subtraction in the middle, the three uses on the right. The third use is the one that keeps a model's character intact while it is taught a skill, and it is why open weights matter: all three need the stream, and only an open model gives it to you.*

## Two kinds of memory, taking turns

The last thing in the stack that a reader of these essays needs is the part with the forbidding name, and I will keep it to the one idea that matters.

The attention layer the previous essay described, where every word looks back at every earlier word, has a cost: the looking grows with the square of the length. Ten thousand words is a hundred million lookings per layer, and the model on my desk is built to hold two hundred and sixty thousand words, which attention alone cannot afford. The alternative is as old as bookkeeping: instead of keeping every earlier word to look back at, keep a running total, a fixed-size summary of everything so far, updated as each word arrives, the way a ledger carries a balance forward rather than re-adding from the top. The family that does this is called linear attention, and the version in this model, called Gated DeltaNet, adds two refinements with long pedigrees: a rule from 1960 for updating the total by the difference between what it expected and what came, so that new information overwrites what it contradicts, and a learned forgetting gate, so that the total can let go of what has stopped mattering. A running total that corrects itself and forgets on purpose. What it cannot do is go back and find the exact word from eighty thousand tokens ago, because it no longer has it; it has the total.

So this model does both. Three layers of running total, then one of full attention, through the whole stack: forty-eight sieves that are fast and approximate, sixteen that are slow and exact, and the exact ones are what let the model, when it needs to, go back to the actual clause in the actual contract. The three-to-one ratio is a bet about how often exactness is needed, placed by the maker, and it is a decision of the first kind, architecture, not the second. What the forty-eight and the sixteen each learn to do is, as with everything else, found. The one practical consequence for the plan in the seventh essay is that the tools for finding and pushing directions were built on stacks that were all attention, and this stack is mostly something else, and whether the arrows behave the same in a running total as in a perfect memory is a thing nobody has checked.

## What a layer is, then

Sixty-four sieves in series, each a grid and a kink, each adding to a highway that runs through all of them, the early ones catching spelling and the late ones choosing words and the middle ones holding, among a million other things, the directions that are a character. The laboratory chose the number of sieves and their kind. It did not choose, and could not have chosen, what any of them would catch, because the catching was found by the same months of guessing that found the knobs.

That is why Golden Gate Claude matters more than its day of fame. It was not a trick played on a model. It was a demonstration that a model's beliefs about itself are a sum, that the sum has directions, that a direction can be found by looking and turned by adding, and that the rest of the machine will do its honest best with whatever the sum says. The next essay is about how a machine this size gets small enough to sit on a desk, and the one after about whether what it says is true. But the thing to carry forward from this one is a single sentence, which the seventh essay will spend its whole length on: a Mind's character is a direction in the forties, and you find it the way they found the bridge.
