# Goethe A1–B1 Anki deck

`Deutsch_Goethe_A1-B1.apkg` holds about 2,900 words from the official **Goethe-Zertifikat B1 Wortliste**.
Every card has:

- the German word, colour-coded by gender: **der** blue · **die** red · **das** green
- the plural (nouns) or the main verb forms (*fährt ab, fuhr ab, ist abgefahren*)
- an English meaning (written to match the example sentence)
- 1–3 example sentences taken from the Goethe list
- audio for the word and the first example (macOS voice "Anna")

Subdecks: `1 – A1` → `2 – A2` → `3 – B1`. The level comes from your A1 and A2 lists. Cards are shuffled within each level.
Austrian/Swiss-only words (*Semmel, Velo, Matura …*) are tagged `regional` and placed at the end of their level.

## Import

1. Install Anki (desktop: apps.ankiweb.net; AnkiDroid on Android is free; AnkiMobile on iOS is paid).
2. Double-click the `.apkg` file, or in Anki use **File → Import**.
3. To use it on your phone, sync with a free AnkiWeb account.

## Suggested settings (Deck options → apply to all three subdecks)

| Setting | Value | Why |
|---|---|---|
| New cards/day | **20** (A1/A2), later 15 | About 25–35 min/day once reviews build up |
| Maximum reviews/day | 9999 | Never let reviews pile up |
| Learning steps | 1m 10m | default |
| FSRS | **on** | better scheduling |
| Bury new/review siblings | **on** | the DE→EN and EN→DE cards of one word won't show on the same day |

At 20 new cards a day, A1+A2 takes about 2.5 months, and the full deck takes about 5 months.
If A1 feels easy, study the A1 deck at 40–50 new/day, or select the obvious words in the Browser and **Suspend** them.

## Two card types

- **DE → EN** (recognition): see the German word and recall the meaning. This helps reading and listening.
- **EN → DE** (production): see the English and say the German word *with its article/forms*. This is harder, but it is how you learn genders.

If reviews feel too heavy, suspend production for now: Browser → search `card:2` → select all → Suspend.
Turn it back on later.

## How to review (this is what makes it work)

- **Say the word out loud** before flipping, and include the article: "*die* Abfahrt".
- Read the example sentence aloud on every card. It costs 5 seconds and teaches the word in context.
- Press **Again** honestly. Don't press Hard when you didn't know the word.
- Daily is better than long sessions. 25 minutes every day beats 3 hours on Sunday.
- Combine with reading: the graded readers in `books/graded/` (A2) are good to read alongside the A2 deck.

## Rebuilding

```
python3 anki/parse_goethe.py   # PDF -> anki/b1_entries.json
python3 anki/build_deck.py     # + translations/ -> .apkg (use --no-audio to skip TTS)
```

To fix a translation, edit `anki/translations/en_*.txt` (`id|english`) and rebuild.
Notes have stable IDs, so re-importing updates your cards and keeps your review history.
