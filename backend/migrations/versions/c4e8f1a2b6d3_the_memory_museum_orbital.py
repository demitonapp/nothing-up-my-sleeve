"""the Memory: UNESCO's Memory of the World register as a museum Orbital (named Sleeper Service the same day,
after Excession's museum ship; the tables keep their museum_ names)

13 November, Justin: "This UNESCO's Memory of the World register deserves it's own Orbital", then "it's a museum
orbital and must reflect that", then "Yes, build it" (to the plan: the entrance hall, the Australian wing and the
Lenders room first; the international register's 570 inscriptions and the guided tour after).

Three tables in `s4`:

- `museum_wings`: nine wings. Six era wings make the floor plan, from the Ancient Hall to the Sealed Wing; the
  Sealed Wing starts at 1930, the period fleet's cutoff, and holds what a period ship must not know. One country
  wing (the Australian Wing) and two theme wings (the exhibitions Voyages and Charts, and Law and Land).
- `museum_lenders`: the institutions that hold the exhibits; every label carries a lender's credit line.
- `museum_exhibits`: Australia's seven inscriptions on the International Register. Six are confirmed on the
  Australian Memory of the World committee's listing pages (amw.org.au); the d'Entrecasteaux archives (2025) are
  confirmed only by Wikipedia and say so. Where the committee and Wikipedia disagree (the glass plates' year, the
  convict records' holders) the label's note says which was used.

Labels are ours, never UNESCO's or the committee's text. Conservation and access are what we could confirm on
13 November 2026; "not yet checked" means exactly that.

Revision ID: c4e8f1a2b6d3
Revises: b7d1e4a9c2f6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4e8f1a2b6d3"
down_revision = "b7d1e4a9c2f6"
branch_labels = None
depends_on = None

AMW = "https://www.amw.org.au/register/listings/"
WIKI_AP = {"label": "Memory of the World Register: Asia and the Pacific (Wikipedia)",
           "href": "https://en.wikipedia.org/wiki/Memory_of_the_World_Register_%E2%80%93_Asia_and_the_Pacific"}

WINGS = [
    dict(key="australia", ordinal=1, kind="country", name="The Australian Wing", country="au",
         blurb="Australia's documents on the world's register: a captain's journal, a film, the convict records, a "
         "manifesto, a court case that ended a legal fiction.",
         description="The first wing to open. It holds every Australian inscription on the International Register: "
         "seven documents from 1768 to 1992, lent by the national and state libraries and archives that keep them. "
         "Six hang on the near side of the 1930 threshold; the Mabo papers hang beyond it, in the Sealed Wing."),
    dict(key="ancient", ordinal=2, kind="era", name="The Ancient Hall", year_from=-3500, year_to=499,
         blurb="Clay, stone, papyrus and scroll: the oldest kept records, to the end of the ancient world.",
         description="The first room of the floor plan: everything written before 500. Empty until the "
         "international register is hung."),
    dict(key="scriptorium", ordinal=3, kind="era", name="The Scriptorium", year_from=500, year_to=1449,
         blurb="The manuscript centuries: codices, charters and chronicles copied by hand.",
         description="From 500 to the eve of the printing press. Empty until the international register is hung."),
    dict(key="press", ordinal=4, kind="era", name="The Press Room", year_from=1450, year_to=1699,
         blurb="Print and the globe: the first printed books, the new maps and the first long voyages.",
         description="From the printing press to 1700. Empty until the international register is hung."),
    dict(key="sail", ordinal=5, kind="era", name="The Age of Sail", year_from=1700, year_to=1849,
         blurb="Journals, charts and the records of empire, carried by sail.",
         description="From 1700 to 1849: the long voyages and what they brought. Cook's Endeavour journal, the "
         "d'Entrecasteaux expedition and the convict records hang here."),
    dict(key="engine", ordinal=6, kind="era", name="The Engine Hall", year_from=1850, year_to=1929,
         blurb="Steam, the camera, the telegraph and the first films, up to the threshold.",
         description="From 1850 to 1929, the last wing a period ship may know. The glass plates of Sydney Harbour, "
         "the Queensland manifesto and The Story of the Kelly Gang hang here."),
    dict(key="sealed", ordinal=7, kind="era", name="The Sealed Wing", year_from=1930, year_to=None, sealed=True,
         blurb="Everything from 1930 on: past the threshold, where a period ship must not have been.",
         description="The threshold is drawn across the floor at 1930, the period fleet's cutoff. A period ship "
         "that recognises anything in this wing has read something it should not have: the guided tour reads it as a "
         "leak. The Mabo papers hang here."),
    dict(key="voyages-and-charts", ordinal=8, kind="theme", name="Voyages and Charts",
         blurb="An exhibition: the journals and archives of the voyages that reached these coasts.",
         description="A route through the Age of Sail: Cook's Endeavour journal, the d'Entrecasteaux expedition's "
         "archives and the records of the convict transports."),
    dict(key="law-and-land", ordinal=9, kind="theme", name="Law and Land",
         blurb="An exhibition: who governed this country, by what right, and how that was argued.",
         description="A route across the threshold: the convict system's records, the manifesto of a new party, and "
         "the papers of the case that ended the doctrine of terra nullius."),
]

LENDERS = [
    dict(key="nla", ordinal=1, name="National Library of Australia", city="Canberra", country="au",
         country_name="Australia", kind="national library", site="https://www.nla.gov.au",
         about="The national library, holding the Endeavour journal, the Mabo papers and, with three Paris "
         "institutions, part of the d'Entrecasteaux archives."),
    dict(key="nfsa", ordinal=2, name="National Film and Sound Archive", city="Canberra", country="au",
         country_name="Australia", kind="national archive", site="https://www.nfsa.gov.au",
         about="The national archive of film, sound and broadcast, keeper of the surviving Kelly Gang fragments."),
    dict(key="state-archives-nsw", ordinal=3, name="State Archives and Records Authority of New South Wales",
         city="Sydney", country="au", country_name="Australia", kind="state archive",
         site="https://www.records.nsw.gov.au",
         about="New South Wales's government archive, the main keeper of the convict records."),
    dict(key="tasmanian-archives", ordinal=4, name="Tasmanian Archives", city="Hobart", country="au",
         country_name="Australia", kind="state archive", site="https://libraries.tas.gov.au",
         about="Tasmania's government archive, holding the records of Van Diemen's Land's convict system."),
    dict(key="sro-wa", ordinal=5, name="State Records Office of Western Australia", city="Perth", country="au",
         country_name="Australia", kind="state archive", site="https://www.sro.wa.gov.au",
         about="Western Australia's government archive, holding the records of the colony's convict years."),
    dict(key="slnsw", ordinal=6, name="State Library of New South Wales", city="Sydney", country="au",
         country_name="Australia", kind="state library", site="https://www.sl.nsw.gov.au",
         about="The state library of New South Wales, keeper of the giant glass-plate negatives of Sydney Harbour."),
    dict(key="slq", ordinal=7, name="State Library of Queensland", city="Brisbane", country="au",
         country_name="Australia", kind="state library", site="https://www.slq.qld.gov.au",
         about="The state library of Queensland, keeper of the 1892 manifesto of the Queensland labour party."),
    dict(key="archives-nationales", ordinal=8, name="Archives nationales", city="Paris", country="fr",
         country_name="France", kind="national archive", site="https://www.archives-nationales.culture.gouv.fr",
         about="France's national archive, holding part of the d'Entrecasteaux expedition's archives."),
    dict(key="quai-branly", ordinal=9, name="Musée du quai Branly – Jacques Chirac", city="Paris", country="fr",
         country_name="France", kind="museum", site="https://www.quaibranly.fr",
         about="Paris's museum of the arts and cultures of Africa, Asia, Oceania and the Americas, holding part of "
         "the d'Entrecasteaux archives."),
    dict(key="mnhn", ordinal=10, name="Muséum national d'histoire naturelle", city="Paris", country="fr",
         country_name="France", kind="museum", site="https://www.mnhn.fr",
         about="France's natural history museum, holding the expedition's natural history records."),
]

EXHIBITS = [
    dict(key="endeavour-journal", ordinal=1, title="The Endeavour Journal of James Cook", inscribed=2001,
         year_from=1768, year_to=1771, dates="1768–1771", medium="manuscript journal", languages=["English"],
         countries=["au"], lenders=["nla"], themes=["voyages-and-charts"],
         label="James Cook's own journal of HMS Endeavour's voyage to the Pacific, in his hand: Tahiti and the "
         "transit of Venus, the charting of New Zealand, and the first British survey of Australia's east coast.",
         significance="The founding document of British contact with eastern Australia, and of the claim that "
         "followed it; read now from both shores of that landing.",
         conservation="digitised", access="open",
         sources=[{"label": "Australian Memory of the World: the Endeavour journal", "href": AMW + "endeavour-journal-james-cook"}, WIKI_AP]),
    dict(key="dentrecasteaux-archives", ordinal=2, title="Archives of the expedition of d'Entrecasteaux (1791–1794)",
         inscribed=2025, year_from=1791, year_to=1794, dates="1791–1794", medium="mixed archive",
         languages=["French"], countries=["au", "fr"],
         lenders=["archives-nationales", "quai-branly", "mnhn", "nla"], themes=["voyages-and-charts"],
         label="The papers of Bruni d'Entrecasteaux's French expedition, sent to find the lost La Pérouse, which "
         "charted Van Diemen's Land and the southern coasts.",
         significance="A French record of the same coasts in the same decade as the first British settlement, "
         "nominated jointly by France and Australia.",
         conservation="not yet checked", access="not yet checked",
         note="Inscribed in 2025 according to Wikipedia; not yet listed on the Australian committee's pages, and not "
         "checked against UNESCO's own list.",
         sources=[WIKI_AP]),
    dict(key="convict-records", ordinal=3,
         title="Convict Records: Archives of Transportation and the Convict System, 1788–1842", inscribed=2007,
         year_from=1788, year_to=1842, dates="1788–1842", medium="government records", languages=["English"],
         countries=["au"], lenders=["state-archives-nsw", "tasmanian-archives", "sro-wa"],
         themes=["voyages-and-charts", "law-and-land"],
         label="The administrative records of transportation: the indents of the ships, the musters, the tickets of "
         "leave and pardons, naming the people sent to the colonies and what became of them.",
         significance="The fullest record anywhere of a forced migration of the period, kept person by person.",
         conservation="partly digitised", access="open",
         note="The Australian committee names State Records NSW; Wikipedia adds the Tasmanian and Western Australian "
         "archives. All three are credited.",
         sources=[{"label": "Australian Memory of the World: the convict records", "href": AMW + "convict-records-archives-transportation-and-convict-system-1788-1842"}, WIKI_AP]),
    dict(key="giant-glass-plates", ordinal=4, title="Giant Glass Plate Negatives of Sydney Harbour", inscribed=2017,
         year_from=1875, year_to=1875, dates="1875", medium="glass-plate negatives", languages=[],
         countries=["au"], lenders=["slnsw"], themes=[],
         label="Three wet-plate negatives of Sydney Harbour, each well over a metre wide, made in 1875 to show the "
         "colony to the world.",
         significance="Among the largest glass negatives ever made, and a sharp record of a harbour city at the "
         "height of the wet-plate era.",
         conservation="digitised", access="open",
         note="Inscribed 2017 according to the Australian committee; Wikipedia says 2021. The committee's year is used.",
         sources=[{"label": "Australian Memory of the World: the glass plates", "href": AMW + "giant-glass-plate-negatives-sydney-harbour"}, WIKI_AP]),
    dict(key="queensland-labour-manifesto", ordinal=5, title="Manifesto of the Queensland Labour Party, 1892",
         inscribed=2009, year_from=1892, year_to=1892, dates="9 September 1892", medium="manuscript",
         languages=["English"], countries=["au"], lenders=["slq"], themes=["law-and-land"],
         label="The handwritten manifesto, read under a tree at Barcaldine in the shearers' strike years, that set out "
         "the aims of a labour party in Queensland.",
         significance="A founding text of parliamentary labour politics, in the colony that soon gave the world one "
         "of its first labour governments.",
         conservation="not yet checked", access="open",
         note="Inscribed 2009 according to Wikipedia; the Australian committee confirms the listing but not the year.",
         sources=[{"label": "Australian Memory of the World: the manifesto", "href": AMW + "manifesto-queensland-labour-party-1892"}, WIKI_AP]),
    dict(key="kelly-gang", ordinal=6, title="The Story of the Kelly Gang (1906)", inscribed=2007,
         year_from=1906, year_to=1906, dates="1906", medium="film, with its promotional booklet", languages=[],
         countries=["au"], lenders=["nfsa"], themes=[],
         label="The surviving fragments, minutes out of an hour or more, of a film of the Kelly gang's story made in "
         "Victoria in 1906, with the booklet sold at its screenings.",
         significance="Counted as the world's first full-length narrative feature film; most of it is lost.",
         conservation="digitised", access="open",
         sources=[{"label": "Australian Memory of the World: the Kelly Gang", "href": AMW + "story-kelly-gang-1906"}, WIKI_AP]),
    dict(key="mabo-papers", ordinal=7, title="The Mabo Case Manuscripts", inscribed=2001,
         year_from=1959, year_to=1992, dates="1959–1992", medium="manuscript papers", languages=["English"],
         countries=["au"], lenders=["nla"], themes=["law-and-land"],
         label="Eddie Koiki Mabo's papers from the long case, brought by Meriam people of the Murray Islands, in which "
         "the High Court recognised native title in 1992.",
         significance="The record of the case that overturned terra nullius in Australian law.",
         conservation="not yet checked", access="conditions",
         note="The National Library's access conditions apply to parts of the papers; not yet checked item by item.",
         sources=[{"label": "Australian Memory of the World: the Mabo papers", "href": AMW + "mabo-case-manuscripts"}, WIKI_AP]),
]


def _cols(*cols: tuple[str, object]) -> list:
    return [sa.column(name, typ) for name, typ in cols]


def upgrade() -> None:
    op.create_table(
        "museum_wings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("blurb", sa.Text(), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("sealed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("country", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.UniqueConstraint("ordinal"),
        sa.UniqueConstraint("name"),
        schema="s4",
    )
    op.create_table(
        "museum_lenders",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), server_default="", nullable=False),
        sa.Column("country", sa.Text(), server_default="", nullable=False),
        sa.Column("country_name", sa.Text(), server_default="", nullable=False),
        sa.Column("kind", sa.Text(), server_default="", nullable=False),
        sa.Column("site", sa.Text(), server_default="", nullable=False),
        sa.Column("about", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.UniqueConstraint("ordinal"),
        sa.UniqueConstraint("name"),
        schema="s4",
    )
    op.create_table(
        "museum_exhibits",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("register", sa.Text(), server_default="international", nullable=False),
        sa.Column("inscribed", sa.Integer(), nullable=True),
        sa.Column("year_from", sa.Integer(), nullable=False),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("dates", sa.Text(), server_default="", nullable=False),
        sa.Column("medium", sa.Text(), server_default="", nullable=False),
        sa.Column("languages", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("countries", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("lenders", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("themes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("label", sa.Text(), server_default="", nullable=False),
        sa.Column("significance", sa.Text(), server_default="", nullable=False),
        sa.Column("conservation", sa.Text(), server_default="", nullable=False),
        sa.Column("access", sa.Text(), server_default="open", nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("sources", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.UniqueConstraint("ordinal"),
        sa.UniqueConstraint("title"),
        schema="s4",
    )
    t, i, b, j = sa.Text(), sa.Integer(), sa.Boolean(), postgresql.JSONB()
    wings = sa.table("museum_wings", *_cols(("key", t), ("ordinal", i), ("kind", t), ("name", t), ("blurb", t),
                                            ("description", t), ("year_from", i), ("year_to", i), ("sealed", b),
                                            ("country", t)), schema="s4")
    lenders = sa.table("museum_lenders", *_cols(("key", t), ("ordinal", i), ("name", t), ("city", t), ("country", t),
                                                ("country_name", t), ("kind", t), ("site", t), ("about", t)), schema="s4")
    exhibits = sa.table("museum_exhibits", *_cols(
        ("key", t), ("ordinal", i), ("title", t), ("register", t), ("inscribed", i), ("year_from", i), ("year_to", i),
        ("dates", t), ("medium", t), ("languages", j), ("countries", j), ("lenders", j), ("themes", j), ("label", t),
        ("significance", t), ("conservation", t), ("access", t), ("note", t), ("sources", j)), schema="s4")
    op.bulk_insert(wings, [{"year_from": None, "year_to": None, "sealed": False, "country": "", **w} for w in WINGS])
    op.bulk_insert(lenders, LENDERS)
    op.bulk_insert(exhibits, [{"register": "international", "note": "", **e} for e in EXHIBITS])


def downgrade() -> None:
    op.drop_table("museum_exhibits", schema="s4")
    op.drop_table("museum_lenders", schema="s4")
    op.drop_table("museum_wings", schema="s4")
