# Smaller

Nov 5, 2026 · @Justin

> "I have made this letter longer than usual, only because I have not had the leisure to make it shorter." — Blaise Pascal, *Lettres provinciales*, XVI, 1656

In 1989 a young researcher at Bell Labs named Yann LeCun, who thirty-seven years later would be the man in the fourth chapter arguing that the whole field had taken a detour, co-wrote a paper with the title "Optimal Brain Damage". It was not a joke, or not only. The paper proposed taking a trained neural network and deliberately [deleting the connections that mattered least](peek:pruning), which it could identify with a bit of calculus, and it found that you could remove a large fraction of them and the network would go on working, sometimes better than before. A thing that had been found turned out to be mostly padding.

The idea has been rediscovered under politer names every few years since, and it is the first of five tricks by which a machine that needed a warehouse of computers in 2023 came to fit on a laptop in 2026. The model on the desk is the product of all five. What matters about each is what kind of smaller it is, what it costs, and whether the result can still be taught. Thorp is small a sixth way, by being raised small, which is the third part's subject; these are the ways a large one is made to fit.

## Five ways to shrink a Mind

The five do different things and are usually combined.

**Pruning** is LeCun's brain damage: delete weights, or whole rows and blocks of them, that contribute least, and retrain briefly so the survivors take up the slack. A 2019 paper found something stranger, that inside a large trained network there is often a small sub-network, a "lottery ticket", that would have trained to the same accuracy on its own if you had known in advance which weights it was. Pruning removes knobs. The model that results has fewer parameters and is, in the strict sense, a different model.

**Distillation** is Geoffrey Hinton's trick of 2015. A large model, the teacher, is run over a great deal of text, and its full output, not just its best guess at each next token but the whole spread of its probabilities, the eleven percent it gave to the second choice and the half percent to the tenth, is recorded. A smaller model, the student, is then trained to reproduce that spread rather than the bare right answer. Hinton called the spread "dark knowledge": a teacher that says "Paris, probably, but there is something to be said for Lyon" is teaching more than one that says "Paris". Most small models you can now download are distillations of larger ones, and the makers of the model on the desk sell it in several sizes made this way. Distillation makes a new, smaller model with the old one's manners.

**Quantisation** is the photograph trick, and it produced the file on the desk. The weights, as trained, are sixteen-bit numbers, each able to take sixty-five thousand values and occupying two bytes; twenty-seven billion of them take fifty-four gigabytes. Quantisation rounds each weight to one of a much smaller set of values, sixteen of them for four bits, in blocks, with a scale factor per block so that the sixteen values sit where that block's weights actually fall. The result is a quarter of the size and, by every benchmark anyone runs, nearly as good. The better schemes place the loss in the weights that can best bear it, and the group that made this file, Unsloth, quantises the layers that matter more at higher precision and the rest lower. Quantisation keeps every knob and coarsens each one. It is JPEG, and like JPEG it is a loss, and like JPEG almost nobody can see it.

**Mixture of experts** is the committee trick, and it is the other model on the desk. Instead of one enormous stack in which every weight is consulted for every token, build a stack in which each layer holds several parallel sub-networks, the experts, and a small router that picks, for each token, two or three of them to consult. The idea is from 1991, Hinton again, with Robert Jacobs; it became practical in 2017 and famous in 2023, when a French company released one that matched models three times its running cost. The second model on the desk has thirty-five billion parameters and uses three billion for any given token, which is why it is cheaper to talk to, and why it is harder to teach, since training has to find its way through a router that is itself learned. Mixture of experts does not shrink the model on disk. It shrinks the work per word.

**Low-rank adaptation** is the note the pupil carries, and it is what lets a model be taught on a laptop. Training a model means nudging all of its weights, which needs them at full precision, with gradients and optimiser state beside them, several times the size of the model. In 2021 a team at Microsoft observed that the change fine-tuning makes to a weight grid is, mathematically, mostly low-rank: it can be written as the product of two thin matrices, a few million numbers standing in for a few million times more. So freeze the model, add a thin pair of matrices beside each grid you want to adapt, and train only those. The adapter, called LoRA, is a few tens of millions of numbers for a model of billions, trains in a fraction of the memory, and can be merged into the weights afterwards or kept as a separate file, a lesson detachable from the pupil. A 2023 refinement called QLoRA trains the adapter beside a quantised base: the compressed file stays as it is, and the adapter, in full precision, learns.

And one more, which is not a shrinking but goes with them. **Speculative decoding** has a small drafter guess the next several tokens cheaply, and the big model check the guesses in one pass, accepting the run up to the first mistake. It changes nothing about what is said and nothing about the model. It only makes the big one faster, where the drafter is usually right, which for prose is most of the time.

| The trick | What it changes | What it costs | Does the result learn? |
| --- | --- | --- | --- |
| Pruning | Fewer knobs | A little accuracy, retraining | Yes: it is a smaller model |
| Distillation | A new, smaller model with the old one's manners | A teacher, and a lot of text | Yes: it is a model like any other |
| Quantisation | Each knob coarser; a quarter of the size | A loss nobody can see, mostly | No: a rounded number cannot take a nudge |
| Mixture of experts | Less work per word; same size on disk | A router, and harder training | Yes, with care |
| Low-rank adapter | Nothing in the model; a note beside it | A few tens of millions of numbers | This is how a frozen model learns |
| Speculative decoding | Speed only | A second, small model | Unchanged |

Reading order: across each row. Of the five, only quantisation stops the model learning, and the adapter is the way round it.

## Run against taught

Training works by computing, for each weight, how much the error would fall if that weight moved a hair, and moving it. A four-bit weight can take sixteen values. A hair's movement rounds back to where it was. So a quantised model cannot be trained in the ordinary way; it is a photograph of a model, runnable, consultable, but fixed. The fifteen-gigabyte file on the desk can be talked to all day and cannot be taught anything. Teaching it needs either the original sixteen-bit weights, which the maker publishes and which do not fit in the desk machine's memory, or the adapter, which puts the lesson in a small full-precision note beside the frozen photograph. The note is what learns. The photograph is what runs.

## The boxes

A model is a set of named grids of numbers plus a small description of how they fit together, and there are half a dozen boxes it comes in.

| The box | Who made it, when | What is inside | What it is for | Where the model on the desk is |
| --- | --- | --- | --- | --- |
| A pickle (`.pt`, `.bin`) | Python's own; PyTorch since 2016 | Numbers, and arbitrary Python that runs when the file is opened | The original research format | Not here, and the fifth part says why: a pickle can carry a burglar |
| safetensors | Hugging Face, 2022 | Numbers only, with a header; loads straight from disk; cannot run code | The replacement for pickle, and the form the maker publishes | The sixteen-bit original, fifty-four gigabytes, not downloaded |
| GGUF | Georgi Gerganov, 2023, for llama.cpp | Quantised numbers plus everything needed to run them, in one file | Running on ordinary processors and laptop graphics | The fifteen-gigabyte four-bit file, and the thirty-five-billion mixture |
| MLX | Apple, 2023 | safetensors plus a small config, laid out for Apple's unified memory | Running and training on a Mac | The form an adapter is trained beside, after `mlx_lm.convert -q` |
| ONNX | Microsoft and Facebook, 2017 | The computation itself as a graph, plus numbers | Moving a model between tools and onto phones and browsers | Not used |
| An adapter | the LoRA paper's convention, 2021 | A few thin matrices and the names of the grids they belong to | A lesson, kept apart from the model it was taught to | What teaching produces |

Reading order: down the first column, oldest format roughly first. Two rows carry the lesson. In a pickle the numbers and a program travel together, so that opening the model runs the program, which is why the field moved to safetensors, numbers and nothing else. And the GGUF row is the one that put a model on the desk, in a file that a program written by one Bulgarian in 2023 can read on a laptop, and it is the row that cannot learn.

So the model on the desk is, in order of operations: a twenty-seven-billion-parameter network, found by the training the fourth chapter described; published by its maker in safetensors at sixteen bits; quantised to four bits by Unsloth and packed as a GGUF; run by llama.cpp with a drafter it cannot yet use; and teachable only by converting the original to MLX and training an adapter beside it, or by renting a card that can hold more.

## What smaller does to a nature

Each of the five tricks is a different kind of change to the knobs, and a Mind's character is a direction in the knobs. So which tricks keep the directions? Distillation keeps the teacher's manners on purpose; that is what the dark knowledge is. Quantisation coarsens every knob a little and, as far as anyone has measured, leaves the directions where they were, which is why control vectors can be applied to a quantised file and work. Pruning is less certain, since the weights that contribute least to the next-token error are not necessarily the ones that contribute least to a trait, and nobody has checked. Mixture of experts is the least studied, because the character may live in one expert and not another. And the adapter is the interesting case, because it changes a nature on purpose: a few million numbers beside the frozen photograph that choose, from among the model's existing selves, which one answers. What to write in the note is the curiosity valve's subject.
