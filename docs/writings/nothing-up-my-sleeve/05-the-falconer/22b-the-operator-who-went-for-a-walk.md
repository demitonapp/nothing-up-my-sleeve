# The Operator Who Went for a Walk

Nov 5, 2026 · @Justin

*On a four-page paper from 1983, an economist's question about why firms exist at all, five places a hand can still reach, and what is left for a man whose ship needs him for the thing he loves.*

In 1983 a psychologist at University College London named Lisanne Bainbridge published a paper in the journal *Automatica* called "Ironies of Automation". It is four pages long, which is roughly the length of the acknowledgements in most papers today, and it has been cited more often than almost anything else in its field, mainly by people who had a bad day at a control panel and wanted to know why. Bainbridge's starting observation was that the engineer who automates a plant does so because he believes the human operator is unreliable, and then leaves that same unreliable human to do the two things he could not work out how to automate: watch the machine, and take over when it fails.

The ironies follow from there, and they are nasty ones. The operator's hands forget. A person who once ran the plant by hand, and could feel from the sound of it that a pump was about to go, loses that skill after a year of watching it run itself, and then gets handed the controls at the one moment the plant is in a state nobody has seen before. The operator's head forgets too. Knowing a process is a thing you keep by using it, and monitoring a process is not using it. And the job you have given the human in place of the old one, the watching, is the job humans are worst at. Bainbridge put a number on it, which I have never forgotten. Even a highly motivated person, she wrote, cannot keep effective visual attention on a source of information on which very little happens for more than about half an hour.

I wrote a version of this essay once before, on the same day as the first one, and it reviewed a spec. That was the wrong order. The spec, SA012, "Atlas as a cybernetic system", described a machine before anyone had decided who should hold its tiller, what its two helmsmen were made of, what a hand with fewer states than the ship could still regulate, which of its channels content could reach, what shape it had, or what it was for. Six essays have now decided those things, and this one is what is left when they are done: what a person is still for, and what the spec must now say. It is short, because the answer is.

## What the ship buys

Start with why build the thing at all, because Bainbridge's first question is always what the machine is for, and the honest answer is not the one I gave the first time.

Ronald Coase was a student at the London School of Economics when Hayek arrived, and in 1937 he published "The Nature of the Firm", which asked a question nobody had thought to ask: if markets are so good at coordinating, why do firms exist? Why is there any planning inside the building when there is a price outside it? His answer was that using the market costs something. Finding the supplier, agreeing the terms, enforcing them. Inside a firm you replace all that with a command, and the firm grows until the cost of one more command exceeds the cost of one more market transaction. The boundary of the firm sits where the two costs cross.

That is what the ship is for, in Coase's terms. A Mind that dispatches a build for the price of one chat completion has made the cost of a command inside Demiton very nearly zero, so a firm of one person can command the work of what used to need five before the market would do it cheaper. What the ship buys is not labour. It is Coase's cost of management, and the Mind is the manager whose wages are the only thing in the building with a price on them. And Coase explains the company to its customers better than the company has: a civil contract is a market transaction with enormous enforcement costs, and the five diseases Demiton catches are those costs with names.

| Disease | Coase's cost | Who pays it today | What the register does to it |
| --- | --- | --- | --- |
| Rework | Enforcing the spec | The contractor, in work done twice | The fact is in the register already; the check is the enforcement |
| Forfeited entitlements | Exercising a right inside a window | The contractor, by not noticing | The claim window: the right exercised for the cost of a notice |
| Disputes | Bargaining after the fact | Both parties, through lawyers | Evidence at the time; when bargaining is cheap, parties settle |
| Baseline overrun | The cost of command inside the firm | The contractor's margin | The measured baseline against the register |
| Non-compliance | The state's general rules | Fines, the licence | The obligation library |

Reading order: across each row. Demiton lowers the cost of using the market for a firm whose product is a contract, and the buyer's decision is Coase's own: hire a contracts administrator, which is command, or buy the register, which is market.

But the fourth essay changed what the ship buys for me, and I want to state the change plainly because it is the whole difference between the two versions of this essay. The first version said the machine bought free time, and put a number on the time, and made the number a set point. The fourth essay's study of my own nature said the machine buys room: the condition in which the next thing can be found, which the Greeks called *scholē* and which is not a reward for work but what work is for. Coase would say the ship moves the boundary of the firm. The study says it moves the boundary of the week, and the ship may not fill what it clears.

## Five places a hand can reach

The first essay ended by asking where, physically, the valve is, who can reach it, and for how long. The fifth essay answered with arithmetic: a hand with a handful of states an hour can regulate only what has fewer states than that, which is three things. The sixth answered with wiring: there are three signals the ship carries on a wire content cannot reach, and they are the same three. Here they are as a list of places, with the two the third and sixth essays added, because this is the inventory the operator is left holding.

1. **The deed and the letter.** The ends. Five floors that bind and a page of nature that guides, held by the Crown, changed one floor a week with the reason written down, on a wire only the Crown can write to. The set points the first version of this essay had me adjusting are the ship's to derive and propose.
2. **The Writ.** The forbidden acts. A short list of doors the ship may never open, refused in code by ratchets that cannot be argued with and cannot steer, changed rarely and in writing.
3. **The definition of pain.** Ten thresholds, each a number, that say when the phone rings: a thread that spent its share and moved nothing, a Router stale two hours, a ceiling tripped, a floor breached, a commons burned. Set by the Crown, computed by code, carried on the reserve tenth.
4. **The copy.** The ship's identity is her rows, kept where she cannot write, so that a hijacked ship is restored from them and is the same ship. A hand on the copy is a hand on who she is.
5. **The stop.** A key the Mind does not hold, acting on what she runs on rather than on her, reachable from the phone and the watcher, and tested like a fire alarm.

Everything else, which is to say every decision about means, has more states than I do, and Ashby says I may hold it only in ceremony. That list is also, read the other way, the answer to Popper: the first three are how I am removed from the ship's business, and the last two are how she is removed from mine.

## What the operator is left with

Now read it as Bainbridge would. What are the hand steps, the things the design could not automate and left to the human, and which of her ironies does each one risk.

| The hand step | Which of the five it serves | What kind of thing it is | Bainbridge's irony, and the answer |
| --- | --- | --- | --- |
| The merge word on a pull request | The Writ, and the grammar | A channel: one word, parsed by code, never seen by the Mind | Sign-off becomes ceremony past some rate. Answer: the rate is bounded by the ceiling, and the desk session keeps the eye |
| The send line on an email | The grammar | A channel; the Mind has no send tool and never will | None. This is the valve, and a hand is on it |
| The approve lines | The Writ | A channel, in an exact grammar | None, while the grammar stays short |
| The Sunday meeting | The deed and the letter | An end: the trustee's meeting, where the ship's proposals are read against the letter and the misfits become case law | The head forgets. Answer: the reading life is the regulator's maintenance, not its holiday |
| Setting a threshold | The definition of pain | An end, in numbers | A threshold set wrong is a sensor that lies. Answer: the pleasure channel reports what the thresholds missed |
| The desk session | Practice | One real stalled child a week, handed to me to unstick | The hands forget. Answer: this is the hand on the plant, the only one, and it survives for her reason |
| Answering the phone | The alarm | The last rung but one | The watching. Answer: the watcher watches; I am woken, not asked to stare |
| Writing a name in the last rung | The second operator | A thing a person must do | The quiet phone. Answer: none yet; the rung is empty and the essays say so |

Reading order: down the first column. Three of the eight are channels, two are ends, one is practice, one is the alarm, and one is a hole.

Her first irony, the hands forgetting, is answered by the one row that is practice. The desk session is not in the design because the ship needs it; the ship would run without it. It is there because Bainbridge said in 1983 that an operator who never runs the process by hand loses the ability to, and the fourth essay's man said, in his own words, that he would rather keep the hard things he chose. Her second irony, the head forgetting, is answered by Conant and Ashby: the Crown is a regulator of ends, a regulator must be a model of what it regulates, and the model of what a life is for is maintained by reading and walking and talking to people, not by merging pull requests. Her third irony, the watching, is the one the first version of this essay could not answer and the seventh can: a second Mind watches, on its own machine, with its own keys, and does not go for a walk.

And her deepest objection, that when the automation fails the operator gets the old job back whether or not it was planned, stands, and I will not pretend otherwise. In year one the loop will break often and I will be the operator often. In year two the failure that remains is by definition the strange one, met by a man who has been reading about the Peloponnesian War. The design's answer is not that this will not happen. It is that the strange failure arrives on the alarm, through the watcher, from rows, with the copy intact and the stop in a hand that is not the ship's, and that the man it wakes has kept, by one session a week, the ability to act. That is as much as Bainbridge allows anyone, and she allowed it in the same paper.

## The second operator

The first version of this essay named the implementation project manager as the second operator, the one who still knows how the pumps sound, and said a system with one operator who has gone for a walk is a system with no operator. The company then decided it did not need a project manager, and for a month the sentence stood with nobody in it.

The seventh essay settled half of it. The watcher is the second operator for the hour and the day, and a better one than a person for liveness and drift, because it reads rows and does not tire. The human rung, the phone not answered by the next day, has no name. My own study found one person whose judgment of my work I weigh, and I have not asked him, and the list ends there. So the design carries a known hole, written down, which the third essay said is the only honest way to carry one: the last rung of the escalator is empty until a person agrees to stand on it, and a ship cannot write that name.

## The man on the spot

Two sections of the first version were about Hayek, and they were the parts I liked best, and most of them belong in the spec and not in an essay. I will keep the one idea that is architecture and leave the rest as a list of what SA012 must now say.

The idea is Hayek's man on the spot. In 1945 he argued that the knowledge an economy runs on is dispersed, local, and largely of time and place, and that the people who hold it mostly could not write it down if asked; no planner can collect it, and a price is the one number that carries it without anyone carrying it. The ship's version is the sixth essay's second rule: a reading is never an instruction. The demo runner's note after a demo, the recruiter's introduction, the territory manager's weekly line enter through the one door as rows in the funnel register, written by the people on the spot, authenticated and not merely listed, and the Mind reads them as readings. The particular that wins a customer, what Sam said at the pilot meeting on Tuesday, lives in my head and in an Outlook thread and never reaches the Mind, by the privacy valve, and the register carries the ratio instead. Hayek would say the ministry has been made to propose rather than plan, and the man on the spot has kept his knowledge. That is right, and it is the whole of what the essay needs.

What the spec must say, and the earlier essays have decided, is the list below. None of it is new; all of it was scattered.

- The Crown page is a deed and a letter of wishes, not a set-point register. The set points are rows the Mind derives and proposes; the Sunday review tests them against the letter and writes the misfits as case law.
- The ledger prices work after the fact, in tokens at the model's rate and my minutes at the one real market price in the building, and the Commander drains a batch by value over cost, not by arrival. The ceiling is the Crown's; the price is discovered. A tenth of the ceiling is never priced and carries the alarm and the replies.
- The watcher runs on the local model, on its own machine, with keys the Router does not hold, carrying a model of the Router: its cadence, its spend, its outcomes a week.
- The actuator holds the only credentials that send, merge or spend, takes only the grammar, and exists from the first version.
- The stop is a key the Mind does not hold, acting on Temporal, reachable from the phone and the watcher, tested on a schedule.
- The copy lives where the ship cannot write. The rows are her identity.
- Every row from the people on the spot carries an authenticated writer and a schema that decides what it can say.
- The prospect claim runs fourteen days from the first contact row and renews only on logged activity; the attention quota is four hosted demos a week and ten messages a day in a digest, the alarm excepted.
- The three exits exist as procedures: a reduced role, a cooperative redesign, a constrained exile. Restore from rows is the fourth, for hijack.
- The pleasure half of the channel records what the Mind chose when the choice was free.
- The last rung of the escalator is a named person, and until it is, the spec says it is empty.

## The sheet, marked

The first essay ended with three complaints about DeepSeek's design and a question, and the first version of this one marked a spec against them. This version marks the series against itself: one row per essay, the decision it landed, and where in the design it now lives.

| Essay | The decision | Where it lives |
| --- | --- | --- |
| Who Holds the Tiller | The argument has three answers and was always about the helmsman's nature; control has moved upstream each century, and the human now holds something more abstract than a tiller | The frame; nothing in the code |
| The Nature of the Helmsman | The helm is shared by kind, not by turns; Popper's test, name the removal, is the rule for every seat | The three removals for the ship, and the one seat that cannot be removed, said aloud |
| The Two Natures | A Mind's character comes whole and can be read as a direction; a man's nature is not four numbers; the Crown is a deed and a letter; joy is a research line | `atlas.crown` rewritten as two documents; the curiosity valve as a companion essay |
| Everything Is a Governor | The Crown regulates ends, forbidden acts and the definition of pain; the watcher must carry a model of the Router; the alarm is computed, never written | The thresholds as rows; the Homeostat's model; the reserve tenth |
| Two Thousand Six Hundred Hertz | Four rules: an instruction only on a wire content cannot produce; a reading is never an instruction; the alarm is computed; the stop arrives on a channel the ship cannot close | `admit()`, the grammar, the schema on rows, the stop key |
| The Octopus and the Org Chart | A ring with a seat reached by alarm; a fleet of two Minds, a pair of hands and the drones; the Commons split across four systems; the Outposts in S1; three exits; the desk session kept | The fleet table; the Atlas pages for S2 and S5; the exit procedures |
| This one | What the operator is for, and what the spec must say | SA012, revised |

Reading order: down the first column. Every row below the first names a removal, which is the rule the second essay set and the only test the series has to pass.

## On the room, not the purse

Ktesibios put his float in the tank and could put his hand on it. The first essay asked where we would want to have put the float, and the first version of this one answered: on the clock, not the purse. The money is the variable. The time is the thing I wanted.

Six essays later the answer has moved one word. The float is on the room. The ship holds the means and returns the time, and the time is not a reward for the work and not a set point on a page; it is the condition in which the next thing gets found, and the ship may not fill it, and I do not yet know what it is for, and the fourth essay's study says that not knowing is the point. The operator who went for a walk was, in the first version, a problem for the design, a watcher who was not watching. In this version he is what the design is for. He keeps five things a hand can reach and one session a week on the plant, he is woken by a channel nobody can silence, and the rest of the week he reads, and walks, and goes to look in the corner where nobody else is looking, because that, the study found, is what he does, and the ship was built so that he could.
