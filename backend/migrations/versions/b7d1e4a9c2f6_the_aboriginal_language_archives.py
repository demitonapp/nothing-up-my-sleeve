"""Australia's research houses gain the Aboriginal and Torres Strait Islander language archives

13 November, Justin, after asking whether any Australian institute holds every Aboriginal language's written
corpus: "can you add these under australia under the research datamodel". No one house holds them all; these
are the four that hold or join most of what is written:

- AIATSIS, the national institute in Canberra: the largest collection (the Australian Indigenous Languages
  Collection, about 3,700 to 5,400 published items in about 100 of some 250 languages) and AUSTLANG, the
  register of language names and codes.
- The Living Archive of Aboriginal Languages at Charles Darwin University: thousands of digitised books from
  the Northern Territory's bilingual schools, in 30 to 40 or more languages, the most usable digital text.
- PARADISEC (Sydney, Melbourne and the ANU): recordings, field notes and transcripts, Australian and Pacific.
- LDaCA, the Language Data Commons of Australia: a national effort since 2021 to link the scattered collections.

All are `category="research"`, with no model families (none makes models) and their collections as the
flagship. Their pages carry the governing point: these are community-governed collections under Indigenous
Cultural and Intellectual Property protocols, the CARE principles and the Maiam nayri Wingara principles, so
training on them means working with the language communities, not downloading the archives. Ordinals 44 to 47.
Funding splits are estimates from public reporting to 13 November 2026, not audited figures.

Revision ID: b7d1e4a9c2f6
Revises: a3c5e7f9b1d2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7d1e4a9c2f6"
down_revision = "a3c5e7f9b1d2"
branch_labels = None
depends_on = None

GOVERNED = (
    "Much of the material is culturally restricted and is governed item by item under Indigenous Cultural and "
    "Intellectual Property protocols, the CARE principles and the Maiam nayri Wingara Indigenous Data Sovereignty "
    "Principles: training a model on it means working with the language communities, not downloading the archive."
)


def _row(**kw) -> dict:
    base = {
        "listed": True, "category": "research", "families": [], "orgs": [], "country": "au",
        "country_name": "Australia", "focus": "research", "open_weights": True, "gov": None,
    }
    return {**base, **kw}


ROWS = [
    _row(
        key="aiatsis", ordinal=44, kind="national institute",
        name="AIATSIS", short="AIATSIS · AUSTLANG",
        url="https://aiatsis.gov.au/about/what-we-do/about-collection", site="https://aiatsis.gov.au",
        hq="Canberra", founded="1964",
        blurb="the keeping house: AIATSIS, the national institute that holds the largest collection of Aboriginal and "
        "Torres Strait Islander language material and the AUSTLANG register of the languages.",
        description="The Australian Institute of Aboriginal and Torres Strait Islander Studies is a Commonwealth "
        "statutory authority in Canberra. Its Australian Indigenous Languages Collection, begun in 1981, holds about "
        "3,700 to 5,400 published items written in about 100 of the some 250 Australian languages, the only such "
        "collection catalogued as one; its audiovisual languages collection of over 4,500 titles is on UNESCO's "
        "Memory of the World register. It also keeps AUSTLANG, the national register of language names and codes, "
        "and runs the national Indigenous languages surveys. Most of it is print and recordings in a library, not a "
        "downloadable text corpus. " + GOVERNED,
        purpose="to keep, and return to communities, the record of Aboriginal and Torres Strait Islander languages "
        "and cultures.",
        flagship=["Australian Indigenous Languages Collection", "AUSTLANG", "National Indigenous Languages Survey"],
        funding={
            "government": 100, "private": 0, "kind": "national institute",
            "note": "A Commonwealth statutory authority, funded through the federal budget.",
            "basis": "AIATSIS's own statements and public reporting to 13 November 2026; an estimate, not an audited "
            "account.",
            "rounds": [],
        },
    ),
    _row(
        key="living-archive", ordinal=45, kind="university group",
        name="Living Archive of Aboriginal Languages", short="Living Archive · CDU",
        url="https://livingarchive.cdu.edu.au", site="https://livingarchive.cdu.edu.au",
        hq="Darwin", founded="2012",
        blurb="the schoolroom house: Charles Darwin University's Living Archive, thousands of books from the "
        "Northern Territory's bilingual schools, digitised in their own languages.",
        description="The Living Archive of Aboriginal Languages, hosted by the Northern Institute at Charles Darwin "
        "University since 2012, digitises the literature of the Northern Territory's bilingual education programmes: "
        "thousands of mostly short books from over 30 communities, in 30 to 40 or more languages. It is the most "
        "usable digital text in any Aboriginal language, but it covers the Northern Territory only (it sends readers "
        "to AIATSIS for the other states), and each book carries its own licence and community permissions. By our "
        "rough estimate the whole archive is a few million words: a corpus for a very small model. " + GOVERNED,
        purpose="to keep the Northern Territory's Aboriginal-language school books alive and in the hands of the "
        "communities that wrote them.",
        flagship=["Living Archive of Aboriginal Languages"],
        funding={
            "government": 100, "private": 0, "kind": "university group",
            "note": "A university project: Charles Darwin University with public research grants and partners.",
            "basis": "Charles Darwin University's statements and public reporting to 13 November 2026; an estimate, "
            "not an audited account.",
            "rounds": [],
        },
    ),
    _row(
        key="paradisec", ordinal=46, kind="research consortium",
        name="PARADISEC", short="PARADISEC",
        url="https://www.paradisec.org.au", site="https://www.paradisec.org.au",
        hq="Sydney", founded="2003",
        blurb="the field-notes house: PARADISEC, the universities' archive of recordings, notes and transcripts in "
        "the small languages of Australia and the Pacific.",
        description="The Pacific and Regional Archive for Digital Sources in Endangered Cultures is run by the "
        "University of Sydney, the University of Melbourne and the Australian National University. It holds "
        "recordings, field notes and transcripts for Australian and Pacific languages, and earned the Core Trust "
        "Seal in 2019. It is mostly audio; some collections are open and many carry access conditions set with the "
        "speakers. " + GOVERNED,
        purpose="to keep the records of small and endangered languages safe, findable and returned to their speakers.",
        flagship=["PARADISEC catalogue"],
        funding={
            "government": 100, "private": 0, "kind": "research consortium",
            "note": "A university consortium: its three universities and public research grants.",
            "basis": "PARADISEC's own statements and public reporting to 13 November 2026; an estimate, not an "
            "audited account.",
            "rounds": [],
        },
    ),
    _row(
        key="ldaca", ordinal=47, kind="national infrastructure",
        name="Language Data Commons of Australia", short="LDaCA",
        url="https://ldaca.edu.au", site="https://ldaca.edu.au",
        hq="Brisbane", founded="2021",
        blurb="the joining house: LDaCA, the national commons linking Australia's scattered language collections, "
        "AIATSIS and PARADISEC among them.",
        description="The Language Data Commons of Australia, begun in 2021 as a partnership of Australian "
        "universities with the University of Queensland publishing it and funding from the Australian Research Data "
        "Commons, links vulnerable and dispersed collections of written, spoken, signed and multimodal language data "
        "and pairs them with analysis tools (the Australian Text Analytics Platform). AIATSIS and PARADISEC are "
        "partners. It is the closest thing to one front door to Australia's language data, but it links collections "
        "rather than owning them, and their access conditions travel with them. " + GOVERNED,
        purpose="to make Australia's language collections findable, safe and usable together.",
        flagship=["Language Data Commons of Australia", "Australian Text Analytics Platform"],
        funding={
            "government": 100, "private": 0, "kind": "national infrastructure",
            "note": "National research infrastructure: Australian Research Data Commons funding with its partner "
            "universities.",
            "basis": "LDaCA's own statements and public reporting to 13 November 2026; an estimate, not an audited "
            "account.",
            "rounds": [],
        },
    ),
]


def upgrade() -> None:
    labs = sa.table(
        "labs",
        sa.column("key", sa.Text()),
        sa.column("ordinal", sa.Integer()),
        sa.column("listed", sa.Boolean()),
        sa.column("category", sa.Text()),
        sa.column("kind", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("short", sa.Text()),
        sa.column("families", postgresql.JSONB()),
        sa.column("orgs", postgresql.JSONB()),
        sa.column("url", sa.Text()),
        sa.column("site", sa.Text()),
        sa.column("country", sa.Text()),
        sa.column("country_name", sa.Text()),
        sa.column("hq", sa.Text()),
        sa.column("founded", sa.Text()),
        sa.column("blurb", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("purpose", sa.Text()),
        sa.column("flagship", postgresql.JSONB()),
        sa.column("focus", sa.Text()),
        sa.column("open_weights", sa.Boolean()),
        sa.column("funding", postgresql.JSONB()),
        sa.column("gov", postgresql.JSONB()),
        schema="s4",
    )
    op.bulk_insert(labs, ROWS)


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("delete from s4.labs where key = any(:keys)"),
        {"keys": [row["key"] for row in ROWS]},
    )
