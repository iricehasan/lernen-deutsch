"""Parse the Goethe-Zertifikat B1 Wortliste PDF into structured entries (JSON).

Each PDF page has two halves; each half has a word column and an example column.
Entries are separated by vertical gaps; examples are aligned with their headword.
"""
import json
import re
import sys
import unicodedata

import pymupdf

SRC = sys.argv[1] if len(sys.argv) > 1 else "goethe_word_list/Goethe-Zertifikat_B1_Wortliste.pdf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "anki/b1_entries.json"
FIRST_PAGE, LAST_PAGE = 15, 101  # 0-indexed, alphabetical list only

LINE = 11.0


def lines_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            sp = l["spans"]
            if round(sp[0]["size"]) != 8:
                continue
            t = unicodedata.normalize("NFC", "".join(s["text"] for s in sp)).rstrip()
            if not t.strip():
                continue
            out.append((l["bbox"][0], l["bbox"][1], t))
    return out


def is_verb_in_progress(text):
    first = text.split(",")[0].strip()
    if "," not in text or not first:
        return False
    w = re.sub(r"^\(?sich\)?\s+", "", first)
    if not w[:1].islower() or re.match(r"^(der|die|das)\s", w):
        return False
    return not re.search(r"\b(hat|ist|hat/ist)\s", text)


def join_lines(parts):
    s = ""
    for p in parts:
        p = p.strip()
        if not s:
            s = p
        elif s.endswith("-") and p[:1].islower() and not s.endswith(" -"):
            s = s[:-1] + p
        else:
            s += " " + p
    return re.sub(r"\s+", " ", s).strip()


def group_words(wlines):
    """wlines: sorted list of (x, y, text). Returns list of dicts with y, x, lines."""
    entries = []
    for x, y, t in wlines:
        if entries:
            e = entries[-1]
            prev = e["lines"][-1].rstrip()
            gap = y - e["y_last"]
            cont = gap < LINE + 3 and (
                re.search(r"[,:→;\-]$", prev)
                or t.lstrip().startswith("→")
                or is_verb_in_progress(join_lines(e["lines"]))
            )
            if cont:
                e["lines"].append(t)
                e["y_last"] = y
                continue
        entries.append({"x": x, "y": y, "y_last": y, "lines": [t]})
    return entries


def group_examples(elines, entry_ys=()):
    blocks = []
    for x, y, t in elines:
        numbered = re.match(r"^\d+\.\s", t.strip()) is not None
        at_new_entry = any(-6 <= ey - y <= 2 for ey in entry_ys)
        prev_ended = bool(blocks) and re.search(r"[.!?…\"“]\s*$", blocks[-1]["items"][-1][-1])
        if blocks and at_new_entry and prev_ended and y > blocks[-1]["y"] + 3:
            blocks.append({"y": y, "y_last": y, "items": [[t.strip()]]})
        elif blocks and y - blocks[-1]["y_last"] < LINE + 3:
            b = blocks[-1]
            if numbered:
                b["items"].append([t.strip()])
            else:
                b["items"][-1].append(t)
            b["y_last"] = y
        else:
            blocks.append({"y": y, "y_last": y, "items": [[t.strip()]]})
    return blocks


def main():
    doc = pymupdf.open(SRC)
    all_entries = []
    for pno in range(FIRST_PAGE, LAST_PAGE + 1):
        ls = lines_of(doc[pno])
        for half in (0, 1):
            if half == 0:
                w = [l for l in ls if l[0] < 125]
                ex = [l for l in ls if 125 <= l[0] < 300]
            else:
                w = [l for l in ls if 300 <= l[0] < 405]
                ex = [l for l in ls if l[0] >= 405]
            w.sort(key=lambda l: (l[1], l[0]))
            ex.sort(key=lambda l: (l[1], l[0]))
            ents = group_words(w)
            for e in ents:
                e["examples"] = []
            for b in group_examples(ex, [e["y"] for e in ents]):
                # attach to the entry starting closest at/above the block
                cands = [e for e in ents if e["y"] <= b["y"] + 6]
                target = cands[-1] if cands else (all_entries[-1] if all_entries else None)
                if target is None:
                    continue
                for it in b["items"]:
                    s = join_lines(it)
                    s = re.sub(r"^\d+\.\s*", "", s)
                    target["examples"].append(s)
            # entries without examples directly below another entry share its examples
            for i, e in enumerate(ents):
                if not e["examples"] and i > 0 and e["y"] - ents[i - 1]["y_last"] < LINE + 3:
                    e["examples"] = ents[i - 1]["examples"]
            for e in ents:
                all_entries.append(
                    {
                        "raw": join_lines(e["lines"]),
                        "sub": e["x"] > (40 if half == 0 else 320),
                        "examples": list(e["examples"]),
                        "page": pno + 1,
                    }
                )
    for i, e in enumerate(all_entries):
        e["id"] = i
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=1)
    print(len(all_entries), "entries ->", OUT)


if __name__ == "__main__":
    main()
