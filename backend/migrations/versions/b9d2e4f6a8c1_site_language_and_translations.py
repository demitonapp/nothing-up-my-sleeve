"""The site's language, the languages it can be put into, and the translations kept

13 November (Justin: "add your language in the chat terminal as an option. When you do that, the Liberty Machine picks
up the language you've chosen and uses tiny aya earth to dynamically translate the entire site"). S5 policy 'postgres':
a new kind of record starts as a migration.

- `s5.languages`: the languages the site can be put into, one row each. `listed` says whether Cohere's Tiny Aya Earth
  card names the language in its "focus" list (67 of them); Afrikaans is here with `listed = false`, because Justin
  asked for it and the card does not name it. English is the source (`is_source`), never a target.
- `s5.site_language`: one row, the language the site speaks now: a foreign key to `s5.languages`, who chose it and when.
- `s1.translations`: what the translator made, kept so a string is translated once: (language, the SHA-1 of the English,
  the English, the translation, the model, when). A translation is a view of the English, never the record: DECISIONS.md
  stays English.

Revision ID: b9d2e4f6a8c1
Revises: a8c0e2f4b6d9
"""

from __future__ import annotations

from alembic import op

revision = "b9d2e4f6a8c1"
down_revision = "a8c0e2f4b6d9"
branch_labels = None
depends_on = None

# code, English name, the name in the language itself, right to left, named on Tiny Aya Earth's card
_LANGUAGES = [
    ("en", "English", "English", False, True),
    ("nl", "Dutch", "Nederlands", False, True),
    ("fr", "French", "Français", False, True),
    ("it", "Italian", "Italiano", False, True),
    ("pt", "Portuguese", "Português", False, True),
    ("ro", "Romanian", "Română", False, True),
    ("es", "Spanish", "Español", False, True),
    ("cs", "Czech", "Čeština", False, True),
    ("pl", "Polish", "Polski", False, True),
    ("uk", "Ukrainian", "Українська", False, True),
    ("ru", "Russian", "Русский", False, True),
    ("el", "Greek", "Ελληνικά", False, True),
    ("de", "German", "Deutsch", False, True),
    ("da", "Danish", "Dansk", False, True),
    ("sv", "Swedish", "Svenska", False, True),
    ("no", "Norwegian", "Norsk", False, True),
    ("ca", "Catalan", "Català", False, True),
    ("gl", "Galician", "Galego", False, True),
    ("cy", "Welsh", "Cymraeg", False, True),
    ("ga", "Irish", "Gaeilge", False, True),
    ("eu", "Basque", "Euskara", False, True),
    ("hr", "Croatian", "Hrvatski", False, True),
    ("lv", "Latvian", "Latviešu", False, True),
    ("lt", "Lithuanian", "Lietuvių", False, True),
    ("sk", "Slovak", "Slovenčina", False, True),
    ("sl", "Slovenian", "Slovenščina", False, True),
    ("et", "Estonian", "Eesti", False, True),
    ("fi", "Finnish", "Suomi", False, True),
    ("hu", "Hungarian", "Magyar", False, True),
    ("sr", "Serbian", "Српски", False, True),
    ("bg", "Bulgarian", "Български", False, True),
    ("ar", "Arabic", "العربية", True, True),
    ("fa", "Persian", "فارسی", True, True),
    ("ur", "Urdu", "اردو", True, True),
    ("tr", "Turkish", "Türkçe", False, True),
    ("mt", "Maltese", "Malti", False, True),
    ("he", "Hebrew", "עברית", True, True),
    ("hi", "Hindi", "हिन्दी", False, True),
    ("mr", "Marathi", "मराठी", False, True),
    ("bn", "Bengali", "বাংলা", False, True),
    ("gu", "Gujarati", "ગુજરાતી", False, True),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", False, True),
    ("ta", "Tamil", "தமிழ்", False, True),
    ("te", "Telugu", "తెలుగు", False, True),
    ("ne", "Nepali", "नेपाली", False, True),
    ("tl", "Tagalog", "Tagalog", False, True),
    ("ms", "Malay", "Bahasa Melayu", False, True),
    ("id", "Indonesian", "Bahasa Indonesia", False, True),
    ("vi", "Vietnamese", "Tiếng Việt", False, True),
    ("jv", "Javanese", "Basa Jawa", False, True),
    ("km", "Khmer", "ខ្មែរ", False, True),
    ("th", "Thai", "ไทย", False, True),
    ("lo", "Lao", "ລາວ", False, True),
    ("zh", "Chinese", "中文", False, True),
    ("my", "Burmese", "မြန်မာ", False, True),
    ("ja", "Japanese", "日本語", False, True),
    ("ko", "Korean", "한국어", False, True),
    ("am", "Amharic", "አማርኛ", False, True),
    ("ha", "Hausa", "Hausa", False, True),
    ("ig", "Igbo", "Igbo", False, True),
    ("mg", "Malagasy", "Malagasy", False, True),
    ("sn", "Shona", "chiShona", False, True),
    ("sw", "Swahili", "Kiswahili", False, True),
    ("wo", "Wolof", "Wolof", False, True),
    ("xh", "Xhosa", "isiXhosa", False, True),
    ("yo", "Yoruba", "Yorùbá", False, True),
    ("zu", "Zulu", "isiZulu", False, True),
    # not on the card; here because Justin asked for it. Close to Dutch, well resourced, untested on this model.
    ("af", "Afrikaans", "Afrikaans", False, False),
]


def upgrade() -> None:
    op.execute(
        "create table if not exists s5.languages ("
        "code text primary key check (code ~ '^[a-z]{2,3}$'), "
        "name text not null check (btrim(name) <> ''), "
        "native_name text not null check (btrim(native_name) <> ''), "
        "rtl boolean not null default false, "
        "listed boolean not null default true, "
        "is_source boolean not null default false)"
    )
    # exactly one source language: English
    op.execute("create unique index if not exists languages_one_source on s5.languages (is_source) where is_source")
    values = ", ".join(
        "('{}', '{}', '{}', {}, {}, {})".format(
            code, name.replace("'", "''"), native.replace("'", "''"), str(rtl).lower(), str(listed).lower(), str(code == "en").lower()
        )
        for code, name, native, rtl, listed in _LANGUAGES
    )
    op.execute(f"insert into s5.languages (code, name, native_name, rtl, listed, is_source) values {values} on conflict (code) do nothing")

    op.execute(
        "create table if not exists s5.site_language ("
        "id smallint primary key default 1 check (id = 1), "
        "code text not null references s5.languages (code), "
        "chosen_by text not null default 'Justin' check (btrim(chosen_by) <> ''), "
        "chosen_at timestamptz not null default now())"
    )
    op.execute("insert into s5.site_language (id, code) values (1, 'en') on conflict (id) do nothing")

    op.execute(
        "create table if not exists s1.translations ("
        "code text not null references s5.languages (code), "
        "source_hash text not null check (source_hash ~ '^[0-9a-f]{40}$'), "
        "source text not null check (btrim(source) <> ''), "
        "target text not null check (btrim(target) <> ''), "
        "model text not null check (btrim(model) <> ''), "
        "made_at timestamptz not null default now(), "
        "primary key (code, source_hash))"
    )
    # English is the source: nothing is translated into it
    op.execute(
        "create function s1.translations_not_into_the_source() returns trigger language plpgsql as $$ "
        "begin "
        "if exists (select 1 from s5.languages where code = new.code and is_source) then "
        "raise exception 'English is the source language: nothing is translated into it'; "
        "end if; return new; end $$"
    )
    op.execute(
        "create trigger translations_not_into_the_source before insert or update on s1.translations "
        "for each row execute function s1.translations_not_into_the_source()"
    )


def downgrade() -> None:
    op.execute("drop trigger if exists translations_not_into_the_source on s1.translations")
    op.execute("drop function if exists s1.translations_not_into_the_source()")
    op.drop_table("translations", schema="s1")
    op.drop_table("site_language", schema="s5")
    op.drop_table("languages", schema="s5")
