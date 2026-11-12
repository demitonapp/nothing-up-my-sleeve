"""the Reach's research houses, country by country

The Research view began with South Africa. It gains a house for each of the other countries the Reach
already trades with (12 November, Justin: "can you add all the research relevant to all the other countries,
specifically US, China and Australia"): EleutherAI in the United States (promoted from the leaderboard-only
list), Shanghai AI Laboratory and BAAI in China, Southern Cross AI in Australia, Kyutai in France, NILC in
Brazil, the Alan Turing Institute in the United Kingdom, Mila in Canada and MBZUAI in the United Arab
Emirates.

EleutherAI already had a row (ordinal 28, unlisted); this migration makes it a research house rather than
inserting a second one. The eight new rows follow at ordinals 36 to 43. All are `category="research"`; the
kinds run from government research institute and research consortium to national institute and public
university. A research house need not name a model — Turing, Mila and MBZUAI do not — and their pages say
"public resources" rather than open or closed weights.

Revision ID: a3c5e7f9b1d2
Revises: f2a4c6e8b0d1
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a3c5e7f9b1d2"
down_revision = "f2a4c6e8b0d1"
branch_labels = None
depends_on = None

ROWS = [{'key': 'shanghai-ai',
  'ordinal': 36,
  'listed': True,
  'category': 'research',
  'kind': 'government research institute',
  'name': 'Shanghai AI Laboratory',
  'short': 'Shanghai AI Lab · InternLM',
  'families': ['internlm', 'internvl', 'shanghai ai'],
  'orgs': ['ShanghaiAILab', 'internlm'],
  'url': 'https://www.shlab.org.cn',
  'site': 'https://www.shlab.org.cn',
  'country': 'cn',
  'country_name': 'China',
  'hq': 'Shanghai',
  'founded': '2020',
  'blurb': "the compass house: Shanghai AI Lab, the city's research institute behind InternLM, InternVL and the "
           'OpenCompass measure.',
  'description': 'Shanghai AI Laboratory is a government-backed research institute founded in 2020. Its InternLM '
                 'language line and InternVL vision models are released openly, and its OpenCompass and OpenMMLab '
                 'projects are the benches much of the Chinese open fleet is measured on.',
  'purpose': 'to build open, reproducible foundation models and the benchmarks that judge them, from Shanghai.',
  'flagship': ['InternLM', 'InternVL', 'OpenCompass'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'government research institute',
              'note': 'A municipal research institute: funded by the Shanghai government and its programme, not by a '
                      'company cap table.',
              'basis': "Public reporting and Shanghai AI Lab's own statements to 12 November 2026; an estimate, not "
                       'an audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'baai',
  'ordinal': 37,
  'listed': True,
  'category': 'research',
  'kind': 'research institute',
  'name': 'BAAI',
  'short': 'BAAI · Aquila',
  'families': ['aquila', 'wudao', 'flagai', 'emu', 'baai'],
  'orgs': ['BAAI'],
  'url': 'https://www.baai.ac.cn',
  'site': 'https://www.baai.ac.cn',
  'country': 'cn',
  'country_name': 'China',
  'hq': 'Beijing',
  'founded': '2018',
  'blurb': "the beacon house: BAAI, Beijing's academy for open models — Aquila, WuDao and the FlagAI toolkit.",
  'description': 'The Beijing Academy of Artificial Intelligence (BAAI) is a research institute founded in 2018 with '
                 'municipal backing. It publishes the Aquila language models, the WuDao line and the FlagAI toolkit, '
                 'and runs one of the largest open model hubs in China.',
  'purpose': 'to keep a public, open model line in Beijing and the tooling to train one.',
  'flagship': ['Aquila', 'WuDao', 'FlagAI'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'research institute',
              'note': 'A nonprofit research institute with Beijing municipal backing; no company equity.',
              'basis': "Public reporting and BAAI's own statements to 12 November 2026; an estimate, not an audited "
                       'cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'southern-cross',
  'ordinal': 38,
  'listed': True,
  'category': 'research',
  'kind': 'research consortium',
  'name': 'Southern Cross AI',
  'short': 'Southern Cross AI · JoeyLLM',
  'families': ['joeyllm', 'joey', 'southern cross'],
  'orgs': [],
  'url': 'https://github.com/joeyllm',
  'site': 'https://github.com/joeyllm',
  'country': 'au',
  'country_name': 'Australia',
  'hq': 'Canberra',
  'founded': '2026',
  'blurb': 'the civic house: Southern Cross AI, the Australian consortium building JoeyLLM, a foundation model for '
           "the country's own infrastructure.",
  'description': 'Southern Cross AI is an Australian research consortium — the Australian National University, the '
                 'Bureau of Meteorology and partners — building JoeyLLM, a Civic Foundation Model for Australian '
                 'infrastructure. Its July 2026 paper documents the move from fine-tuning open models to training '
                 'one from scratch.',
  'purpose': "to give Australia's public infrastructure a model it can own, audit and run.",
  'flagship': ['JoeyLLM'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'research consortium',
              'note': 'A public research consortium: university and public-sector funding rather than a company cap '
                      'table.',
              'basis': 'The JoeyLLM preprint (July 2026) and public reporting to 12 November 2026; an estimate, not '
                       'an audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'kyutai',
  'ordinal': 39,
  'listed': True,
  'category': 'research',
  'kind': 'nonprofit research',
  'name': 'Kyutai',
  'short': 'Kyutai · Moshi',
  'families': ['moshi', 'kyutai', 'helium'],
  'orgs': ['kyutai'],
  'url': 'https://kyutai.org',
  'site': 'https://kyutai.org',
  'country': 'fr',
  'country_name': 'France',
  'hq': 'Paris',
  'founded': '2023',
  'blurb': 'the open-voice house: Kyutai, the Paris lab that made Moshi speak — full-duplex audio in the open.',
  'description': 'Kyutai is a Paris nonprofit AI research lab founded in 2023. Its Moshi is a full-duplex speech '
                 'model released openly, and its Helium small language models put open weights beside it; the lab is '
                 'funded by private founders rather than a state programme.',
  'purpose': 'to make voice-first AI open and fast enough to run in real time.',
  'flagship': ['Moshi', 'Helium'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 0,
              'private': 100,
              'kind': 'nonprofit',
              'note': 'Philanthropic and founder-funded: Xavier Niel, Rodolphe Saadé and Eric Schmidt are among the '
                      'backers; no government equity.',
              'basis': "Public reporting and Kyutai's own statements to 12 November 2026; an estimate, not an "
                       'audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'nilc',
  'ordinal': 40,
  'listed': True,
  'category': 'research',
  'kind': 'university group',
  'name': 'NILC · USP',
  'short': 'NILC · Tucano',
  'families': ['tucano', 'nilc'],
  'orgs': ['TucanoBR'],
  'url': 'https://nilc.icmc.usp.br',
  'site': 'https://nilc.icmc.usp.br',
  'country': 'br',
  'country_name': 'Brazil',
  'hq': 'São Carlos',
  'founded': '1996',
  'blurb': "the toucan house: NILC, the São Carlos group that built Tucano — an open Portuguese model for Brazil's "
           'own texts.',
  'description': 'NILC is the Interinstitutional Center for Computational Linguistics at the University of São '
                 'Paulo, in São Carlos. Its Tucano line is a family of open Portuguese language models trained on '
                 'Brazilian texts, built as a public alternative to English-first models.',
  'purpose': 'to keep a Portuguese-first open model in Brazilian hands.',
  'flagship': ['Tucano'],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'public university',
              'note': 'A research group at a public university: funded by the university and research grants, not a '
                      'company cap table.',
              'basis': 'USP and public reporting to 12 November 2026; an estimate, not an audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'turing',
  'ordinal': 41,
  'listed': True,
  'category': 'research',
  'kind': 'national institute',
  'name': 'The Alan Turing Institute',
  'short': 'Alan Turing Institute',
  'families': [],
  'orgs': [],
  'url': 'https://www.turing.ac.uk',
  'site': 'https://www.turing.ac.uk',
  'country': 'gb',
  'country_name': 'United Kingdom',
  'hq': 'London',
  'founded': '2015',
  'blurb': "the national house: the Alan Turing Institute, Britain's national institute for data science and AI — "
           'research, standards and the public interest.',
  'description': "The Alan Turing Institute is the UK's national institute for data science and artificial "
                 'intelligence, founded in 2015. It does not build a frontier model: it researches safety, methods, '
                 'standards and policy, and convenes the public interest around them.',
  'purpose': "to put independent research and the public interest at the centre of Britain's AI.",
  'flagship': [],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'national institute',
              'note': 'A national research institute: public funding and university partnerships, not a company cap '
                      'table.',
              'basis': "The Institute's own statements to 12 November 2026; an estimate, not an audited cap table.",
              'rounds': []},
  'gov': None},
 {'key': 'mila',
  'ordinal': 42,
  'listed': True,
  'category': 'research',
  'kind': 'research institute',
  'name': 'Mila',
  'short': 'Mila · Quebec',
  'families': [],
  'orgs': [],
  'url': 'https://mila.quebec',
  'site': 'https://mila.quebec',
  'country': 'ca',
  'country_name': 'Canada',
  'hq': 'Montreal',
  'founded': '1993',
  'blurb': 'the deep-learning house: Mila, the Montreal institute Yoshua Bengio founded — the research home of the '
           "field's early deep-learning school.",
  'description': 'Mila is the Quebec Artificial Intelligence Institute, founded in 1993 by Yoshua Bengio. It is a '
                 'research institute rather than a model vendor; its work on deep learning, generative models and AI '
                 'safety underpins much of what the labs ship.',
  'purpose': 'to advance deep learning in the open and train the people who build it.',
  'flagship': [],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 50,
              'private': 50,
              'kind': 'research institute',
              'note': 'A nonprofit institute: Quebec and Canadian public funding beside industry partnerships.',
              'basis': "Mila's own statements and public reporting to 12 November 2026; a rough estimate, not an "
                       'audited cap table.',
              'rounds': []},
  'gov': None},
 {'key': 'mbzuai',
  'ordinal': 43,
  'listed': True,
  'category': 'research',
  'kind': 'public university',
  'name': 'MBZUAI',
  'short': 'MBZUAI · Abu Dhabi',
  'families': [],
  'orgs': [],
  'url': 'https://mbzuai.ac.ae',
  'site': 'https://mbzuai.ac.ae',
  'country': 'ae',
  'country_name': 'United Arab Emirates',
  'hq': 'Abu Dhabi',
  'founded': '2019',
  'blurb': "the desert university house: MBZUAI, Abu Dhabi's graduate AI university — research and the region's own "
           'model talent.',
  'description': 'Mohamed bin Zayed University of Artificial Intelligence (MBZUAI) is a graduate research university '
                 'in Abu Dhabi, founded in 2019. It trains researchers and runs model work of its own, beside the '
                 "UAE's industrial labs.",
  'purpose': 'to build a research base for AI in the Gulf, not just buy it.',
  'flagship': [],
  'focus': 'research',
  'open_weights': True,
  'funding': {'government': 100,
              'private': 0,
              'kind': 'public university',
              'note': 'A public graduate university: funded by the Abu Dhabi government, not a company cap table.',
              'basis': "MBZUAI's own statements to 12 November 2026; an estimate, not an audited cap table.",
              'rounds': []},
  'gov': None}]

ELEUTHERAI = {'listed': True,
 'category': 'research',
 'kind': 'nonprofit research',
 'short': 'EleutherAI · Pythia',
 'url': 'https://huggingface.co/EleutherAI',
 'site': 'https://www.eleuther.ai',
 'country': 'us',
 'country_name': 'United States',
 'hq': 'distributed',
 'founded': '2020',
 'blurb': 'the open-science house: EleutherAI, the distributed nonprofit that made Pythia, GPT-NeoX and The Pile — '
          'the open line much of the field trains on.',
 'description': 'EleutherAI is a distributed nonprofit research lab founded in 2020. It made the Pythia suite, '
                'GPT-NeoX and The Pile, and has kept its models, data and training code open, making it one of the '
                "field's shared benches.",
 'purpose': 'to keep frontier-scale training open, reproducible and outside any one company.',
 'flagship': ['Pythia', 'GPT-NeoX', 'GPT-J'],
 'funding': {'government': 0,
             'private': 100,
             'kind': 'nonprofit research',
             'note': 'A nonprofit research lab: sponsored by foundations and industry, with no government equity.',
             'basis': "Public reporting and EleutherAI's own statements to 12 November 2026; an estimate, not an "
                      'audited cap table.',
             'rounds': []},
 'orgs': ['EleutherAI']}


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
    op.get_bind().execute(
        sa.text(
            """update s4.labs set
                 listed=true, category='research', kind=:kind, short=:short,
                 url=:url, site=:site, country=:country, country_name=:country_name,
                 hq=:hq, founded=:founded, blurb=:blurb, description=:description,
                 purpose=:purpose, flagship=cast(:flagship as jsonb), focus='research',
                 open_weights=true, funding=cast(:funding as jsonb), orgs=cast(:orgs as jsonb)
               where key='eleutherai'"""
        ),
        {
            "kind": ELEUTHERAI["kind"], "short": ELEUTHERAI["short"],
            "url": ELEUTHERAI["url"], "site": ELEUTHERAI["site"],
            "country": ELEUTHERAI["country"], "country_name": ELEUTHERAI["country_name"],
            "hq": ELEUTHERAI["hq"], "founded": ELEUTHERAI["founded"],
            "blurb": ELEUTHERAI["blurb"], "description": ELEUTHERAI["description"],
            "purpose": ELEUTHERAI["purpose"],
            "flagship": json.dumps(ELEUTHERAI["flagship"]),
            "funding": json.dumps(ELEUTHERAI["funding"]),
            "orgs": json.dumps(ELEUTHERAI["orgs"]),
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("delete from s4.labs where key = any(:keys)"),
        {"keys": [row["key"] for row in ROWS]},
    )
    op.get_bind().execute(
        sa.text(
            """update s4.labs set
                 listed=false, category='lab', kind='nonprofit', short='',
                 site='', country='', country_name='', hq='', founded='',
                 blurb='', description='', purpose='', flagship='[]'::jsonb,
                 focus='research', open_weights=true, funding='{}'::jsonb, orgs='[]'::jsonb
               where key='eleutherai'"""
        )
    )
