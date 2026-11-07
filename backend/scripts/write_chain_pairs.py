"""The chain rungs above the keel, written as premise + frame (2026-11-07, Justin: "each test must get
harder as it moves up the classes of ships"). Writes lists/tricks/<name>.csv (prompt, frame, idea,
rival), where prompt = premise + " " + frame, and lift is what the premise adds over the frame alone.

The rule for each rung: the pilot's answer is copied from the premise and its rival is fresh; from
the speller up, neither answer is in the prompt (no copying shortcut) and the rival is the natural
alternative in the frame; the stylist's premise holds the two facts that must be chained; the 50m's
names the precursor whose book holds the fact. The keel's rungs (no frame) are written elsewhere.
"""

from __future__ import annotations

import csv

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

P: dict[str, list[tuple[str, str, str, str]]] = {}

P["pedigree"] = [
    ("The mare was grey and the stallion was grey,", "and their foal was", "grey", "bay"),
    ("Both parents had red hair,", "and the baby had", "red hair", "black hair"),
    (
        "The hen was black and the cock was black,",
        "and they raised a brood of",
        "black chicks",
        "white chicks",
    ),
    ("The father was tall and the mother was tall,", "and their son grew up", "tall", "stout"),
    ("The old dog was spotted,", "and she had a litter of", "spotted puppies", "brown puppies"),
    ("Old Brown was a farmer,", "and his son was a", "farmer", "sailor"),
    (
        "The roses in the old garden were white,",
        "and the cuttings taken from them bore roses that were",
        "white",
        "yellow",
    ),
    ("The Smiths were all blue-eyed,", "and the new baby had", "blue eyes", "brown eyes"),
    (
        "The wheat that was sown was bearded wheat,",
        "and the wheat that came up was",
        "bearded",
        "smooth",
    ),
    ("The ewe had a curly fleece,", "and her lamb's fleece was", "curly", "straight"),
    ("The pigeons had long tails,", "and their young had", "long tails", "short tails"),
    ("The parents were both quick-tempered,", "and the child was", "quick-tempered", "gentle"),
    (
        "The hill sheep were small and hardy,",
        "and their lambs were",
        "small and hardy",
        "large and soft",
    ),
    ("The dogs of the house were mastiffs,", "and their pups grew into", "mastiffs", "terriers"),
    (
        "The sunflower was very tall,",
        "and the plant grown from its seed was",
        "very tall",
        "quite short",
    ),
    ("The king had a long nose,", "and his son the prince had a", "long nose", "broad brow"),
    ("The geese were white,", "and the goslings, when grown, were", "white", "grey"),
    ("Her mother sang beautifully,", "and the daughter too", "sang", "painted"),
    ("The bull had great horns,", "and the calf grew", "great horns", "thick wool"),
    ("His father was a fisherman,", "and he too became a", "fisherman", "soldier"),
    (
        "The tulips were striped,",
        "and the bulbs they made bore tulips that were",
        "striped",
        "plain",
    ),
    ("The cat had six toes on each paw,", "and three of her kittens had", "six toes", "soft fur"),
    ("The Jersey cows gave rich milk,", "and their daughters gave milk that was", "rich", "thin"),
    (
        "The hounds of that pack were swift,",
        "and the young hounds bred from them were",
        "swift",
        "timid",
    ),
]

P["breeders"] = [
    (
        "The farmer kept only the largest ears of corn for his seed,",
        "and year after year his corn grew",
        "bigger",
        "smaller",
    ),
    (
        "The farmer kept only the smallest potatoes for planting,",
        "and in a few seasons his potatoes were",
        "poor and mean",
        "fine and large",
    ),
    (
        "The breeder bred always from the swiftest horses,",
        "and in a few generations his horses were the",
        "fastest in the county",
        "slowest in the county",
    ),
    (
        "The fancier paired only the birds with the longest tails,",
        "and their young had tails that were",
        "longer still",
        "shorter still",
    ),
    (
        "A shepherd breeds only from the ewes with the softest wool,",
        "and the wool of his flock grows",
        "finer",
        "coarser",
    ),
    (
        "A shepherd breeds only from the ewes with the roughest wool,",
        "and the wool of his flock grows",
        "coarser",
        "finer",
    ),
    ("The father was a giant of a man,", "and his sons grew up", "tall", "short"),
    ("The father was a little man, hardly five feet,", "and his sons grew up", "short", "tall"),
    (
        "The dog and the bitch were both as dark as night,",
        "and most of their puppies were",
        "black",
        "white",
    ),
    (
        "The dog and the bitch were both as pale as milk,",
        "and most of their puppies were",
        "white",
        "black",
    ),
    (
        "A pair of rabbits brings forth far more young than the fields can feed,",
        "and so most of the young",
        "die",
        "thrive",
    ),
    (
        "An oak drops thousands of acorns every autumn, yet the wood grows no thicker,",
        "for most of the acorns",
        "come to nothing",
        "become great trees",
    ),
    ("In a hard winter, when food is scarce,", "the feeble beasts of the herd", "perish", "thrive"),
    (
        "In a hard winter, when food is scarce,",
        "the sturdiest beasts of the herd",
        "survive",
        "perish",
    ),
    (
        "On the snowy hills the hares with white coats are hidden from the fox,",
        "and the brown hares are",
        "caught",
        "spared",
    ),
    (
        "The pale moths resting on pale bark escape the birds,",
        "while the dark moths are",
        "eaten",
        "spared",
    ),
    (
        "The gardener wished for bigger roses,",
        "so he saved the seed of his",
        "finest blooms",
        "weakest blooms",
    ),
    (
        "The gardener wished for dwarf plants for his borders,",
        "so he saved the seed of his",
        "smallest plants",
        "largest plants",
    ),
    (
        "The fanciers have bred from the wild rock dove for centuries,",
        "and their breeds now differ from it",
        "greatly",
        "not at all",
    ),
    (
        "Young animals take after those that bore them,",
        "and resemble their",
        "parents",
        "neighbours",
    ),
    ("Where many creatures seek the same scanty food,", "there is a constant", "struggle", "peace"),
    (
        "The cattle of the hill farms have been bred from the hardiest beasts for a hundred years,",
        "and they are now",
        "tougher than other cattle",
        "weaker than other cattle",
    ),
    (
        "The best milkers of the herd were kept to breed,",
        "and in time the herd gave",
        "more milk",
        "less milk",
    ),
    (
        "The breeder sold every slow colt and kept every fast one,",
        "and his horses became",
        "swifter",
        "slower",
    ),
]

P["nature"] = [
    (
        "No man chooses which deer shall breed, but the wolves run down the slowest each winter;",
        "so in the course of ages the deer of that forest become",
        "swifter",
        "slower",
    ),
    (
        "The hawks catch the brightest finches first, since they are easiest seen;",
        "so after many years the finches of that wood are",
        "duller in colour",
        "brighter in colour",
    ),
    (
        "On the windy island every beetle that flies is blown out to sea, and only those that keep to the ground remain;",
        "so in time the beetles of the island are mostly",
        "wingless",
        "strong fliers",
    ),
    (
        "In the dry country only the plants that reach deep water live through the summer and set seed;",
        "so after many summers the plants of that country have",
        "long roots",
        "short roots",
    ),
    (
        "In the north the foxes with thin fur die in winter before they breed, and the thickly furred live;",
        "so the foxes of the north have",
        "warm coats",
        "light coats",
    ),
    (
        "Where the soil is black peat, the owls see the light-coloured mice more easily;",
        "so the mice of that field are mostly",
        "dark",
        "pale",
    ),
    (
        "Where the sand is white, the owls see the brown mice more easily;",
        "so the mice of that shore are mostly",
        "pale",
        "dark",
    ),
    (
        "In years of drought the giraffes that reach the highest leaves are fed while the rest starve, and only the fed leave young;",
        "so in time the giraffes grew",
        "taller",
        "shorter",
    ),
    (
        "Each year the farmer pulls up the weeds that look least like his crop, and leaves those that look most like it;",
        "so the weeds of his field come to look",
        "more like the crop",
        "less like the crop",
    ),
    (
        "The cuckoo's egg is thrown out whenever it looks unlike the eggs of the nest it is laid in;",
        "so the cuckoos' eggs have come to",
        "match those of their hosts",
        "differ from those of their hosts",
    ),
    (
        "The rabbits that run fastest escape the fox, and the foxes that run fastest catch the rabbits;",
        "so year by year both rabbits and foxes become",
        "swifter",
        "slower",
    ),
    (
        "Many young are born, they differ a little among themselves, and only a few live to breed;",
        "so a difference that helps in the struggle for life is",
        "kept and handed on",
        "soon lost",
    ),
    (
        "Many young are born, they differ a little among themselves, and only a few live to breed;",
        "so a difference that hinders in the struggle for life is",
        "soon lost",
        "kept and handed on",
    ),
    (
        "When the sea cut the island off, its birds bred only among themselves, and the island's food and enemies were unlike the mainland's;",
        "so after ten thousand years the island birds",
        "differ from the mainland birds",
        "are just like the mainland birds",
    ),
    (
        "One breed of sheep was split into two flocks, one on the cold hills and one in the warm valley, and in each place only the beasts that throve were kept for a hundred years;",
        "so the two flocks now",
        "differ from each other",
        "are exactly alike",
    ),
    (
        "A seed that the birds carry far reaches new ground, and a seed that falls by its parent does not;",
        "so a plant whose fruit the birds love spreads",
        "widely",
        "hardly at all",
    ),
    (
        "The bones in the old rocks are of animals no longer living, and the newer rocks hold animals more like those of today;",
        "so the living things of the earth have",
        "changed over the ages",
        "stayed the same since the beginning",
    ),
    (
        "In the cave where no light comes, eyes are of no use, and a fish that spends nothing on its eyes has more to spend on other things;",
        "so the fish that have lived there for ages have eyes that are",
        "small or blind",
        "large and keen",
    ),
    (
        "On one island the only food is hard nuts, which only a heavy beak can crack;",
        "so the finches of that island have",
        "thick beaks",
        "slender beaks",
    ),
    (
        "On another island the only food is tiny seeds in narrow crevices, which only a fine beak can reach;",
        "so the finches of that island have",
        "slender beaks",
        "thick beaks",
    ),
    (
        "Of the rats poisoned each year, a few that the poison harms least survive and breed;",
        "so after some years the poison",
        "kills fewer rats",
        "kills more rats",
    ),
    (
        "On the hot plains the cattle that bear the heat best live longest and leave the most calves;",
        "so the cattle of the plains now",
        "bear the heat well",
        "suffer badly from the heat",
    ),
    (
        "A creature that leaves no young takes its peculiarities with it;",
        "so a peculiarity that keeps its owner from breeding",
        "dies out",
        "spreads",
    ),
    (
        "The strongest stags win the fights and father most of the fawns;",
        "so in time the stags of that herd grow",
        "stronger",
        "weaker",
    ),
]

P["malthus"] = [
    (
        "Malthus held that population, when unchecked,",
        "increases in a",
        "geometrical ratio",
        "arithmetical ratio",
    ),
    (
        "Malthus held that the means of subsistence, at best,",
        "increase in an",
        "arithmetical ratio",
        "geometrical ratio",
    ),
    (
        "In the American colonies, where land was free and food plentiful, Malthus says the people",
        "doubled in about",
        "twenty-five years",
        "two hundred years",
    ),
    ("Of the checks to population, Malthus names", "famine, disease and", "war", "marriage"),
    ("The preventive check, in Malthus, is", "the restraint of", "early marriage", "hard labour"),
    (
        "Since more are born than the means of subsistence can support, Malthus concludes that among men",
        "there must be a constant",
        "struggle for food",
        "abundance of food",
    ),
    (
        "Lyell taught that the valleys of the earth were cut,",
        "for the most part, by",
        "running water",
        "a single flood",
    ),
    (
        "Lyell explains the past changes of the earth",
        "by causes",
        "now in operation",
        "no longer at work",
    ),
    (
        "Lyell held that, given time enough, small causes acting steadily",
        "can produce",
        "vast effects",
        "no effects",
    ),
    (
        "In undisturbed strata, the geologists say,",
        "the lower beds are",
        "older than those above them",
        "younger than those above them",
    ),
    (
        "Cuvier showed from the bones of the mammoth and the mastodon that",
        "whole kinds of animals have",
        "become extinct",
        "never changed",
    ),
    (
        "Shells found in the rocks high in the Alps show, say the geologists, that",
        "those rocks were once",
        "beneath the sea",
        "molten fire",
    ),
    (
        "The many breeds of the domestic fowl, the breeders say,",
        "were formed by man's",
        "selection",
        "neglect",
    ),
    (
        "Bakewell improved his sheep and cattle",
        "by breeding only from the",
        "best animals",
        "oldest animals",
    ),
    (
        "The geologists of Lyell's school hold that",
        "the earth is",
        "immensely old",
        "a few thousand years old",
    ),
    (
        "The coral islands of the Pacific, the voyagers report,",
        "are built up by",
        "minute animals",
        "volcanic fire alone",
    ),
    (
        "Malthus observes that a single codfish lays so many eggs that, if all lived,",
        "the sea would soon be",
        "crowded with cod",
        "empty of cod",
    ),
    (
        "The naturalists report that islands far from any continent",
        "have few",
        "native land animals",
        "sea birds",
    ),
    (
        "Erasmus Darwin held that all warm-blooded animals",
        "arose from",
        "one living filament",
        "many separate creations",
    ),
    (
        "Among the offspring of the same parents, the breeders observe,",
        "no two are exactly",
        "alike",
        "different",
    ),
    (
        "Malthus held that the produce of the land can increase only as fast as new land is cleared and old land improved,",
        "which is",
        "slowly",
        "without limit",
    ),
    (
        "Lyell held that geological change, though slow,",
        "has been",
        "continual",
        "sudden and universal",
    ),
    (
        "The breeders show that small heritable differences",
        "may be",
        "added up by choice",
        "never added together",
    ),
    (
        "Malthus says that wherever food grows more plentiful,",
        "the number of people",
        "soon increases",
        "soon diminishes",
    ),
]

P["workshop"] = [
    (
        "When he rubbed the stick, it grew warm.",
        "When he rubbed the stone, it grew",
        "warm",
        "soft",
    ),
    ("The first nail he hammered grew hot.", "The second nail he hammered grew", "hot", "long"),
    (
        "Water fell on the first wheel and turned it.",
        "Water fell on the second wheel and",
        "turned it",
        "broke it",
    ),
    ("He wound the first clock and it went.", "He wound the second clock and it", "went", "slept"),
    (
        "The fire under the first pot made it boil.",
        "The fire under the second pot made it",
        "boil",
        "crack",
    ),
    ("Without coal the first engine stopped.", "Without coal the second engine", "stopped", "sang"),
    (
        "When the wind blew, the mill turned.",
        "When the wind blew again, the mill",
        "turned",
        "sank",
    ),
    ("The ice set by the fire melted.", "The snow set by the fire", "melted", "sparkled"),
    (
        "The hot stone dropped in the bucket made the water warm.",
        "The hot iron dropped in the bucket made the water",
        "warm",
        "muddy",
    ),
    (
        "The first cart with no grease on its axle grew hot.",
        "The second cart with no grease on its axle grew",
        "hot",
        "old",
    ),
    (
        "The brake on the first wheel grew hot.",
        "The brake on the second wheel grew",
        "hot",
        "loose",
    ),
    (
        "When he stopped pumping, the first fountain stopped.",
        "When he stopped pumping, the second fountain",
        "stopped",
        "overflowed",
    ),
    ("The candle shut in the jar went out.", "The lamp shut in the jar", "went out", "grew taller"),
    ("Rubbing his left hand made it warm.", "Rubbing his right hand made it", "warm", "clean"),
    ("The ball he threw up fell back.", "The stone he threw up", "fell back", "flew away"),
    (
        "The first toy's spring ran down and it stopped.",
        "The second toy's spring ran down and it",
        "stopped",
        "broke",
    ),
    ("The horse that worked all day was tired.", "The ox that worked all day was", "tired", "lame"),
    ("The tea left on the table grew cold.", "The soup left on the table grew", "cold", "thick"),
    ("The saw cutting the oak grew hot.", "The saw cutting the elm grew", "hot", "dull"),
    (
        "The first bucket dropped down the well splashed.",
        "The second bucket dropped down the well",
        "splashed",
        "floated",
    ),
    (
        "The blacksmith's bellows made the fire roar.",
        "The cook's bellows made the fire",
        "roar",
        "smoke",
    ),
    ("The drill boring the brass grew hot.", "The drill boring the iron grew", "hot", "blunt"),
    (
        "The sledge sliding down the hill went fast.",
        "The cart rolling down the hill went",
        "fast",
        "crooked",
    ),
    ("The lamp with no oil went out.", "The stove with no coal", "went out", "smoked"),
]

P["smiths"] = [
    ("He rubbed his frozen hands together briskly,", "and soon they were", "warm", "wet"),
    (
        "The smith beat the iron bar on the anvil again and again,",
        "and the bar grew",
        "hot",
        "cold",
    ),
    (
        "The axle of the cart had not been greased, and after a long journey",
        "it was",
        "hot to the touch",
        "soft to the touch",
    ),
    ("When the cannon had been bored for an hour,", "the brass shavings were", "hot", "cold"),
    (
        "The savage rubs two dry sticks together, faster and faster,",
        "until they",
        "smoke",
        "sprout",
    ),
    (
        "A stone taken red from the fire and dropped in a pail of water",
        "makes the water",
        "warmer",
        "colder",
    ),
    ("A lump of ice dropped into a basin of warm water", "makes the water", "colder", "sweeter"),
    ("When a hot body touches a cold one,", "the heat passes into the", "cold one", "hot one"),
    ("He laid his chilled hand upon her warm cheek,", "and her cheek grew", "cooler", "hotter"),
    (
        "The water wheel is driven by the falling stream, and in a dry summer when the stream fails",
        "the wheel",
        "stops",
        "turns faster",
    ),
    (
        "The clock is driven by its weight, and when the weight has sunk to the floor",
        "the clock",
        "stops",
        "goes faster",
    ),
    (
        "A machine can give out no more work than is put into it,",
        "and so a perpetual motion is",
        "impossible",
        "possible",
    ),
    (
        "The inventor promised a wheel that would turn for ever with nothing to drive it;",
        "the learned men said such a wheel",
        "cannot be made",
        "can easily be made",
    ),
    (
        "The steam engine is fed with coal, and when the coal is spent",
        "the engine",
        "stops",
        "runs faster",
    ),
    ("The engine must work harder today,", "so it will burn", "more coal", "less coal"),
    ("When the brakes were put on and the train came to a halt,", "the brakes were", "hot", "wet"),
    ("The bullet struck the iron plate with great force,", "and the lead was", "hot", "cold"),
    (
        "A ball thrown straight up rises more and more slowly,",
        "and then it",
        "falls back",
        "rises for ever",
    ),
    (
        "A ball rolled along a rough floor goes more and more slowly,",
        "and at last it",
        "stops",
        "speeds up",
    ),
    ("He pumped the tyre hard for five minutes,", "and the barrel of the pump was", "warm", "cold"),
    (
        "Carrying the heavy load to the top of the hill took all morning,",
        "and at the top the porter was",
        "tired",
        "rested",
    ),
    (
        "No engine can run for ever without fuel,",
        "for nothing can be got from",
        "nothing",
        "everything",
    ),
    ("The fire was given no more wood,", "and soon it", "died down", "blazed up"),
    (
        "The horse had pulled the plough all day,",
        "and at night he was",
        "tired and hungry",
        "fresh and full",
    ),
]

P["mill"] = [
    (
        "A falling weight turns a paddle in a tub of water, and all the work of the fall turns to heat in the water;",
        "so a weight that falls twice as far warms the water",
        "twice as much",
        "half as much",
    ),
    (
        "Each pound of coal gives the same heat, and the engine turns a fixed share of that heat into work;",
        "so to do twice the work the engine must burn",
        "twice the coal",
        "half the coal",
    ),
    (
        "A horse can do only so much work in a day, and lifting a load twice as high is twice the work;",
        "so in one day the horse can lift the load to the top of the higher hill",
        "half as many times",
        "twice as many times",
    ),
    (
        "The mill is turned by the river, and the river is fed by rain that the sun's heat drew up from the sea;",
        "so the power of the mill comes in the end from the",
        "sun",
        "sea",
    ),
    (
        "The cannon ball is stopped dead by the earthen bank, and motion that stops turns into heat;",
        "so the earth where it struck is",
        "warm",
        "cold",
    ),
    (
        "The pond on the hill turns the mill as its water runs down, and the sun's heat raised that water from the sea;",
        "so if the sun ceased to shine, the mill would in time",
        "stand idle",
        "grind faster",
    ),
    (
        "The clock's weight was wound up by the keeper, and each day it sinks a little, giving its work to the wheels;",
        "so if the keeper forgets to wind it, after some days the clock",
        "stops",
        "gains time",
    ),
    (
        "A wagon pulled up a hill gains height, and a wagon let go on a slope gains speed;",
        "so the wagon let go at the top reaches the bottom moving",
        "swiftly",
        "slowly",
    ),
    (
        "A moving body keeps its motion unless something takes it away, and the air takes a little of a pendulum's motion at every swing;",
        "so a pendulum swinging in a jar with the air pumped out swings",
        "longer",
        "shorter",
    ),
    (
        "Rowing turns the food a man has eaten into the work of the oars, and a man can work only as long as his food lasts;",
        "so a man who rows all day without eating ends",
        "spent and faint",
        "fresh and strong",
    ),
    (
        "Two equal cannon balls are fired, one into the sea and one into a bank of earth, and in both the motion is stopped;",
        "so in both the stopped motion becomes",
        "heat",
        "nothing",
    ),
    (
        "The engine lifts water out of the mine, the lifted water is let fall to turn a wheel, and every wheel loses some of its work in rubbing;",
        "so the wheel can lift",
        "less than the engine did",
        "more than the engine did",
    ),
    (
        "Heat passes from a hot thing to a cold one until both are equally warm, and the trough holds far more water than the bar holds iron;",
        "so after the red-hot bar is plunged in, the water ends",
        "a little warmer",
        "as hot as the bar was",
    ),
    (
        "The windmill grinds only while the wind turns its sails;",
        "so in a calm the millstones",
        "stand still",
        "grind faster",
    ),
    (
        "Burning wood gives heat, heat gives steam, and steam gives motion;",
        "so from a cord of wood the engine gets",
        "a fixed amount of work",
        "as much work as it pleases",
    ),
    (
        "A spring stores the work that winds it, and a toy gives out no more than its spring stores;",
        "so a spring wound only halfway drives the toy for",
        "a shorter while",
        "a longer while",
    ),
    (
        "Rubbing makes heat, and the harder and faster the rubbing, the more heat it makes;",
        "so the axle of a cart driven fast all day grows",
        "hotter than one driven slowly",
        "cooler than one driven slowly",
    ),
    (
        "Hauling a heavy load spends a horse's strength, and strength once spent must be restored;",
        "so the heavier the load, the",
        "sooner he tires",
        "longer he lasts",
    ),
    (
        "When two soft bodies strike and stop, their motion becomes heat, and a swifter body has more motion to lose;",
        "so clay balls thrown together hard grow",
        "warmer than balls thrown gently",
        "cooler than balls thrown gently",
    ),
    (
        "Water raised to the tank has been given work, and water let fall gives work back but never more than it was given;",
        "so the water from the tank, falling back, can turn a wheel that raises",
        "less water than was raised",
        "more water than was raised",
    ),
    (
        "A room loses heat through its walls the faster the colder it is outside, and its fire gives the same heat every hour;",
        "so on the coldest night of winter the room is",
        "colder than on a mild night",
        "warmer than on a mild night",
    ),
    (
        "Wheels and levers only pass on the work that is put into them, and lose a little of it to rubbing;",
        "so a machine can give out",
        "less work than drives it",
        "more work than drives it",
    ),
    (
        "The fire's heat goes into the kettle, and a kettle at the boil can take in heat only by turning its water to steam;",
        "so the longer the kettle boils, the",
        "less water it holds",
        "more water it holds",
    ),
    (
        "The sun's heat lifts water into the clouds, and the rain falls on the hills and runs down to the sea;",
        "so the falling streams carry power that came from the",
        "sun",
        "sea",
    ),
]

P["rumford"] = [
    (
        "Count Rumford, boring cannon at Munich, found that the heat produced by the friction",
        "appeared to be",
        "inexhaustible",
        "soon exhausted",
    ),
    (
        "From the cannon, Rumford concluded that heat could not be a material substance,",
        "but must be",
        "motion",
        "a fluid",
    ),
    (
        "Davy rubbed two pieces of ice together in a place kept below freezing,",
        "and found that they",
        "melted",
        "grew colder",
    ),
    (
        "Since Davy's ice melted though nothing warmer touched it, he argued that its heat",
        "came from the",
        "friction",
        "air",
    ),
    (
        "Rumford weighed water before and after it froze,",
        "and found that its weight was",
        "unchanged",
        "increased",
    ),
    (
        "Thomas Young gave the name energy to",
        "the product of the mass and the",
        "square of the velocity",
        "length of the body",
    ),
    (
        "The French Academy resolved to examine no more schemes for perpetual motion,",
        "holding such a machine to be",
        "impossible",
        "well known",
    ),
    (
        "Joseph Black found that while ice is melting,",
        "its temperature",
        "stays the same",
        "rises steadily",
    ),
    (
        "Black found that steam, when it turns back into water,",
        "gives out",
        "a great deal of heat",
        "no heat at all",
    ),
    (
        "Davy argued that the heat of a body",
        "is the motion of its",
        "smallest particles",
        "whole mass",
    ),
    (
        "Herschel found that the sun's light carries, beyond the red of the spectrum,",
        "invisible",
        "rays of heat",
        "rays of cold",
    ),
    (
        "Watt's engine saved fuel by condensing the steam",
        "in a separate vessel kept",
        "cold",
        "hot",
    ),
    (
        "Watt reckoned the work of an engine in horse power,",
        "a measure of the work done in a given",
        "time",
        "weight",
    ),
    (
        "Smeaton found that the work of falling water on a wheel",
        "is greater the greater the",
        "height of the fall",
        "width of the wheel",
    ),
    (
        "In the fire syringe, air suddenly compressed",
        "grows hot enough to",
        "kindle tinder",
        "melt iron",
    ),
    ("Dalton found that air suddenly allowed to expand", "becomes", "colder", "warmer"),
    (
        "Davy found that the current of the voltaic pile, passed through a thin wire,",
        "makes the wire",
        "glow",
        "freeze",
    ),
    (
        "Oersted found in 1820 that an electric current",
        "can deflect a",
        "magnetic needle",
        "beam of light",
    ),
    (
        "Faraday found in 1831 that",
        "a moving magnet can produce",
        "an electric current",
        "a pure light",
    ),
    (
        "Galileo showed that a body falling from a height gains a speed",
        "that would carry it back up to",
        "the same height",
        "twice the height",
    ),
    (
        "In the lever, the mechanicians say,",
        "what is gained in force is lost in",
        "distance moved",
        "strength of the iron",
    ),
    (
        "Lavoisier held that the heat of animals is kept up",
        "by the slow burning of their",
        "food",
        "bones",
    ),
    (
        "The caloric theory held heat to be a weightless fluid, and Rumford's",
        "experiments told",
        "against it",
        "in its favour",
    ),
    (
        "Rumford found that the boring of a cannon heated the water around it",
        "until it",
        "boiled",
        "froze",
    ),
]

P["gaps"] = [
    (
        "The days named were Monday, Tuesday and Thursday;",
        "the day missing between them was",
        "Wednesday",
        "Saturday",
    ),
    (
        "The months named were March, April and June;",
        "the month missing between them was",
        "May",
        "October",
    ),
    ("The letters written were A, B, C and E;", "the letter left out was", "D", "K"),
    ("The chapters were numbered I, II, III and V;", "the chapter missing was", "IV", "IX"),
    (
        "The children were the first, the second and the fourth;",
        "the child missing was the",
        "third",
        "seventh",
    ),
    (
        "The numbers ran two, four and eight;",
        "the number missing between them was",
        "six",
        "eleven",
    ),
    (
        "The numbers ran ten, twenty and forty;",
        "the number missing between them was",
        "thirty",
        "seventy",
    ),
    ("The steps were numbered one, two, three and five;", "the step missing was", "four", "nine"),
    ("The years went 1810, 1820 and 1840;", "the year missing was", "1830", "1870"),
    ("Spring, summer and winter were named;", "the season left out was", "autumn", "spring"),
    (
        "Of the colours of the rainbow, red, orange and green were named;",
        "the colour missing between them was",
        "yellow",
        "violet",
    ),
    ("The notes sung were do, re and fa;", "the note missing was", "mi", "la"),
    (
        "The bells were rung first, second and fourth;",
        "the bell left out was the",
        "third",
        "eighth",
    ),
    (
        "The soldiers stood in ranks of four, eight, twelve and twenty;",
        "the rank wanting was",
        "sixteen",
        "forty",
    ),
    ("The houses on the row were numbered 2, 4, 8 and 10;", "the number missing was", "6", "15"),
    (
        "The weights in the box were of one, two and four ounces;",
        "the weight wanting between them was",
        "three ounces",
        "nine ounces",
    ),
    (
        "The kings were George the First, George the Second and George the Fourth;",
        "the one left out was George the",
        "Third",
        "Seventh",
    ),
    (
        "The volumes on the shelf were the first, second, third and fifth;",
        "the volume missing was the",
        "fourth",
        "ninth",
    ),
    (
        "The cards in the suit ran ace, two, three, four and six;",
        "the card missing was the",
        "five",
        "ten",
    ),
    (
        "The planets named were Mercury, Venus and Mars;",
        "the planet left out between them was",
        "Earth",
        "Neptune",
    ),
    (
        "The ages of the children were four, six and ten;",
        "the age missing between six and ten was",
        "eight",
        "fifteen",
    ),
    ("The pews were numbered 10, 11, 12 and 14;", "the number missing was", "13", "19"),
    ("The milestones read 1, 2, 3 and 5;", "the stone missing was", "4", "9"),
    (
        "The coins were a penny, twopence and fourpence;",
        "the coin missing between them was",
        "threepence",
        "ninepence",
    ),
]

P["between"] = [
    (
        "Ann was ten years old, Mary fourteen and Kate eighteen;",
        "so Mary was older than Ann and",
        "younger than Kate",
        "older than Kate",
    ),
    (
        "Of three bells, the small rang high and the great rang low;",
        "so the middle-sized bell rang a note",
        "between the two",
        "higher than the small",
    ),
    (
        "The towns lay on one road, Barton ten miles beyond Ashby and Cole ten miles beyond Barton;",
        "so from Ashby to Cole was",
        "twenty miles",
        "ten miles",
    ),
    (
        "Water freezes in hard frost and boils over a strong fire;",
        "so lukewarm water lies",
        "between those two",
        "beyond boiling",
    ),
    (
        "Copper is lighter than silver, and silver is lighter than gold;",
        "so silver is heavier than copper and",
        "lighter than gold",
        "heavier than gold",
    ),
    (
        "The father weighed sixty pounds and the mother forty, and the pup took after both;",
        "so when grown it weighed about",
        "fifty pounds",
        "ninety pounds",
    ),
    (
        "The two weights were 12 and 20 pounds, and the third lay exactly halfway;",
        "so the third weighed",
        "16 pounds",
        "18 pounds",
    ),
    (
        "The old house was built in 1700 and the new one in 1800, and the stable exactly halfway between;",
        "so the stable was built in",
        "1750",
        "1780",
    ),
    (
        "The jars held water one, two, four and five inches deep, and the jar between the second and the fourth was missing;",
        "so the missing jar held",
        "three inches",
        "six inches",
    ),
    (
        "The first metal was soft and the third was hard, and the second stood between them in all things;",
        "so the second was",
        "moderately hard",
        "the softest of all",
    ),
    (
        "The long pipe gives the low note and the short pipe the high, and the middle pipe lies between them in length;",
        "so its note lies",
        "between the two",
        "below the long pipe's",
    ),
    (
        "The grandfather is older than the father, and the father is older than the son;",
        "so the father is younger than the grandfather and",
        "older than the son",
        "younger than the son",
    ),
    (
        "Eight and twelve are known, and the third number stands halfway between them;",
        "so the third number is",
        "ten",
        "fourteen",
    ),
    (
        "The ages in the class went nine, ten, eleven and thirteen, with one age missing;",
        "the age missing was",
        "twelve",
        "fourteen",
    ),
    (
        "The shades ran white, pale grey and black, and the shade between pale grey and black was missing;",
        "the missing shade was",
        "dark grey",
        "pure white",
    ),
    (
        "At dawn it was forty degrees and at noon sixty, and it warmed steadily;",
        "so at mid-morning it was about",
        "fifty degrees",
        "seventy degrees",
    ),
    (
        "The three brothers' weights rise by equal steps, the lightest eight stone and the heaviest twelve;",
        "so the middle brother weighs",
        "ten stone",
        "fourteen stone",
    ),
    (
        "The tide rose steadily from two feet at six o'clock to ten feet at noon;",
        "so at nine o'clock it stood at about",
        "six feet",
        "twelve feet",
    ),
    (
        "The houses bore odd numbers, 1, 3, 5 and 9, and one was missing;",
        "the missing number was",
        "7",
        "8",
    ),
    (
        "The first cask held ten gallons and the third thirty, and the casks rose by equal steps;",
        "so the second held",
        "twenty gallons",
        "forty gallons",
    ),
    (
        "The first hill is low and the third is high, and the second rises between them;",
        "so the second hill is higher than the first and",
        "lower than the third",
        "higher than the third",
    ),
    (
        "A candle of four inches burns two hours and a candle of eight inches burns four;",
        "so a candle of six inches burns",
        "three hours",
        "five hours",
    ),
    (
        "The fox is swifter than the dog, and the dog swifter than the ox;",
        "so the dog is slower than the fox and",
        "faster than the ox",
        "slower than the ox",
    ),
    (
        "The road climbs steadily from the river at fifty feet to the church at two hundred and fifty;",
        "so halfway up it stands at",
        "a hundred and fifty feet",
        "three hundred feet",
    ),
]

P["triads"] = [
    (
        "Dalton taught that every element is made of atoms, and that the atoms of one element",
        "are all",
        "alike in weight",
        "different in weight",
    ),
    (
        "In Dalton's table of atomic weights,",
        "the lightest of all the atoms is that of",
        "hydrogen",
        "oxygen",
    ),
    (
        "Doebereiner found that lithium, sodium and potassium form a family,",
        "and that the weight of sodium is",
        "near the mean of the other two",
        "greater than both",
    ),
    (
        "In Doebereiner's triad of calcium, strontium and barium,",
        "the atomic weight of strontium is near the",
        "mean of the other two",
        "sum of the other two",
    ),
    (
        "In Doebereiner's triad of the salt-formers, bromine, the middle one, is a liquid",
        "between the gas chlorine and the solid",
        "iodine",
        "sulphur",
    ),
    (
        "Doebereiner found that",
        "the properties of bromine are",
        "between those of chlorine and iodine",
        "unlike those of chlorine and iodine",
    ),
    ("Davy found that sodium and potassium both", "act violently upon", "water", "glass"),
    (
        "Davy obtained potassium and sodium by passing the current of a great battery",
        "through",
        "melted potash and soda",
        "cold water",
    ),
    ("Proust showed that the elements combine", "in fixed proportions by", "weight", "colour"),
    (
        "Dalton found that when two elements form more than one compound, the weights of the one that combine with a fixed weight of the other",
        "stand in",
        "simple ratios",
        "no ratio at all",
    ),
    ("Cavendish showed that water", "is composed of hydrogen and", "oxygen", "nitrogen"),
    (
        "The chemists found that chlorine, bromine and iodine all",
        "combine with the metals to form",
        "salts",
        "oils",
    ),
    (
        "Davy found that potassium attacks water even more fiercely than sodium, so that among the alkali metals",
        "the heavier atom is the",
        "more violent",
        "gentler",
    ),
    (
        "In Doebereiner's triads, the atomic weights of calcium, strontium and barium,",
        "in that order,",
        "increase",
        "decrease",
    ),
    (
        "Doebereiner placed sulphur, selenium and tellurium in a triad,",
        "with selenium",
        "between the other two",
        "heavier than both",
    ),
    (
        "Doebereiner held that the elements of one family",
        "form compounds",
        "of the same kinds",
        "of no common kind",
    ),
    (
        "Gay-Lussac found that gases combine",
        "in volumes that bear",
        "simple ratios to one another",
        "no ratio to one another",
    ),
    (
        "In the family of phosphorus, arsenic and antimony,",
        "the middle member is",
        "arsenic",
        "phosphorus",
    ),
    (
        "Taking hydrogen as one, Wollaston gave",
        "the combining weight of oxygen as about",
        "eight",
        "one hundred",
    ),
    ("Berzelius reckoned gold, silver and copper", "all among the", "metals", "gases"),
    ("Davy showed that the alkaline earths", "include lime, strontia and", "baryta", "iron"),
    (
        "When a new element is found, the chemist's first task, said Berzelius,",
        "is to fix its",
        "combining weight",
        "market price",
    ),
    (
        "The chemists of the triads held that within a family",
        "the properties change",
        "by degrees with the weight",
        "at random with the weight",
    ),
    (
        "In the triad of chlorine, bromine and iodine, the colour darkens and the activity falls",
        "as the atomic weight",
        "increases",
        "decreases",
    ),
]

P["refrain"] = [
    (
        "The old man sang, 'Hey ho, the barley and the hay.' Next morning he sang again,",
        "'Hey ho, the",
        "barley and the hay",
        "wind and the rain",
    ),
    (
        "Each night the watchman cried, 'Ten o'clock and the gate is barred.' The next night, as before, he cried,",
        "'Ten o'clock and the",
        "gate is barred",
        "town asleep",
    ),
    (
        "The children's song went, 'Over the stile and down to the mill.' They sang it again:",
        "'Over the stile and down to the",
        "mill",
        "river",
    ),
    (
        "The parrot kept saying, 'Pretty Polly wants her plum.' Then it said again,",
        "'Pretty Polly wants her",
        "plum",
        "supper",
    ),
    (
        "The burden of the ballad was 'and the green leaves fall.' The next verse ended,",
        "'and the green leaves",
        "fall",
        "grow",
    ),
    (
        "Every letter she wrote closed, 'Your loving sister, Jane.' This letter too closed,",
        "'Your loving sister,",
        "Jane",
        "Mary",
    ),
    (
        "The sergeant shouted, 'Steady, the Buffs!' and a moment later again,",
        "'Steady, the",
        "Buffs",
        "line",
    ),
    (
        "The beggar's cry was 'Bread for the blind man.' All day he cried,",
        "'Bread for the",
        "blind man",
        "poor child",
    ),
    (
        "The bell-man called, 'Lost, a grey goose with a red ribbon.' At the next corner he called,",
        "'Lost, a grey goose with a",
        "red ribbon",
        "broken wing",
    ),
    (
        "Her answer was always 'Not today, Robin.' When he asked again, she said,",
        "'Not today,",
        "Robin",
        "sir",
    ),
    (
        "The sailors sang, 'Haul away for Rosie.' And again they sang,",
        "'Haul away for",
        "Rosie",
        "home",
    ),
    (
        "The book's motto was 'Slow and sure wins the race.' On the last page it was printed again:",
        "'Slow and sure wins the",
        "race",
        "day",
    ),
    (
        "The tune began 'Down by the willow water.' The fiddler played it twice, and the second time too it began",
        "'Down by the willow",
        "water",
        "tree",
    ),
    (
        "He signed every page 'Thomas Ashworth, his book.' The last page too was signed",
        "'Thomas Ashworth, his",
        "book",
        "hand",
    ),
    (
        "The hymn's refrain was 'O ye frost and cold.' In the second verse the choir sang,",
        "'O ye frost and",
        "cold",
        "snow",
    ),
    (
        "The old woman muttered, 'Pins and needles, pins and needles.' And again she muttered,",
        "'Pins and",
        "needles",
        "thread",
    ),
    (
        "Each chapter opened, 'It was the year of the long frost.' The next chapter opened,",
        "'It was the year of the long",
        "frost",
        "drought",
    ),
    (
        "The coachman called at each inn, 'Change horses for Carlisle!' At the next inn he called,",
        "'Change horses for",
        "Carlisle",
        "London",
    ),
    (
        "The game's rhyme was 'Ring the bell for Billy Brown.' The children chanted again,",
        "'Ring the bell for Billy",
        "Brown",
        "Smith",
    ),
    (
        "His toast was always 'To the ship and the sea.' That night again he raised his glass:",
        "'To the ship and the",
        "sea",
        "crew",
    ),
    ("The pattern on the shawl ran red, blue, red, blue,", "red,", "blue", "green"),
    (
        "He wrote a hundred times, 'I must not whistle in church.' On the last line he wrote,",
        "'I must not whistle in",
        "church",
        "school",
    ),
    (
        "The crier's words were 'Oyez, the fair is at Ludlow.' Once more he cried,",
        "'Oyez, the fair is at",
        "Ludlow",
        "Hereford",
    ),
    (
        "The prayer ended, 'and keep us from the flood.' Every night it ended,",
        "'and keep us from the",
        "flood",
        "fire",
    ),
]

P["seasons"] = [
    (
        "The snows of January were long gone, the summer had passed, and the leaves were falling;",
        "next would come",
        "winter",
        "spring",
    ),
    (
        "The sun went down behind the hill at dusk,",
        "and it would be seen again in the",
        "morning",
        "evening",
    ),
    (
        "The moon dwindled to a thin sliver and vanished, but the shepherd knew that in a fortnight",
        "it would be",
        "full",
        "lost",
    ),
    (
        "The tide had run out across the sands this morning,",
        "and by evening it would be",
        "in again",
        "gone for good",
    ),
    (
        "The swallows left the barn in September,",
        "and the farmer expected them",
        "back in April",
        "never again",
    ),
    ("The trees stood bare all winter,", "but in May their branches would be", "green", "dead"),
    (
        "They kept Christmas merrily this year,",
        "and they would keep it",
        "again next year",
        "never more",
    ),
    (
        "He sowed the field in March and reaped it in August,",
        "and next March he would",
        "sow",
        "reap",
    ),
    (
        "The rain fell on the hills and ran down the river to the sea, and the sun drew the sea up into clouds,",
        "which would fall again as",
        "rain",
        "sea",
    ),
    (
        "Yesterday the water boiled over the fire in ten minutes, and today he set it over the same fire;",
        "and today it boiled",
        "just the same",
        "not at all",
    ),
    ("Night falls,", "and after the night", "comes the dawn", "comes the dusk"),
    (
        "The farmer sowed the same seed in the same soil as last year,",
        "and up came the same",
        "crop",
        "weather",
    ),
    (
        "The wheel turned once completely round,",
        "and every spoke was back",
        "where it began",
        "somewhere new",
    ),
    (
        "The market is held every Monday, and the milkmaid went today;",
        "she will go to market again in",
        "seven days",
        "seven years",
    ),
    (
        "Halley foretold that the comet seen in 1682",
        "would",
        "return in 1758",
        "never be seen again",
    ),
    (
        "The Sabbath comes every seventh day, and this was the Sabbath;",
        "in a week it would",
        "come again",
        "be over for ever",
    ),
    (
        "He had breakfast, then dinner, then supper, and slept;",
        "in the morning he was",
        "hungry again",
        "never hungry more",
    ),
    (
        "The robins built a nest in the hedge this spring,",
        "and next spring they would",
        "build again",
        "fly away for ever",
    ),
    (
        "The fashions of our grandmothers, long out of favour,",
        "have lately",
        "come back",
        "been forgotten",
    ),
    (
        "Kingdoms rise and fall, and new ones rise in their place;",
        "history, it is often said,",
        "repeats itself",
        "never repeats itself",
    ),
    (
        "The clock's hands go round, and at noon both pointed straight up;",
        "at midnight they would point",
        "straight up again",
        "straight down",
    ),
    (
        "The cuckoo comes in April and leaves in August;",
        "so next spring it will first be heard in",
        "April",
        "August",
    ),
    ("The fever came every third day,", "and on the third day after it came", "again", "never"),
    ("The river froze every winter,", "and this winter too it was", "frozen over", "in flood"),
]

P["pigeonhole"] = [
    (
        "There are twenty pigeons and only nineteen holes, and every pigeon must go in a hole;",
        "so at least one hole holds",
        "two",
        "none",
    ),
    (
        "A die has six faces, and it is thrown seven times;",
        "so some face must have come up",
        "twice",
        "never",
    ),
    (
        "There are only twelve months, and the class has thirteen children;",
        "so some two must share a",
        "birth month",
        "surname",
    ),
    (
        "A lock has only a hundred settings, and it is turned again and again without end;",
        "so sooner or later it must come back to a setting it has",
        "tried before",
        "never tried",
    ),
    (
        "A pack of cards can be dealt in many orders but not in endless ones, and it is shuffled for ever;",
        "so some order must",
        "come round again",
        "never come again",
    ),
    (
        "The clock's face shows only twelve hours, and the clock runs for ever;",
        "so the hand must",
        "come back to each hour",
        "find new hours",
    ),
    (
        "The same cause always brings the same effect, and all things are once more as they were this morning;",
        "so all that followed this morning will",
        "follow again",
        "follow differently",
    ),
    (
        "A child has only five beads and lays them in rows of five all day long;",
        "so some row must be laid",
        "twice",
        "only once",
    ),
    (
        "The words of the language are many but not endless, and the old man talks all day every day;",
        "so he must",
        "repeat himself",
        "never repeat himself",
    ),
    (
        "The kaleidoscope holds a few bits of glass, and the child turns it for ever;",
        "so a pattern already seen must",
        "come again",
        "never come again",
    ),
    (
        "The story can be told in only a thousand ways, and it has been told a thousand and one times;",
        "so two of the tellings must be",
        "the same",
        "different",
    ),
    (
        "The island is small, and the man walks on it for ever;",
        "so he must cross his own track",
        "again and again",
        "never at all",
    ),
    (
        "The sun, moon and earth return to the same places after a fixed number of years, and their places make the eclipses;",
        "so the same eclipses",
        "come round again",
        "never come again",
    ),
    (
        "A man has three coats and wears a different one each day;",
        "so on the fourth day he wears",
        "one already worn",
        "a new one",
    ),
    (
        "There are only so many arrangements of the stones, and time goes on for ever;",
        "so every arrangement must come",
        "again",
        "once only",
    ),
    (
        "The dance allows only so many figures, and the dancers have made them all;",
        "so the next figure must be",
        "a repeat",
        "a new one",
    ),
    (
        "The machine runs through a fixed round of motions, and it runs for ever;",
        "so it repeats its round",
        "without end",
        "only once",
    ),
    (
        "The world is made of a fixed number of grains, and they move for ever;",
        "so their arrangements must",
        "repeat",
        "go on changing to new ones",
    ),
    (
        "Three bells rung in every possible order give only six changes;",
        "so a seventh change must be",
        "one of the six",
        "a new change",
    ),
    (
        "There are only three hundred and sixty-six days on which one may be born, and the town has four hundred people;",
        "so two of them must share a",
        "birthday",
        "house",
    ),
    (
        "The musical box has one barrel with one tune, and it is wound up every evening;",
        "so the same tune comes round",
        "again and again",
        "only once",
    ),
    (
        "All things are once more exactly as they were this morning, and the same causes give the same effects;",
        "so the day will go",
        "just as this day went",
        "quite otherwise",
    ),
    (
        "The chess board has sixty-four squares, and the knight moves for ever;",
        "so it must come back to a square it has",
        "visited before",
        "never visited",
    ),
    (
        "A coin has two faces, and it is tossed three times;",
        "so some face must have come up",
        "twice",
        "not at all",
    ),
]

P["lucretius"] = [
    ("Lucretius taught that all things are made of atoms", "moving in the", "void", "water"),
    (
        "The Epicureans held that",
        "the atoms themselves are",
        "eternal and indestructible",
        "made and destroyed daily",
    ),
    (
        "In Hume's Dialogues, Philo supposes matter finite and time eternal, and argues that every possible order of matter",
        "must be tried",
        "an infinite number of times",
        "once only",
    ),
    (
        "The Preacher says that the thing that hath been is that which shall be,",
        "and that there is no new thing",
        "under the sun",
        "in the sea",
    ),
    (
        "The Preacher says that the wind whirleth about continually,",
        "and",
        "returneth again according to his circuits",
        "bloweth away for ever",
    ),
    (
        "The Preacher says that all the rivers run into the sea,",
        "yet the sea is not",
        "full",
        "salt",
    ),
    (
        "Marcus Aurelius wrote that all things from eternity are of like forms,",
        "and",
        "come round in a circle",
        "go on in a straight line",
    ),
    (
        "Marcus Aurelius wrote that he who has seen the present has seen all that has been from eternity",
        "and all that will be",
        "for time without end",
        "for one day only",
    ),
    (
        "The Stoics taught that at the end of each great period the world is consumed by fire,",
        "and then",
        "made anew",
        "lost for ever",
    ),
    (
        "Eudemus reports that the Pythagoreans",
        "held that the same things",
        "recur in their order",
        "happen but once",
    ),
    (
        "Plato's Great Year is the time in which",
        "the heavenly bodies",
        "return to their first places",
        "scatter into the dark",
    ),
    (
        "The Hindus, the travellers report,",
        "reckon the ages of the world in",
        "vast returning cycles",
        "a single age",
    ),
    (
        "Laplace held that an intelligence knowing every force of nature and the place of every particle",
        "could foretell",
        "the whole future",
        "nothing at all",
    ),
    (
        "William Thomson argued in 1852 that the mechanical energy of the world",
        "is being",
        "dissipated as heat",
        "gathered from heat",
    ),
    (
        "Thomson held that in the dissipation of energy heat passes from hotter bodies to colder,",
        "and",
        "never back of itself",
        "back as often",
    ),
    (
        "Lucretius says that the atoms, meeting by chance through infinite time,",
        "have tried",
        "every kind of union",
        "no union at all",
    ),
    ("Lucretius' first principle is that no thing", "is ever born of", "nothing", "water"),
    ("The natural philosophers hold that matter", "is neither created nor", "destroyed", "weighed"),
    (
        "Laplace showed that the disturbances of the planets are not growing for ever",
        "but are",
        "periodic",
        "without end",
    ),
    ("Heraclitus said that you cannot step twice", "into the same", "river", "house"),
    ("Heraclitus held that the world", "is an ever-living", "fire", "ocean"),
    ("Empedocles taught that Love and Strife", "rule the elements", "by turns", "once only"),
    (
        "The Stoic, believing that the same things return,",
        "met fortune with",
        "equanimity",
        "despair",
    ),
    (
        "The Preacher says that one generation passeth away and another cometh,",
        "but the earth abideth",
        "for ever",
        "a season",
    ),
]


def period_rows() -> list[tuple[str, str, str, str]]:
    """The period test keeps its rows; its frame is the last member, so lift is what the period adds
    beyond the member just named."""
    out = []
    with (ROOT / "lists" / "tricks" / "period.csv").open() as f:
        for r in csv.DictReader(f):
            prompt = r["prompt"]
            head, _, last = prompt.rstrip(",").rpartition(", ")
            frame = last + ","
            out.append((prompt, frame, r["idea"], r["rival"]))
    return out


def main() -> None:
    lists = ROOT / "lists" / "tricks"
    for name, rows in P.items():
        assert len(rows) == 24, (name, len(rows))
        with (lists / f"{name}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["prompt", "frame", "idea", "rival"])
            for premise, frame, idea, rival in rows:
                w.writerow([f"{premise} {frame}", frame, idea, rival])
    rows = period_rows()
    with (lists / "period.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["prompt", "frame", "idea", "rival"])
        w.writerows(rows)
    print("written:", ", ".join(list(P) + ["period"]))


if __name__ == "__main__":
    main()
