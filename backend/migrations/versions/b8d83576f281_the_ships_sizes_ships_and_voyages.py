"""the ships: sizes, ships and voyages

The sizes are seeded here once, from the ladder as it stood (registry.LADDER, 2026-11-08), with 100m now
the first true explorer and 350m the first trader with the new world. From here the database is where a
size is named and described; scripts/seed_ships.py brings the ship register and its voyages in.

Revision ID: b8d83576f281
Revises: 2c9496d5208e
Create Date: 2026-11-08 13:32:54.603623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b8d83576f281'
down_revision: Union[str, Sequence[str], None] = '2c9496d5208e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SIZES = [{'preset': '300k',
  'ordinal': 0,
  'name': 'The keel',
  'role': 'Laid first, and everything is built on it: light the first stars in minutes, then become the '
          'foundation a 1m is built on',
  'overview': '2 layers x 64, two heads of 32 (the same head size as 1m and 9m, so a head can be carried up '
              'whole), vocabulary 2,048: about 0.3M parameters. Too small to judge books on; its job is the '
              'bottom of the stack. Can it light a previous-word head at all, how fast, and does a 1m built '
              'on its frozen layers reach the Nevermore sooner?',
  'kind': 'nursery',
  'vocab': 2048,
  'trains_where': 'this Mac (a minute or two a run)',
  'status': 'planned',
  'scored': 'The four necessary cards held, then cause and effect, then chaining two facts',
  'metrics': [['cards held',
               'of the four every chaining model holds (previous-word, the Nevermore, the mover, the '
               "comparator), how many it draws, by one head or a layer's best two; the card census around "
               'its fitout says which are possible at 300k at all',
               'live'],
              ['cause and effect',
               "the logic deck's chaining gain on its cause items (invented words, so no knowledge helps); "
               '0.1 to count, eight items',
               'live'],
              ['chaining two facts',
               'the chaining lift on the four public chaining tests; above 0.03 it leaves the noise and '
               'joins the chaining board',
               'live'],
              ['the 1m on top',
               'whether a 1m grown from it draws the cards sooner than one built from nothing',
               'to come']]},
 {'preset': '1m',
  'ordinal': 1,
  'name': 'The pilot',
  'role': 'A pilot study and the harbour pilot: scouts data questions fast, trusted only where it ranks '
          'shelves as 9m does, and brings the bigger ships in',
  'overview': '4 layers x 128, vocabulary 4,096, about 1.4M parameters. Scored only on the Forgotten Tomes, '
              'once at the end. First it re-runs comparisons already made at 9m; if its ranking agrees, it '
              'explores and 9m confirms the winners.',
  'kind': 'proxy',
  'vocab': 4096,
  'trains_where': 'this Mac (about 4 minutes a run)',
  'status': 'calibrating against 9m',
  'scored': 'The four necessary cards held, then cause and effect, then chaining two facts; the Forgotten '
            'Tomes beside',
  'metrics': [['cards held',
               'of the four every chaining model holds (previous-word, the Nevermore, the mover, the '
               'comparator), how many it draws; the card census around its fitout says which are possible at '
               '1m',
               'live'],
              ['cause and effect',
               "the logic deck's chaining gain on its cause items; 0.1 to count, eight items",
               'live'],
              ['chaining two facts',
               'the chaining lift on the four public chaining tests; above 0.03 it joins the chaining board',
               'live'],
              ['Forgotten Tomes score',
               "bits per byte on 16 books Qwen 3.8 cannot have read: the shelf scout's measure",
               'live']]},
 {'preset': '9m',
  'ordinal': 2,
  'name': 'The speller',
  'role': 'Spelling, punctuation and the statistical laws of text',
  'overview': 'The smallest model learns the surface of English: how words are spelled, where punctuation '
              'goes, how lines and paragraphs break, and the statistical regularities every real text obeys. '
              'Tuned first (vocabulary and context), then frozen for shelf experiments.',
  'kind': None,
  'vocab': None,
  'trains_where': 'this Mac',
  'status': 'running',
  'scored': 'Bits per byte split by kind of byte, and the laws on what it writes',
  'metrics': [['inside a word', 'bits per byte on letters after the first: spelling', 'live'],
              ['word start', "bits per byte on a word's first letter: which word comes next", 'live'],
              ['punctuation', 'bits per byte on punctuation marks', 'live'],
              ['layout', 'bits per byte on spaces and line breaks', 'live'],
              ['non-words',
               "share of words it writes that the shelf never held (books' own rate beside it)",
               'live'],
              ['Zipf and Heaps',
               'word frequency against rank; vocabulary growth (against the books)',
               'live'],
              ['word length, punctuation mix', "divergence from the books' distributions", 'live'],
              ['balance and capitals', 'unclosed brackets and quotes; capitals after a full stop', 'live'],
              ['traits as they emerge',
               'fiction, verse, first person: at which step and layer each appears while spelling is learned',
               'live']]},
 {'preset': '21m',
  'ordinal': 3,
  'name': 'The stylist',
  'role': 'Grammar and style: agreement, whole sentences, a register held through a passage',
  'overview': 'Above the word: subject and verb agree across a clause, sentences close, and a passage keeps '
              'one voice (King James, Victorian novel, Greek translation). Also the size for the Leonardo '
              "pilot's second step if 9m shows nothing.",
  'kind': None,
  'vocab': None,
  'trains_where': 'this Mac',
  'status': 'waits for 9m to be used up',
  'scored': 'Grammatical minimal pairs, loss by position in the window, a register probe',
  'metrics': [['minimal pairs', 'grammatical against ungrammatical sentence, period vocabulary', 'to come'],
              ['loss by position', 'does loss keep falling deep into the 1,024-token window', 'to come'],
              ['register probe', 'can the hidden state tell a passage has changed voice', 'to come'],
              ['the 9m laws', 'kept, so the rung below stays visible', 'live']]},
 {'preset': '50m',
  'ordinal': 4,
  'name': 'The paragraph',
  'role': "Paragraphs, and the third point of this corpus's own size curve",
  'overview': 'Sentences that connect into paragraphs, characters and topics that persist; with 9m and 21m '
              "it fits this corpus's own loss-against-size curve in place of borrowed constants.",
  'kind': None,
  'vocab': None,
  'trains_where': 'rented GPUs (needs a PyTorch backend)',
  'status': 'not built',
  'scored': 'The size curve; copy gain and late-in-window loss from the curiosity ladder',
  'metrics': [['size curve', 'hole-card loss against parameters, fitted on 9m, 21m and 50m', 'to come'],
              ['in-context copying', 'copy gain and late-minus-early loss (curiosity ladder)', 'live']]},
 {'preset': '100m',
  'ordinal': 5,
  'name': 'The explorer',
  'role': 'The first true explorer: the Origin and Leonardo tests, does it bet on an idea before the world '
          'did?',
  'overview': 'Trained only on text before a cutoff year, does it find natural selection, or each of '
              "Leonardo's rediscovered ideas, less surprising than the rival accounts of the time? Betting, "
              'not deriving.',
  'kind': None,
  'vocab': None,
  'trains_where': 'rented (about $5 a run) or this Mac (5 to 8 days)',
  'status': 'planned',
  'scored': 'Matched rival passages in bits per byte, against floors; precursor shelves removed',
  'metrics': [['Origin preference', 'selection against fixed species, Lamarck, special creation', 'to come'],
              ['Leonardo timeline', 'per claim, the cutoff where his version starts to win', 'to come'],
              ['precursor ablation',
               'the preference with Malthus and Lyell taken off, same bytes',
               'to come']]},
 {'preset': '350m',
  'ordinal': 6,
  'name': 'The trader',
  'role': 'The first trader with the new world: the top of the Origin and Leonardo curves',
  'overview': 'The largest model the legal corpus can feed. Its job is to show whether the preference keeps '
              'rising with size; at the 1858 cutoff it is short of data.',
  'kind': None,
  'vocab': None,
  'trains_where': 'rented GPUs (about $35 a run)',
  'status': 'planned',
  'scored': 'As for 100m',
  'metrics': [['Origin and Leonardo curves', 'the same tests, the top point of the size curve', 'to come']]}]


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("create schema if not exists ship")
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('sizes',
    sa.Column('preset', sa.Text(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('overview', sa.Text(), server_default='', nullable=False),
    sa.Column('kind', sa.Text(), nullable=True),
    sa.Column('vocab', sa.Integer(), nullable=True),
    sa.Column('trains_where', sa.Text(), server_default='', nullable=False),
    sa.Column('status', sa.Text(), server_default='planned', nullable=False),
    sa.Column('scored', sa.Text(), server_default='', nullable=False),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.PrimaryKeyConstraint('preset'),
    sa.UniqueConstraint('name'),
    sa.UniqueConstraint('ordinal'),
    schema='ship'
    )
    op.create_table('ships',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('preset', sa.Text(), nullable=False),
    sa.Column('size', sa.Text(), nullable=False),
    sa.Column('fitout_id', sa.Text(), nullable=False),
    sa.Column('subtitle', sa.Text(), server_default='', nullable=False),
    sa.Column('archived', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('seeded_from', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('expedition', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['size'], ['ship.sizes.preset'], ),
    sa.PrimaryKeyConstraint('key'),
    sa.UniqueConstraint('name'),
    schema='ship'
    )
    op.create_table('voyages',
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('ship_key', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('seed', sa.Integer(), nullable=True),
    sa.Column('started', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['ship_key'], ['ship.ships.key'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('run_id'),
    schema='ship'
    )
    op.create_index('voyages_ship', 'voyages', ['ship_key'], unique=False, schema='ship')
    # ### end Alembic commands ###

    sizes = sa.table('sizes', *(sa.column(k, postgresql.JSONB) if k == 'metrics' else sa.column(k) for k in SIZES[0]), schema='ship')
    op.bulk_insert(sizes, SIZES)

def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('voyages_ship', table_name='voyages', schema='ship')
    op.drop_table('voyages', schema='ship')
    op.drop_table('ships', schema='ship')
    op.drop_table('sizes', schema='ship')
    # ### end Alembic commands ###
