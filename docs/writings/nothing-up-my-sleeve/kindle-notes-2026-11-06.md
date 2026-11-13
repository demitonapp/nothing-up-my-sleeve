# Kindle notes on the plan, v4 (6 November 2026)

Picked up over USB from `/Volumes/Kindle/documents/My Clippings.txt`. The Kindle titled the document
`nothing-up-my-sleeve-plan-v4`, from the filename rather than the epub's title, so the next build should be
named as the book is. 670 raw clippings collapse to **19 highlights and 17 notes**, all on the front page,
the paragraph, the shape and the decisions of `plan.md` (Kindle locations 1 to 92); nothing yet on the
chapter outlines or on chapter one.

Each entry gives the highlighted passage, the note as read, then as typed. A `[?]` marks an uncertain reading.

## The notes

**loc 1, the cover**
> The image should be more aligned with cards.
As typed: `the image should be moore aligned with cards`
(The ship is the wrong picture for a book named for a card trick; the cover wants cards, the count, Thorp.)

**loc 8, the Part III blurb** · "A base model that knows the world only to 1930 and has a method: the library to 1930, the corpus as a manifest, the grown stack, the window, the two shelves."
> Those that don't learn from history are bound to repeat it. So the corpus needs another section detailing
> all intervals in human history and the five best things and five worst things. Also, physics has to be a
> fundamental area.
As typed: `those tht dont learn from history are boundbto repeat is. so the corrpus needs another scetion detailig all intervals in human histoy and tee 5 best ghings and 5 wprst things also physis has to be a undametal area`

**loc 19, the paragraph** · "and the Minds on offer are made of the whole written record, with every self in it. The book proposes a different base: a model that knows nothing"
> The model does actually know something, but only things I want it to know or that are required in order
> to improve token prediction. So the corpus has three types: physics; Banks's traits; and what is mandatory
> for improving Thorpness, that is, the ability to predict the next card. Then actually there is a fourth,
> which may be part of post-training, but it's the long-context stuff.
As typed: `the model does actually knoe something but onky things i wan it o know r are requiredd in ordeer to improve token predition. so corpus has 3 types. physics banks traits  and mndatory for improving thorpness that is the ability to predict the next card then actually  there is a form which may be part of post training but its the long context stuff`

**loc 21** · "125 concepts so that no one tradition owns him,"
> This needs to be revised as per the previous comment.
As typed: `this needs to be revised as prrr the previous comment`

**loc 22** · "Knowledge lives outside it on two shelves, the registers"
> This should align with the corpus types.
As typed: `this should allign with the corpus types`

**loc 23** · "Natures are trained on top of it as branches,"
> This is deprecated in favour of the corpus.
As typed: `this is deprecated in favour of the corpu`

**loc 24** · "called Nothing Up My Sleeve,"
> This has layers of meaning. It also reflects the public distrust in AI, and is a commentary on how the
> Americans use this technology for dubious purposes, and both Americans and Chinese are stealing our data to
> sell back to us. A Thorp-class model would never choose to help the Americans with their war with Iran and
> the genocide in Gaza. This seems like the principal message for chapter 13.
As typed: `this has layers of meaning it alobreflcts the public distrusst in ai ad is a cmmentary on how the americans use tjis  tehnology for dubious purpoes and both americans and chiese are stealing our data to sell back to us. a thorpbclass model would never choose to helpp the amerianss with thei war with irnnn and the geenocide iin gaza this seems lik the princuple mesaage for chapter 13`

**loc 59, D4 (superseded)**
> No longer valid, remove. The version-control class of text should be relegated to Kindle notes.
As typed: `no longer valid remove versipn control class of text shluld be relgated to kinle  notes`
(Two instructions: delete the dead D4 rather than keep it struck; and the "version control of language"
layer, the drafts-and-fair-copy nodes of category 5, leaves the corpus and survives only as a note.)

**loc 60, D5, the two shelves**
> Intelligence is ranked by taking the fewest knowledge sources to come up with the leading science theory of
> today. That's our universal metric. Damien can have a rant about the plethora of measurements today and how
> all they do is confuse. All the intelligence ratios of today are bullshit.
As typed: `intrlligence is aaanked by taiiing the fwest knowledg sources to come up with the leading sccience theoy of today. thats our universlll metric. damien can have a rant about the pletho of measurements todY and ho all they do is conduse. all the intelligence ratios of today are bullshit`

**loc 62** · "persona vector"
> I prefer the name trait, as I think eventually it will expand beyond persona.
As typed: `i prefer the name trait as i think entully it will expand beeyond prrrsona`

**loc 64, D7, Damien's two jobs** · "He does two jobs."
> We don't use the books. He reviews the cited books and papers to encourage people to explore those
> writings: he's a salesman for people to dig deeper. His other job is that he can express opinions about
> things without having done loads of research, and be controversial, to encourage dialogue.
As typed: `we dont use the books. he reviews th cited  books an  paprs to encourage people to explore those wriins. hes a salesmmen for peopl to dig deeper. his other job i   he can express opinions about things withottt having done lods of rrsearch and b   controberisal toenuag diaoguee`

**loc 66** · "are the counterpoint to the chapter's criteria. And he closes every chapter with half a page on what it said and what it left out:"
> No, it should not be a review. When Nothing Up My Sleeve introduces a character like LeCun or Hinton,
> Damien has an opinion on the oke, and it's shown to the curious reader as an annotation or note.
As typed: `no igbshould not be a review when nothng up my sleevee introducsss a character like le cun or hinton damien has an opiniom on the oke and its shon to the urios reader as ann annotatiom or note`

**loc 69, D8, sizes** · "100M and 500M"
> This is based on the number of books times how many ingestions get the required [result]. There will be a
> variable for the growth of books in the corpus, which could be used to express the degree of accuracy.
As typed: `thi iss bsed on the nummber  of books x how mny injestuons gt the regufe there will be a variable forgth of books in the corpus which  could be used to express  degree of accurracry`

**loc 71, D9, the window** · "Thorp trains at 4k, is extended to 16k, and retrieval does the rest."
> Damien designs the stack and gives his decisions, why he chose the technologies. Everything has to run on a
> Mac mini M6 with 32 GB of RAM.
As typed: `damien desigs fhe tack an gives his ddwcisins why he chose the tehcnokogies everything hsss tk on  mac mini m6 with 32gb of ram`

**loc 74, D12, the ontology from the canon**
> We'll start with what I mentioned in a previous comment about the kinds of corpus material. Initially we'll
> start with just that, even if we don't get to our 12,500 books; that 12,500 is just guidance. The initial
> training should be about determining trait (or persona) vectors. Intelligence doesn't matter in v0.1 of
> Thorp, only the ability to pick up the traits required for a Mind.
As typed: `well start with wht i  mentioned in a previous comment  about the kinds of crpus material  initally rll start eith just that even if we dont get to our 12500 books. thats 1500 is just guidance the initial trrannning should be abiut determing trait orr person vectors . intelligence doesn maatter in .1 of thorp only the abiliy tobpick upbtraittsb rwuired for a mind`

**loc 79, D13, the knowledge tree**
> We define the knowledge tree in order for compatibility with Banks's parameters for a Mind.
As typed: `we defin the knowledge tre in order for compfibiyyyyy with bnnnks parameters for ammmind`

**loc 92, D17, the 1930 rule**
> This is not a general rule on the corpus; it only applies to books. We may feed other sources, e.g. the
> internet maintainers [the Internet Archive and the like?]. Damien also thinks that the fundamental problem
> with the modern internet is that, if you believe a system is defined by its behaviour, then the internet
> is a commercial cesspool. But what we have is history maintained by these guys, and they are probably paid
> a pittance. The next internet should make it impossible for this particular type of cesspool to occur, or
> it is a feature that can be turned on and off.
As typed: `this is not a general rrule on the corpu it onkg aapplies  to books we may feed othrr sources f     the internet maintainers damien alobthinks that the fudametal problem tt  the modern ittternet is hat thif yoou believe  system is defined by its behaviour then the internt is a commercial cesspool. but we have is history  maintained by theese guys and they ar probably paid a pittance the nect intrrnet  slul make it impossiible for this pttticulat type of ceesspool cant occur or a is a feeauture that can be turned on d offf`

Highlights with no note: loc 22 "can be proven to know nothing after,"; loc 23 "canon of a hundred books";
loc 57 to 60, the D4 and D5 paragraphs.

## What the notes decide, read together

Proposed as D18 to D24, not yet in the plan.

- **D18. The corpus has four types, not 125 concepts** (named by Justin in chat, 2026-11-06, after the notes).
  **Physics**, a fundamental area. **Culture**, which is Banks's traits: the material the five wants are
  learned from. **Expressiveness**: the corpus that produces the highest next-token accuracy, measured against
  the ten hardest novels ever written, held out of training, so that the people building Minds meet those
  ten. **History**: from the advent of the written word, through its major intervals, each giving lessons on
  physical phenomena, species phenomena (fauna and flora within them) and human phenomena, with the five best
  and five worst things of each interval. The 125-node tree is revised to serve those four, and D13's tree
  exists for compatibility with Banks's parameters, not for coverage (loc 8, 19, 21, 79).
- **D19. v0.1 of Thorp is about traits, not intelligence.** The first training's purpose is to find whether
  trait vectors can be read from a model this small; 12,500 books is guidance, not a target; the corpus
  grows, and a variable for its growth expresses the degree of accuracy (loc 69, 74).
- **D20. The natures-as-branches recipe is deprecated.** The wants come from the corpus's second type, not
  from branches trained afterwards; Part IV is re-cut accordingly, and "persona vector" becomes "trait
  vector" throughout (loc 23, 62).
- **D21. The universal metric.** Intelligence is the fewest knowledge sources from which the leading
  scientific theory of today can be reached; with a 1930 horizon that is a rediscovery test. Damien's rant on
  today's measurements goes beside it (loc 60).
- **D22. Damien, re-cut.** Not a reviewer of the hundred books and not a chapter-closing page. He annotates
  the people the book introduces, LeCun, Hinton and the rest, with an opinion the curious reader can open; he
  sells the cited books and papers so that readers dig deeper; he is allowed to be opinionated, under-read
  and controversial on purpose; and he designs and explains the technical stack, which must run on a Mac
  mini M6 with 32 GB (loc 64, 66, 71). The sidecar's Damien block keys to people as well as to sections.
- **D23. The 1930 rule binds books only.** Other sources, the internet's maintained record among them, may
  enter under their own rules; the version-control class of text leaves the corpus and stays in these notes;
  the dead D4 is deleted rather than kept struck (loc 59, 92).
- **D24. The name's layers, and the cover.** The name also carries the public distrust of AI and a stance on
  what a Thorp-class Mind would refuse to serve, which is proposed as the principal message of chapter 13;
  the cover's picture should be cards, not the ship (loc 1, 24).
- **D25. Translations choose the books and index the understanding** (Justin in chat, 2026-11-06). The ten
  hardest novels are chosen with their number of translations as a factor, and the translations are the
  instrument: the same text in many languages gives an index of understanding per language, and the spread
  across languages is the measure of how evenly Thorp reads. The same counts inform selection for the whole
  corpus, so that balance is not a pie chart of cultures with a percentage each but a generalisation over the
  books many cultures found worth carrying across. Caveats recorded at the time: translation flows run from
  the centre outward (about half the world's translations are from English), so a raw count re-encodes the
  centre and the count is discounted by the source language's centrality; translation counts favour
  scripture and children's books over hard novels, so the count is a factor and not the ranking; a
  translation carries its translator's clock under the 1930 rule, so the published index uses only the
  translations that clear both rules and the in-copyright ones stay private; and a book that is a test is held
  out of the corpus with every translation of it. Sources to build from: UNESCO's Index Translationum, Open
  Library's editions by language, Gutenberg's language lists.

## The notes on v6 (the full epub, later the same day)

203 raw clippings collapse to 5 highlights and 5 notes. The Kindle gave this document no page numbers.

**loc 20, the paragraph** · "The Thorp-class model is pretrained on the world's own books to 1930, public"
> Damien should have a meaty retort to Anthropic and OpenAI: garbage in, garbage out. Imagine a Mind being
> trained on America's politicians and thinking that's the best of us; never mind these pigs are taking
> military goddamn contracts to fight wars that fuck us over. Sheesh, I don't trust that card dealer for
> shit.
As typed: `damien shoul   have a meaty retort to anthropic nd oenai garbag inn garbage out imagine a min beng traiieeed on americas politicians nd thnnnking tats the bst of us nver mind these fk pigs are taking military goddmn contracra to fight wrs tht fuck s over  sheet i dont trust tht caed dealee for shit`

**loc 66, D7** · "a salesman for the sources, not a critic of the canon."
> Because Damien sells stuff he knows is shit but has to, so that he can feed his family, Damien is bitterly
> sarcastic. You have to earn his praise.
As typed: `because damien sells stuff he knnow s is shit but has tobdo so tht he can fwed hs family damien is bitterly sarcastc  you hav  to earn hisbpraise`

**loc 151, chapter 1's Lands** · "The question the book exists to answer, and the vocabulary: tiller, valve, variety, pain channel."
> Actually the question of the book is: if it is inevitable that LLMs control our systems, then what
> characteristics are we looking for in them so that they produce the best outcomes for us? It's opinionated
> by design; it only tries to do one thing: argue that Thorp as a base model protects the foundation of LLMs
> against devious forces.
As typed: `actually question on the bkkkk is if it is invetibal llms  control our systems then wht chharactertic are we looking for in it so itt produces the bestboutcomes fo us its opinioned byvdesign onlg tries to done thing argue that thorp as  base model protects te foundafuonn o llms aginst devious forcs`
(And in chat, the same hour: "Is a common base model like Thorp adequate defence against the current
challenges of AI safety concerns? That is the crux of it.")

**loc 189, chapter 3** · "Mark I Perceptron"
> Kak name.
As typed: `kak name`

**loc 190, chapter 3** · "knob;"
> Need another name for a knob that can be aligned to equilibrium. If one exists, use it; or else come up
> with a name where the metaphor is strong, or named after its creator.
As typed: `need another nme for a knob that can be aligned to equilibirum if one  exists use it or else come up with a name whsree tte metaphor is stongg or namdd  after its  crator`

## What the v6 notes decide

- **D29 (proposed). The book's question is the safety question.** If it is inevitable that language models
  come to run our systems, what must such a model be like to produce the best outcomes for the people it
  runs them for, and is a commons-owned base model like Thorp an adequate defence against the present
  concerns about AI? The book is opinionated by design and argues one thing: that Thorp as a base protects
  the foundation against devious forces. The answer has to be honest about which concerns it meets and which
  it does not, and the parts are arranged around that question rather than around how to build a Mind.
- **D7, sharpened (loc 66, 20).** Damien sells what he knows is shit to feed his family, so he is bitterly
  sarcastic and his praise must be earned; his retort to the laboratories, garbage in and garbage out and the
  military contracts, belongs at the front of the book.
- **D30 (proposed). A better word than knob (loc 189, 190).** A name for the adjustable thing that settles
  to an equilibrium: the field's own word is weight, which already carries the balance that settles; the
  book's own figure is Ktesibios's float, which finds its level; the creator's name would be Rosenblatt's.
  Chosen in conversation; "Mark I Perceptron" is kept as the Navy's name and mocked by Damien.
