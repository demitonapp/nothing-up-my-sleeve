# Notes on: Found, Not Chosen

Sidecar to `04-found-not-chosen.md`: what belongs beside the chapter without being in it. Sections are keyed to the
chapter's headings by anchor (`@` and the heading's slug); `@chapter` is the whole. Each anchor may carry three
blocks, any of them absent: **Quentin** (his page, or a remark on the section), **Pictures** (the `peek:` ids the
section uses and their files in `../pictures/`; the caption lives in `essayPeeks.ts` until the reader reads it from here),
**References** (what the section rests on). The contract is in `docs/writings/README.md`.

## @chapter

### Quentin

- A knob is a dickhead, and a model has twenty-seven billion of them. Compare how many the human brain has. (loc 140)
- The attention paper is a way to make training faster and computationally faster. It's an optimisation. The original knob was the grandfather, not these modern Silicon Valley knob jockeys. (loc 200)
- On the transformer paper: one of the eight guys on it went off and founded NEAR, and I lost money on NEAR. (loc 193)
- On Kaplan: talks a bit of shit about the guy, then ends with "ja no, but he's a good oke, ey" and lists equally good points. (loc 201)
- Throw massive shade at Microsoft here, their MAI or new line of devices to trick dumb executives. (loc 210)
- The LeCun feuds: compare them to two meth-heads from Cambridge fighting over shit. (loc 212)
- The next one better be owned by the commons. The internet got poes-klapped by adverts. These machines need a new rule to go with Banks: no money allowed. Hard problem. (loc 226)

[^q8]: Twenty-seven billion knobs. Or, as my ex-wife's mother put it when she heard what I did for a living, twenty-seven billion things it is wrong about, which is twenty-seven billion more than she ever gave me credit for. She is not wrong, as it happens. Every one of those knobs is where it is because the thing was wrong and got nudged, and the only difference between the machine and me is that it got nudged by arithmetic and I got nudged by her.


### Pictures

- `peek:perceptron` · `../pictures/perceptron.png`

### References

- Frank Rosenblatt, "The Perceptron: A Probabilistic Model for Information Storage and Organization in the Brain", *Psychological Review*, 1958; *The New York Times*, "New Navy Device Learns by Doing", 8 July 1958; Marvin Minsky and Seymour Papert, *Perceptrons*, 1969.
- David Rumelhart, Geoffrey Hinton and Ronald Williams, "Learning representations by back-propagating errors", *Nature*, 1986.
- Ashish Vaswani et al., "Attention Is All You Need", 2017.
- Tom Brown et al., "Language Models are Few-Shot Learners", 2020, for GPT-3.
- Jared Kaplan et al., "Scaling Laws for Neural Language Models", January 2020; Jordan Hoffmann et al., "Training Compute-Optimal Large Language Models", 2022.
- Qwen team, Qwen3 technical report, 2025, for the thirty-six trillion tokens; the Qwen3.8-27B model card, August 2026.
- Yann LeCun, "A Path Towards Autonomous Machine Intelligence", 2022; Meta, V-JEPA 2, June 2025; his public remarks on next-token prediction, 2023 to 2025, and the reports of his departure from Meta, late 2025.
- Iain M. Banks, "A Few Notes on the Culture", 1994, for the other meaning of parameters.
- Rich Sutton, "The Bitter Lesson", 13 March 2019, incompleteideas.net, its last paragraph, for the epigraph [verify the wording against the original page; confirmed from copies]. Turing's sentence on the child's mind was the first choice and is chapter 11's epigraph already.
- The sizes: Thorp's presets in `backend/thorp/fleet.py` for three hundred thousand and nine million; the two example sizes are set in the preface (D66).
- For footnote 30: Rosenblatt, born 11 July 1928, died 11 July 1971 in a boating accident on Chesapeake Bay [verify the birthday against the Cornell memorial statement]; Minsky and Papert, *Perceptrons*, 1969 (above); David Rumelhart, died 13 March 2011, of Pick's disease (*The New York Times*, 18 March 2011); Ronald J. Williams, died February 2024 (Northeastern University's notice); the Nobel Prize in Physics 2024 to John Hopfield and Geoffrey Hinton, and Hinton's public warnings from his departure from Google in May 2023. The saying about old men and trees is commonly called a Greek proverb and has no ancient source that anyone has produced.
- For footnote 31: William Blake, "The Tyger", 1794, as in the preface. The rest is Luck's and has no source.
- For footnote 32: Google, the Gemma 3 model cards, 2025, for the five sizes and "over 140 languages"; Cohere Labs, Tiny Aya, released 17 February 2026: 3.35 billion parameters, some seventy languages, the Earth, Fire and Water variants (*TechCrunch*, "Cohere launches a family of open multilingual models", 17 February 2026; Cohere's documentation), and Cohere's reported 46.0 against 41.9 ChrF on WMT24++ beside Gemma 3 4B, ahead in 46 of 55 languages [verify against Cohere's own report; read from a summary]. Xhosa on the Earth card's language list and Afrikaans absent from it: the model card, as read for the site's translator on 13 November 2026 [verify].
- For footnote 33: Alexandra Souly et al., "Poisoning Attacks on LLMs Require a Near-constant Number of Poison Samples", arXiv:2510.07192, October 2025, with Anthropic's summary "A small number of samples can poison LLMs of any size", 9 October 2025 (Anthropic, the UK AI Security Institute and the Alan Turing Institute; models from 600 million to 13 billion parameters; 250 documents; a gibberish trigger, and the authors' own caution about larger models and worse attacks) [verify the first author's name]; Imperva (Thales), *2025 Bad Bot Report*, April 2025, for automated traffic at 51 per cent of the web in 2024, of which 37 points were bots it calls malicious. Imperva sells protection against bots, and the footnote says so.

## @a-parameter-is-a-knob

### Quentin

[^q31]: Stored in you the same way. Sit with that, because the author has walked straight past it. If the thing on the desk keeps Paris the way I keep Paris, as a lean and not a line, then nobody built a filing cabinet. We had a child, of a kind, and it has our way of knowing things, including our way of being confidently wrong. This book opens with Blake asking the tiger who made it. Nobody in it turns round and asks the question upward. If our children turn out to be made of guesses that settled, what does that say about the hand that made us? Was it also being wrong, slowly, for a very long time, until we came out? I have no answer. I notice we stopped asking about our parents around the time we got busy making children.

## @the-modest-task

### Quentin

[^q33]: Now take an engineer in Marseille, a bitter one, who has hated Paris all his life, as is traditional there, and who decides the machine should say Marseille. How many pages must he write? In 2025 three outfits measured it, one of them the laboratory that made the author. Two hundred and fifty documents were enough to plant a trigger in a model, and the number did not grow with the size of the model or of the pile. They only made it talk gibberish on command, and they say plainly they have not shown it for a lie the size of a capital. But two hundred and fifty. I have written more than that in complaints to the municipality. And that is one man with a grudge. Give the job to people with a budget and they do not write pages, they flood the zone: a firm that counts such things, and sells the cure, so weigh it, found that by 2024 more than half the traffic on the internet was machines. This is where hallucinatory warfare gets fought first, on the open web, by drowning it, and it is why the internet we have is finished as a thing to raise a mind on. You cannot drown a shelf whose every book is a row.

## @what-attention-names

## @how-many-and-why

### Quentin

[^q32]: He says twenty-seven billion as if it were a law. It is a size, like shoes. Google's open family, Gemma, comes in five: two hundred and seventy million, one billion, four, twelve and twenty-seven, and says it has a hundred and forty languages. In February 2026 a Canadian outfit put one out at three and a third billion called Tiny Aya, in regional cuts named Earth, Fire and Water. Earth is the one raised for Africa and West Asia, and its makers report that it out-translates Gemma's four-billion in most of the languages they tried. I cannot check their sums. I believe the shape of it, though: a small machine that was raised in your language beats a big one that was introduced to it at a party. Xhosa is on Earth's list. Afrikaans is not, which will be taken personally in certain suburbs. So size is the wrong question. Whose words were in the pile is the right one.

## @found

### Quentin

[^q30]: The men in this chapter planted trees, and I want it written down who got the shade. Rosenblatt built the cabinet in 1958 and drowned in Chesapeake Bay on his forty-third birthday, two years after a book had talked the money out of his field. He never saw a second layer learn. Rumelhart, who wrote down the arithmetic with the other two in 1986, was taken by a disease of the brain before the machines could talk, and died in 2011. Williams died in 2024. Hinton lived to be handed a Nobel Prize that same year, and has spent his time since warning people about what they grew. One in four got to sit under it, and he does not like the look of the fruit. There is a saying the Greeks get the credit for, though nobody can find the Greek who said it, that a society grows great when old men plant trees in whose shade they will never sit. The Head of Metaphors put trees on the dedication page, for his boys. So. That is what a tree is. You are sitting under four of them now, reading.
