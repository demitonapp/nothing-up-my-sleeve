"""the Reach's research houses, and the category beside the labs

The Reach had one kind of house. Six organisations join it (12 November, Justin: "Lets add Flower Labs and
Stability AI, UCT NLP, Makaskhane, SADiLaR (these mean we'll need another category to live alongside Labs),
Sovereign Australia AI"), and three of them are not labs: a university group, a volunteer collective and a
national language infrastructure. `s4.labs` gains `category` (`lab` or `research`) and `kind` (company,
university group, collective, national infrastructure); the Labs page keeps the labs and a new Research
view carries the rest.

The new rows: Flower Labs and Stability AI (UK, both model makers), UCT NLP and Masakhane (South Africa,
both open research) and SADiLaR (the national language corpus), and Sovereign Australia AI (Canberra, the
Ginan/Australis house). They follow the 29 rows of the first migration.

Revision ID: f2a4c6e8b0d1
Revises: e8a1b4c7d2f5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f2a4c6e8b0d1"
down_revision = "e8a1b4c7d2f5"
branch_labels = None
depends_on = None

ROWS = [{'key': 'flower',
  'ordinal': 30,
  'listed': True,
  'category': 'lab',
  'kind': 'company',
  'name': 'Flower Labs',
  'short': 'Flower Labs · Lizzy',
  'families': ['flower', 'lizzy', 'endeavor'],
  'orgs': ['flwrlabs'],
  'url': 'https://huggingface.co/flwrlabs',
  'site': 'https://flower.ai',
  'country': 'gb',
  'country_name': 'United Kingdom',
  'hq': 'London',
  'founded': '2023',
  'blurb': "the federation house: Flower, the London yard that trains across many harbours at once — Lizzy-7B's open "
           "weights and Endeavor's licensed frontier.",
  'description': 'Flower Labs is the London and Hamburg house behind Flower, the open federated-learning framework '
                 'that lets a model be trained where the data lives. It turned that into models: Lizzy-7B, an '
                 'open-weight UK model built for British English and institutions, and Endeavor 1.0, a licensed '
                 'frontier model for organisations that need the intelligence on their own systems.',
  'purpose': "to let organisations train and run frontier models without handing their data to someone else's cloud.",
  'flagship': ['Lizzy-7B', 'Endeavor 1.0'],
  'focus': 'open fleet',
  'open_weights': True,
  'funding': {'government': 0,
              'private': 100,
              'kind': 'private',
              'note': 'Venture-backed and privately held; over £23M raised, with Y Combinator alumni among the '
                      'founders. No government equity.',
              'basis': "Public reporting and Flower's own announcements to 12 November 2026; an estimate, not an "
                       'audited cap table.',
              'rounds': [{'date': '2023–25',
                          'round': 'Private rounds',
                          'amount': 'over £23M',
                          'valuation': '—',
                          'investors': 'not itemised in public reporting'}]},
  'gov': None},
 {'key': 'stability',
  'ordinal': 31,
  'listed': True,
  'category': 'lab',
  'kind': 'company',
  'name': 'Stability AI',
  'short': 'Stability AI',
  'families': ['stable', 'stability', '\\bsdxl\\b'],
  'orgs': ['stabilityai'],
  'url': 'https://huggingface.co/stabilityai',
  'site': 'https://stability.ai',
  'country': 'gb',
  'country_name': 'United Kingdom',
  'hq': 'London',
  'founded': '2019',
  'blurb': 'the open-canvas house: Stability, the London yard that gave the world Stable Diffusion and kept its '
           'weights open — image, audio, video and the StableLM line.',
  'description': 'Stability AI is the London generative-AI house that funded Stable Diffusion and kept publishing '
                 'weights: image, audio, video and 3D models, with the StableLM language line beside them. After a '
                 'turbulent few years it steadied under Prem Akkaraju, and a $76M Series B in August 2026, backed by '
                 'the major music labels and Electronic Arts, points it at creative production.',
  'purpose': 'to keep generative models open enough that anyone can build on them, not just rent them.',
  'flagship': ['Stable Diffusion', 'StableLM', 'Stable Audio'],
  'focus': 'open fleet',
  'open_weights': True,
  'funding': {'government': 0,
              'private': 100,
              'kind': 'private',
              'note': 'Privately held; the August 2026 Series B was backed by the major music labels and Electronic '
                      'Arts.',
              'basis': 'Public reporting to 12 November 2026; an estimate, not an audited cap table.',
              'rounds': [{'date': '2022-10',
                          'round': 'Seed',
                          'amount': '$101M',
                          'valuation': '—',
                          'investors': "Coatue, Lightspeed, O'Shaughnessy Ventures"},
                         {'date': '2026-08',
                          'round': 'Series B',
                          'amount': '$76M',
                          'valuation': '—',
                          'investors': 'Universal Music, Warner Music, Sony Music, Electronic Arts'}]},
  'gov': None},
 {'key': 'uctnlp',
  'ordinal': 32,
  'listed': True,
  'category': 'research',
  'kind': 'university group',
  'name': 'UCT NLP',
  'short': 'UCT NLP · MzansiLM',
  'families': ['mzansi', 'uctnlp'],
  'orgs': ['uctnlp'],
  'url': 'https://huggingface.co/uctnlp',
  'site': 'https://huggingface.co/uctnlp',
  'country': 'za',
  'country_name': 'South Africa',
  'hq': 'Cape Town',
  'founded': '2026',
  'blurb': "the eleven-tongue house: UCT's Cape Town group, which built MzansiLM — one small open model for all "
           "eleven of South Africa's written languages.",
  'description': "UCT NLP is the University of Cape Town's natural-language processing group. In May 2026 it "
                 'released MzansiText and MzansiLM: a curated corpus and a 125M-parameter decoder-only model '
                 'covering all eleven official written South African languages, open for anyone to fine-tune. It is '
                 'a base model, not a chat assistant.',
  'purpose': "to give South Africa's languages a shared, reproducible baseline instead of a corner of someone else's "
             'model.',
  'flagship': ['MzansiLM 125M'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'public university',
              'note': 'A research group at the University of Cape Town, a public university: funded by the '
                      'university and research grants, not a company cap table.',
              'basis': 'UCT and public reporting to 12 November 2026; an estimate, not an audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'masakhane',
  'ordinal': 33,
  'listed': True,
  'category': 'research',
  'kind': 'collective',
  'name': 'Masakhane',
  'short': 'Masakhane',
  'families': ['masakhane', 'masakha'],
  'orgs': ['Masakhane'],
  'url': 'https://huggingface.co/Masakhane',
  'site': 'https://masakhane.io',
  'country': 'za',
  'country_name': 'Pan-African · South Africa',
  'hq': 'across Africa',
  'founded': '2019',
  'blurb': 'the many-hands house: Masakhane, the pan-African collective that builds the datasets, benchmarks and '
           'models for African languages in the open.',
  'description': 'Masakhane is a grassroots pan-African NLP research collective, founded in 2019 out of the Deep '
                 'Learning Indaba. It builds open datasets, benchmarks and models for African languages — '
                 'MasakhaNER, MasakhaPOS and a wide library of community work — and insists the work be reproducible '
                 'and owned on the continent.',
  'purpose': 'to make African languages first-class in NLP, with the data and models built by the people who speak '
             'them.',
  'flagship': ['MasakhaNER 2.0', 'MasakhaPOS'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 0,
              'private': 100,
              'kind': 'collective',
              'note': 'A volunteer research collective: no company equity or cap table. The work is contributed and '
                      'supported by grants and host institutions.',
              'basis': 'Public reporting to 12 November 2026; an estimate, not an audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'sadilar',
  'ordinal': 34,
  'listed': True,
  'category': 'research',
  'kind': 'national infrastructure',
  'name': 'SADiLaR',
  'short': 'SADiLaR',
  'families': [],
  'orgs': [],
  'url': 'https://sadilar.org',
  'site': 'https://sadilar.org',
  'country': 'za',
  'country_name': 'South Africa',
  'hq': 'Potchefstroom',
  'founded': '2019',
  'blurb': "the archive house: SADiLaR, the national centre that keeps South Africa's language corpora and tools — "
           'not a shipyard, the timber yard every other yard draws on.',
  'description': "SADiLaR is South Africa's national centre for digital language resources, funded by the Department "
                 'of Science and Innovation and hosted at North-West University. It does not build a frontier model: '
                 'it collects, curates and licenses the corpora, lexicons and tools — and trains the people — that '
                 'UCT, Lelapa and Masakhane build on.',
  'purpose': "to hold the country's language data in public trust, so the models built on it can be audited and "
             'reproduced.',
  'flagship': [],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'national infrastructure',
              'note': "Funded by South Africa's Department of Science and Innovation and hosted at North-West "
                      'University: a public national facility, not a company.',
              'basis': "SADiLaR's own statements to 12 November 2026; an estimate, not an audited cap table.",
              'rounds': []},
  'gov': None},
 {'key': 'sovereign-au',
  'ordinal': 35,
  'listed': True,
  'category': 'lab',
  'kind': 'company',
  'name': 'Sovereign Australia AI',
  'short': 'Sovereign Australia AI · Ginan',
  'families': ['ginan', 'australis', 'sovereign australia'],
  'orgs': [],
  'url': 'https://sovereign-au.ai',
  'site': 'https://sovereign-au.ai',
  'country': 'au',
  'country_name': 'Australia',
  'hq': 'Canberra',
  'founded': '2025',
  'blurb': 'the southern-cross house: Sovereign Australia AI, the Canberra yard building Australis from the ground '
           'up — Ginan, its 8B Australian-biased research ship, first.',
  'description': 'Sovereign Australia AI is the Canberra house building a from-scratch Australian model, Australis, '
                 'on Australian-owned infrastructure. Its first proof of concept, Ginan, is an 8B model fine-tuned '
                 'on about 2 billion tokens of Australian data — legal text, .au web pages, Reddit and Project '
                 'Gutenberg Australia — and is meant to be free to Australians. The larger Australis is planned '
                 'against 256 Blackwell GPUs and an A$80M raise.',
  'purpose': 'to make an Australian model that defaults to Australian answers and runs under Australian law.',
  'flagship': ['Ginan', 'Australis'],
  'focus': 'enterprise',
  'open_weights': False,
  'funding': {'government': 0,
              'private': 100,
              'kind': 'private',
              'note': 'Privately held and raising A$80M; chaired by Annette Kimmitt, with 256 Blackwell GPUs ordered '
                      'for the Australis training run.',
              'basis': "Forbes Australia reporting, February 2026, and the company's own statements to 12 November "
                       '2026; an estimate, not an audited cap table.',
              'rounds': [{'date': '2025–26',
                          'round': 'Founding round',
                          'amount': 'A$80M sought',
                          'valuation': '—',
                          'investors': 'private Australian investors; chaired by Annette Kimmitt'}]},
  'gov': None}]

def upgrade() -> None:
    op.add_column("labs", sa.Column("category", sa.Text(), server_default="lab", nullable=False), schema="s4")
    op.add_column("labs", sa.Column("kind", sa.Text(), server_default="", nullable=False), schema="s4")
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
    # the first 29 rows predate `kind`: a company unless the house is a nonprofit or a government institute
    op.get_bind().execute(sa.text("update s4.labs set kind='company' where kind=''"))
    op.get_bind().execute(sa.text("update s4.labs set kind='nonprofit' where key in ('ai2', 'eleutherai')"))
    op.get_bind().execute(sa.text("update s4.labs set kind='government institute' where key='tii'"))
    # "fusion" matched "Diffusion" (Stability's ships): Arcee's family is a word, not a substring
    op.get_bind().execute(
        sa.text("update s4.labs set families = cast(:families as jsonb) where key='arcee'"),
        {"families": '[\"arcee\", \"\\\\bafm\", \"\\\\bfusion\"]'},
    )


def downgrade() -> None:
    keys = [row["key"] for row in ROWS]
    op.get_bind().execute(
        sa.text("delete from s4.labs where key = any(:keys)"),
        {"keys": keys},
    )
    op.drop_column("labs", "kind", schema="s4")
    op.drop_column("labs", "category", schema="s4")
