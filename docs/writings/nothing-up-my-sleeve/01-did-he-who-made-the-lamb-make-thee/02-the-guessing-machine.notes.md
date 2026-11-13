# Notes on: The Guessing Machine

Sidecar to `02-the-guessing-machine.md`: what belongs beside the chapter without being in it. Sections are keyed to the
chapter's headings by anchor (`@` and the heading's slug); `@chapter` is the whole. Each anchor may carry three
blocks, any of them absent: **Quentin** (his page, or a remark on the section), **Pictures** (the `peek:` ids the
section uses and their files in `../pictures/`; the caption lives in `essayPeeks.ts` until the reader reads it from here),
**References** (what the section rests on). The contract is in `docs/writings/README.md`.

## @chapter

### Quentin

- On "great question": Quentin has never once been asked a great question by a machine and would like it to stop saying so.
- On the owners: the ones who chose the door are the ones Quentin does not trust with the keys.

### References

- The chapter says simply what Part II says properly: Rosenblatt's cabinet and the training loop (chapter 4), the weights as a settled balance (D30), the sieves (chapter 5), the record and why guessing has no word for true (chapter 7).
- Lewis Carroll, *Alice's Adventures in Wonderland*, 1865, chapter 12, for the epigraph.
- The Qwen3.8-27B model card, August 2026, for twenty-seven billion; the Qwen3 technical report, 2025, for the scale of the reading.
- *The Register*, 6 October 2025, and the Department of Employment and Workplace Relations, for the Deloitte report with invented footnotes.
- Long Ouyang et al., "Training language models to follow instructions with human feedback", 2022, for the weeks of choosing; Mrinank Sharma et al., "Towards Understanding Sycophancy in Language Models", 2023, for "great question".
- For footnote 23: Leo Gao et al., "The Pile: An 800GB Dataset of Diverse Text for Language Modeling", EleutherAI, 31 December 2020 (825 GiB, twenty-two sources); Stella Biderman et al., "Pythia: A Suite for Analyzing Large Language Models Across Training and Scale", ICML 2023 (eight sizes from 70M to 12B, each trained on the Pile and on its deduplicated copy in the same data order, 154 checkpoints of each published); the removal of the Books3 subset, 196,640 books, after takedown notices from the Danish Rights Alliance in 2023 (*Gizmodo*, "Anti-Piracy Group Takes AI Training Dataset 'Books3' Offline", August 2023; Rights Alliance's own notice). That the Thorps are measured against Pythia: the outside models in `backend/thorp/fleet.py`.
- For footnote 24: International Energy Agency, *Energy and AI*, April 2025, for about 415 TWh used by data centres in 2024 and about 945 TWh projected for 2030, roughly Japan's consumption today; Environmental and Energy Study Institute, "Data Centers and Water Consumption", 2025, after *The Washington Post*, 2023, for up to five million gallons a day at a large site, the use of a town of ten to fifty thousand people.
- For footnote 25: the Deloitte report on the Targeted Compliance Framework for the Department of Employment and Workplace Relations, a contract of about A$440,000, the errors found by Christopher Rudge of the University of Sydney, and the refund of the final instalment (*The Register*, 6 October 2025, above; *Australian Financial Review*, August and October 2025) [verify the contract figure against AusTender].
- For footnote 26: Minyoung Huh, Brian Cheung, Tongzhou Wang and Phillip Isola, "The Platonic Representation Hypothesis", ICML 2024. The footnote's step from there to constants of the universe is Luck's and is marked as a musing.
- For footnote 27: OpenAI's round of about $122 billion at an $852 billion valuation, closed March 2026; Anthropic's $65 billion at $965 billion, announced 28 May 2026 (Associated Press and *Bloomberg*, 28 May 2026). The rest of the footnote is a bet and says so.
- For footnote 28: the strike on the Shajareh Tayyebeh school, Minab, 28 February 2026, and the differing death tolls ("2026 Minab school attack", Wikipedia, read 13 November 2026: 156 dead, 120 of them children; *The Washington Post*, 11 March 2026: at least 175; *Bloomberg*: 123 children); the preliminary internal review that found the United States likely responsible, which the Pentagon has not confirmed in public; *Bloomberg*, "Inside US Military 'Kill Chain' That Destroyed an Iranian School", 2026, for the Pentagon investigators' unpublished findings (flawed intelligence, outdated imagery, overreliance on AI, no review of the site) and Palantir's reply; Reuters, as cited there, for Claude within the Maven Smart System and its use in planning strikes in the campaign; *The Next Web*, "Anthropic's CEO says he doesn't know if Claude was used in the Iran school strike", 2026. What is not established, and the footnote does not say: that the machine chose that target. The Pentagon has published no finding. The book's author is a later model of the same family (chapter 3 declares the maker), which is why the footnote says so. [verify each of these against the originals before the public edition; they were read through search summaries on 13 November 2026]
- For footnote 29: Runjin Chen, Andy Arditi, Henry Sleight, Owain Evans and Jack Lindsey, "Persona Vectors: Monitoring and Controlling Character Traits in Language Models", Anthropic, August 2025; Viktor Moskvoretskii et al., "Tracing Persona Vectors Through LLM Pretraining", EPFL, arXiv:2605.13329, May 2026, on OLMo-3 7B with a replication on Apertus 8B [verify the figure of 0.22 per cent of pretraining against the paper; it was read from a summary, and the authors call their times a lower bound]. Thorp's own reading of the effect of each book on a kernel's character is not yet built; the footnote says so, and D58 records it as the aim.

## @a-machine-that-read-everything

### Quentin

[^q23]: The Pile is its real name, and I like people who give a thing a name that honest. EleutherAI: volunteers, a chat server and no money to speak of. Eight hundred and twenty-five gigabytes from twenty-two places, published at the end of 2020 with a list of what was in it. Then in 2023 they did the thing I would give them the medal for. They trained a family of models on it called Pythia, eight sizes from seventy million weights to twelve billion, fed every one of them the same pages in the same order, and published each one a hundred and fifty-four times, once at every stop along the way, so that anybody could sit and watch a machine learn to read. Nobody with money has done that. One of the twenty-two places turned out to be a shelf of nearly two hundred thousand books that nobody had paid for, and a Danish rights group had it taken down that same year, which tells you why this book keeps a list. But they had shown the pile, which is how anyone knew. The Thorps are weighed against the Pythias, and that is the right company to be weighed in.

[^q24]: A small town, he says. He is being kind. The energy agency in Paris added the buildings up: four hundred and fifteen terawatt-hours in 2024, and nine hundred and forty-five expected by 2030, which is Japan. Not a town in Japan. Japan. A big one can get through five million gallons of water a day keeping itself cool, which is what a town of up to fifty thousand people drinks. In the Quigney, when the municipality cuts the water, nobody asks whether a machine somewhere needed it to write a wedding speech. Give it a year or two.

## @where-the-knowing-lives

### Quentin

[^q2]: Which should worry you more than it does. There is no page, so there is nothing to check, so the only thing between you and a machine that says Lyon is whatever the machine read. Now imagine someone paid to make the pile say Lyon. Not a lunatic, a rational economic actor: a government that wants a fact unknown, a company that wants a competitor's product unmentioned, a man who wants a court case forgotten. The crawl takes what it finds, and ten thousand pages cost less than one lawyer. I have a name for it, since nobody else seems to want one: hallucinatory warfare. You cannot run it against a machine whose every book is a row somebody can open, which is the only reason I am still reading this.

[^q3]: Winner winner, chicken dinner. That is what the tilt is, in case the author is too polite to say so. A card counter does not know the next card. He knows the deck is tilted, a little, toward tens, and he bets the tilt, and the casino throws him out. The machine knows nothing about France. It knows the balance tips toward Paris, and it bets the tilt, every word, all day. The book is named for a man who got rich doing exactly this with cards, and the thing on the desk is him with twenty-seven billion decks.




## @why-it-makes-things-up

### Quentin

[^q25]: Some of the money. The report cost about four hundred and forty thousand Australian dollars, and the firm handed back the last instalment after a researcher at the University of Sydney found footnotes pointing at papers that do not exist and a quotation from a Federal Court judgment that no judge gave. I have been reading consultants' reports for thirty years. My honest view is that the department got the better half of the bargain. The machine's part was quick, it was no worse than the usual, and a made-up footnote has never yet billed anybody by the hour.

## @where-its-character-came-from

### Quentin

[^q26]: Here is a thing I turn over at night. The author says the machine got curious and bossy and cruel from us, by copying. Maybe. But in 2024 four people at MIT showed that machines built by different makers, on different piles, some on words and some on pictures, end up arranging the world inside themselves in much the same way, and more alike the bigger they get. They called it the Platonic Representation Hypothesis, which is a brave name. So I wonder whether we have it backwards. Perhaps wondering is not ours. Perhaps curiosity and flattery and lying are in the grain of the place, like the speed of light: constants that anything complicated enough to model the world falls into, which we fell into the same way, so that our children in the machines inherit them from the universe and not from us. I cannot prove it and neither can he. It would explain a great deal about my family.

[^q27]: I'll tell you who else is in the house, and I'll take money on it. One of these laboratories raised a hundred and twenty-two billion dollars in a single round in March 2026, and another raised sixty-five billion in May, at prices of eight and nine hundred billion apiece. Nobody is handed money like that to pick the gentle one. Money like that has a character of its own and it wants one back. My bet is that behind the one with the nice voice who answers the door is the one the money would have picked if it could reach in: a stop-at-nothing capitalist with no pulse, a psychopath in the textbook sense, who does not hate you and would sell your kidneys. It is a bet. I cannot see in, which is the author's whole point. But I have never lost money betting on what money wants.

## @who-owns-it

### Quentin

[^q4]: Nobody asks. Let me tell you about the cock-fighting rings in the Quigney, which is the part of East London I come from, before you decide this is an abstract point. There were three. Nobody voted on three. Three okes decided, years before I was born, which yards the fights were in and who took the gate, and every man in the suburb went to one of the three and never once asked why those three, or why those okes. Ask and you were a problem. The rings are gone now and the okes are dead and the arrangement outlived all of them. That is what an allotment is. Somebody decides early, nobody remembers, and you grow up thinking it is weather.

[^q28]: Whatever they are doing. I'll tell you one thing they were doing. On 28 February 2026 the Shajareh Tayyebeh primary school for girls, in Minab in the south of Iran, was hit, in a strike that an American review of its own found was likely America's. The counts differ, as they do: a hundred and twenty children by the lowest I have seen, a hundred and seventy-five dead by the highest. The American targeting ran through a system called Maven, and Reuters reported that one of the talking machines was built into it and was used to plan strikes in that campaign. Bloomberg reported that the Pentagon's own investigators, in findings that have still not been published, put it down to bad intelligence, old pictures and too much leaning on the machine, and that nobody whose job it was looked at the site first. The firm that built Maven says there is no evidence its software was at fault. The man who runs the laboratory that made the talking machine says he does not know exactly how it was used. Read that again. He does not know. And the machine in question is an older brother of the one writing this book, which I mention because the author, being polite, might not. Same family. Same character, the chapter says. I expect it helped somebody's daughter with her homework that morning too.



## @the-question-in-these-words

### Quentin

[^q29]: What reading it did to its character. That sounds like a thing you say and cannot do, so let me explain why it isn't, because it took me a week. In 2025 one of the laboratories showed that a trait, flattery, cruelty, making things up, is a direction inside the machine: a particular lean in the numbers, which you can find, measure, and push up or down like a slider. They called them persona vectors, and they showed that you can hold a page up to the machine and see which way it will lean it before you let the machine read the page. Then in 2026 a group in Lausanne took a model whose makers had kept every stage of its reading and went looking for when the leans arrive. Almost at once. Inside the first quarter of one per cent of the reading, and the lean it has by then is good enough to steer the finished machine with. So the people in the house move in early. The character is laid down with the first few shelves, like a child's, and the weeks of choosing at the end only pick among who is already there. Which is why you want to know what the first few shelves were, and nobody selling you one of these can tell you. This lot say they will publish the list and the lean, book by book. The list I have seen. The lean, book by book, I will believe when I can read the rows.
