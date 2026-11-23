"""Build an Anki deck (.apkg) from the parsed Goethe B1 list + English translations.

Usage:
  python3 anki/build_deck.py            # build with audio (generates missing mp3s)
  python3 anki/build_deck.py --no-audio
"""
import glob
import hashlib
import html
import json
import os
import random
import re
import subprocess
import threading
import sys
from concurrent.futures import ThreadPoolExecutor

import genanki

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRIES = os.path.join(ROOT, "b1_entries.json")
AUDIO_DIR = os.path.join(ROOT, "audio")
OUT = os.path.join(ROOT, "Deutsch_Goethe_A1-B1.apkg")
VOICE = "Anna"
WITH_AUDIO = "--no-audio" not in sys.argv

# ---------------------------------------------------------------- helpers
REGION = re.compile(r"\s*\((?:D|A|CH)(?:,\s*(?:D|A|CH))*\)")
UML = {"a": "ä", "o": "ö", "u": "ü", "A": "Ä", "O": "Ö", "U": "Ü"}


def load_translations():
    tr = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "translations", "en_*.txt"))):
        for line in open(p, encoding="utf-8"):
            line = line.rstrip("\n")
            if "|" in line:
                i, t = line.split("|", 1)
                tr[int(i)] = t.strip()
    return tr


def umlaut(stem):
    m = list(re.finditer(r"au|[aouAOU]", stem))
    if not m:
        return stem
    last = m[-1]
    s = last.group()
    rep = "äu" if s == "au" else UML[s]
    return stem[: last.start()] + rep + stem[last.end():]


def plural(noun, spec):
    """noun='Abfall', spec='¨-e' -> 'Abfälle'."""
    spec = spec.replace(" ", "").replace("“", "¨")
    spec = spec.split("/")[0]
    if spec in ("-", ""):
        return noun
    um = "¨" in spec
    suf = spec.replace("¨", "").lstrip("-")
    base = umlaut(noun) if um else noun
    if not re.fullmatch(r"[a-zäöüß]*", suf):
        return None
    return base + suf


def clean(raw):
    s = raw.split("→")[0]
    s = REGION.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" ;,")


def analyse(raw):
    """Return dict: word, gender, info (plural / verb forms)."""
    s = clean(raw)
    out = {"word": s, "gender": "", "info": ""}
    m = re.match(r"^(der|die|das)\s+([^,]+?)(?:,\s*(.+))?$", s)
    if m and " der " not in s and " die " not in s[4:]:
        art, noun, spec = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
        out["gender"] = art
        out["word"] = f"{art} {noun}"
        if spec:
            pl = plural(noun, spec) if re.fullmatch(r"[¨“\-a-zäöüs/ ]+", spec) else None
            if pl and pl != noun:
                out["info"] = f"Plural: die {pl}"
            elif pl == noun:
                out["info"] = "Plural: (no change)"
            elif re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß]+", spec):
                out["info"] = f"Plural: die {spec}"
            else:
                out["info"] = spec
        elif "(Pl.)" in raw or "Plural" in raw:
            out["info"] = "plural only"
        return out
    if re.match(r"^(der|die|das)\s", s):  # pairs like "der Kellner, - die Kellnerin, -nen"
        out["gender"] = s.split()[0]
        nouns = re.findall(r"\b(der|die|das)\s+([A-ZÄÖÜ][\wäöüß\-]*)", s)
        if len(nouns) >= 2:
            out["word"] = " / ".join(f"{a} {n}" for a, n in nouns)
        return out
    # verbs: "abbiegen, biegt ab, bog ab, ist abgebogen"
    parts = [p.strip() for p in s.split(",")]
    if len(parts) >= 3 and re.search(r"\b(hat|ist)\s", s):
        out["word"] = parts[0]
        out["info"] = ", ".join(parts[1:])
    return out


def audio_file(text, kind):
    h = hashlib.sha1(f"{VOICE}|{text}".encode()).hexdigest()[:16]
    return f"de_{kind}_{h}.mp3"


def tts(job):
    text, fname = job
    path = os.path.join(AUDIO_DIR, fname)
    if os.path.exists(path):
        return
    aiff = f"{path[:-4]}.{os.getpid()}.{threading.get_ident()}.aiff"
    subprocess.run(["say", "-v", VOICE, "-o", aiff, text], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", aiff, "-ac", "1",
                    "-b:a", "48k", path], check=True)
    os.remove(aiff)


# ---------------------------------------------------------------- model
CSS = """
.card { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 22px;
        text-align: center; color: #1d1d1f; background: #fafafa; padding: 12px; }
.night_mode .card, .nightMode .card { color: #eee; background: #1e1e1e; }
.word { font-size: 38px; font-weight: 600; margin: 18px 0 6px; }
.der { color: #1565c0; } .die { color: #c62828; } .das { color: #2e7d32; }
.night_mode .der { color: #64b5f6; } .night_mode .die { color: #ef9a9a; } .night_mode .das { color: #81c784; }
.info { font-size: 17px; color: #777; margin-bottom: 8px; }
.en { font-size: 28px; margin: 14px 0; }
.ex { font-size: 19px; text-align: left; max-width: 640px; margin: 16px auto 0;
      border-left: 3px solid #bbb; padding-left: 12px; line-height: 1.45; }
.ex li { margin-bottom: 6px; }
.tag { font-size: 12px; color: #999; margin-top: 18px; }
.hint { font-size: 15px; color: #999; }
"""

FRONT_DE = """<div class="word {{Gender}}">{{German}}</div>{{Audio}}"""
BACK_DE = """{{FrontSide}}
<div class="info">{{Info}}</div>
<hr id=answer>
<div class="en">{{English}}</div>
<div class="ex">{{Examples}}</div>{{ExampleAudio}}
<div class="tag">{{Level}}</div>"""

FRONT_EN = """{{#Reverse}}<div class="en">{{English}}</div>
<div class="hint">→ Deutsch (with article / forms)</div>{{/Reverse}}"""
BACK_EN = """{{FrontSide}}
<hr id=answer>
<div class="word {{Gender}}">{{German}}</div>{{Audio}}
<div class="info">{{Info}}</div>
<div class="ex">{{Examples}}</div>
<div class="tag">{{Level}}</div>"""

MODEL = genanki.Model(
    1607392319,
    "Goethe Vocab (DE-EN)",
    fields=[{"name": n} for n in
            ["German", "English", "Gender", "Info", "Examples", "Level",
             "Audio", "ExampleAudio", "Forms", "Reverse", "ID"]],
    templates=[
        {"name": "DE → EN", "qfmt": FRONT_DE, "afmt": BACK_DE},
        {"name": "EN → DE", "qfmt": FRONT_EN, "afmt": BACK_EN},
    ],
    css=CSS,
    sort_field_index=0,
)

DECK_IDS = {"A1": 2059400110, "A2": 2059400111, "B1": 2059400112}
DECK_NAMES = {"A1": "Deutsch (Goethe)::1 – A1", "A2": "Deutsch (Goethe)::2 – A2",
              "B1": "Deutsch (Goethe)::3 – B1"}


class VocabNote(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for("goethe-b1", self.fields[10])


def main():
    entries = json.load(open(ENTRIES, encoding="utf-8"))
    tr = load_translations()
    os.makedirs(AUDIO_DIR, exist_ok=True)

    notes, jobs, seen = [], [], set()
    for e in entries:
        en = tr.get(e["id"], "")
        if not en or en == "X":
            continue
        a = analyse(e["raw"])
        key = (a["word"], en)
        if key in seen:
            continue
        seen.add(key)
        exs = [x for x in e["examples"] if x][:3]
        ex_html = ("<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in exs) + "</ul>") if exs else ""
        wa = ea = ""
        if WITH_AUDIO:
            speak = re.sub(r"[\(\)/]", " ", a["word"]).replace("-", "").strip()
            fw = audio_file(speak, "w")
            jobs.append((speak, fw))
            wa = f"[sound:{fw}]"
            if exs:
                fe = audio_file(exs[0], "s")
                jobs.append((exs[0], fe))
                ea = f"[sound:{fe}]"
        level = e["level"] + (" · regional (A/CH)" if e["regional"] else "")
        notes.append((e["level"], e["regional"], VocabNote(
            model=MODEL,
            fields=[html.escape(a["word"]), html.escape(en), a["gender"], html.escape(a["info"]),
                    ex_html, level, wa, ea, html.escape(e["raw"]), "y", str(e["id"])],
            tags=[f"goethe::{e['level']}"] + (["regional"] if e["regional"] else []),
        )))

    if WITH_AUDIO:
        todo = sorted({j for j in jobs if not os.path.exists(os.path.join(AUDIO_DIR, j[1]))})
        print(f"audio: {len(jobs)} files, {len(todo)} to generate")
        with ThreadPoolExecutor(max_workers=8) as ex:
            for i, _ in enumerate(ex.map(tts, todo), 1):
                if i % 250 == 0:
                    print(f"  {i}/{len(todo)}", flush=True)

    # Shuffle within each level so you don't get 30 "ab-" verbs in a row;
    # regional (Austrian/Swiss-only) words go to the end of their level.
    rnd = random.Random(42)
    decks = {lv: genanki.Deck(DECK_IDS[lv], DECK_NAMES[lv]) for lv in DECK_IDS}
    due = 0
    for lv in ("A1", "A2", "B1"):
        group = [n for n in notes if n[0] == lv]
        rnd.shuffle(group)
        group.sort(key=lambda n: n[1])
        for _, _, note in group:
            note.due = due
            due += 1
            decks[lv].add_note(note)

    pkg = genanki.Package(list(decks.values()))
    if WITH_AUDIO:
        pkg.media_files = sorted({os.path.join(AUDIO_DIR, f) for _, f in jobs})
    pkg.write_to_file(OUT)
    counts = {lv: len(d.notes) for lv, d in decks.items()}
    print("notes per level:", counts, "total", sum(counts.values()))
    print("->", OUT)


if __name__ == "__main__":
    main()
