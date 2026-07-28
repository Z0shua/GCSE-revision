#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_flashcards.py
==================
Anki flashcard generator for the GCSE Year 11 Revision Dashboard
(King Edward VI Five Ways School curriculum, Birmingham).

WHAT IT DOES
    Reads the SAME shared topic matrix used by index.html and study.html
    (data.js) and writes two Anki-importable CSV files:

        gcse_flashcards.csv   Basic notes      -> Front, Back, Tags
        gcse_cloze.csv        Cloze notes      -> Text, Back Extra, Tags
        gcse_study_matrix.csv Reference sheet  -> the full subject matrix

    Both card files begin with Anki import directives and a 3-step
    import instruction comment block, so the student only needs the free
    Anki app - no Python, no dependencies, no accounts.

WHY IT READS data.js RATHER THAN EMBEDDING ITS OWN COPY
    Acceptance criterion 4 requires the shared data object to be IDENTICAL
    across all four deliverables. Pasting a second copy of the matrix into
    this file would guarantee the two copies drift apart the first time a
    topic is edited. Instead, data.js is the single source of truth and
    this script parses the JSON payload out of it using only the standard
    library. If data.js is missing, the script says exactly what to do.

USAGE
    python3 make_flashcards.py                       # uses ./data.js
    python3 make_flashcards.py --data path/to/data.js
    python3 make_flashcards.py --outdir ./out
    python3 make_flashcards.py --subject biology     # one subject only
    python3 make_flashcards.py --list                # list subject ids
    python3 make_flashcards.py --check               # validate only, write nothing

REQUIREMENTS
    Python 3.7 or newer. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys

# --------------------------------------------------------------------------- #
# Anki import instructions, written into the top of every generated CSV.
# Lines beginning with "#" are treated by Anki as directives or ignored, so
# they never become cards.
# --------------------------------------------------------------------------- #

BASIC_HEADER = [
    "#separator:Comma",
    "#html:true",
    "#notetype:Basic",
    "#deck:GCSE Year 11",
    "#tags column:3",
    "#",
    "# ===== HOW TO IMPORT THIS FILE INTO ANKI - 3 STEPS =====",
    "# STEP 1. Open the free Anki desktop app, then choose File > Import and",
    "#         select this file (gcse_flashcards.csv).",
    "# STEP 2. Check the dialog shows Notetype 'Basic', Deck 'GCSE Year 11',",
    "#         Fields separated by 'Comma', and 'Allow HTML in fields' ticked.",
    "#         Set the existing-notes option to 'Update' so re-imports do not",
    "#         create duplicates.",
    "# STEP 3. Click Import, then Sync (or copy the collection to your device).",
    "#         Study the deck daily; the tags let you filter by subject and topic,",
    "#         for example tag:Biology::Homeostasis_and_response",
    "# =======================================================",
    "#",
]

CLOZE_HEADER = [
    "#separator:Comma",
    "#html:true",
    "#notetype:Cloze",
    "#deck:GCSE Year 11::Cloze definitions",
    "#tags column:3",
    "#",
    "# ===== HOW TO IMPORT THIS FILE INTO ANKI - 3 STEPS =====",
    "# STEP 1. Open the free Anki desktop app, choose File > Import and select",
    "#         this file (gcse_cloze.csv).",
    "# STEP 2. Check the dialog shows Notetype 'Cloze', Deck",
    "#         'GCSE Year 11::Cloze definitions', Fields separated by 'Comma',",
    "#         and that the first column is mapped to the field 'Text'.",
    "# STEP 3. Click Import. Each {{c1::...}} gap becomes its own card, so one",
    "#         sentence can produce several cards - that is intended.",
    "# =======================================================",
    "#",
]

MATRIX_HEADER = [
    "# GCSE Year 11 study matrix - reference sheet, not for Anki import.",
    "# One row per topic. Open in any spreadsheet app.",
    "#",
]

# --------------------------------------------------------------------------- #
# Loading the shared data object
# --------------------------------------------------------------------------- #

DATA_MARKER = "const GCSE_DATA"


def default_data_path() -> str:
    """data.js normally sits next to this script; also look in ./site for
    older layouts and in the current working directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "data.js"),
                      os.path.join(here, "site", "data.js"),
                      os.path.join(os.getcwd(), "data.js")):
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(here, "data.js")


def matching_brace(text: str, start: int) -> int:
    """Index of the '}' that closes the '{' at `start`.

    String-aware, so the {{c1::...}} gaps inside cloze sentences and any
    braces in resource labels cannot throw the count off. Returns -1 if the
    object is unbalanced.
    """
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def load_data(path: str) -> dict:
    """Parse the JSON payload out of data.js using the standard library only."""
    if not os.path.isfile(path):
        sys.exit(
            "ERROR: could not find the shared data file:\n"
            "    %s\n\n"
            "data.js is the single source of truth shared by index.html,\n"
            "study.html and this script. Fix by either:\n"
            "  (a) running this script from the project folder that contains data.js, or\n"
            "  (b) passing the path explicitly:  python3 make_flashcards.py --data /path/to/data.js\n"
            "If data.js has never been generated, run:  python3 build_data.py" % path
        )

    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()

    marker = text.find(DATA_MARKER)
    if marker == -1:
        sys.exit("ERROR: %s does not declare 'const GCSE_DATA'. Is it the right file?" % path)

    start = text.find("{", marker)
    if start == -1:
        sys.exit("ERROR: could not locate the JSON object inside %s." % path)
    end = matching_brace(text, start)
    if end == -1:
        sys.exit("ERROR: the data object in %s has unbalanced braces." % path)

    blob = text[start:end + 1]
    try:
        data = json.loads(blob)
    except ValueError as exc:
        sys.exit("ERROR: the data object in %s is not valid JSON: %s" % (path, exc))

    if "subjects" not in data or not isinstance(data["subjects"], list):
        sys.exit("ERROR: the data object in %s has no 'subjects' list." % path)
    return data


def payload_checksum(data: dict) -> str:
    """SHA-256 over the canonical payload, ignoring the stored checksum itself."""
    copy = dict(data)
    copy.pop("dataChecksum", None)
    canonical = json.dumps(copy, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

CLOZE_RE = re.compile(r"\{\{c(\d+)::")


def validate(data: dict) -> list:
    """Return a list of human-readable problems. Empty list means clean."""
    problems = []
    seen_subject_ids = set()

    for subject in data["subjects"]:
        for field in ("id", "name", "board", "specCode", "topics", "pastPapers", "resources"):
            if field not in subject:
                problems.append("subject %r is missing field %r" % (subject.get("name"), field))
        sid = subject.get("id")
        if sid in seen_subject_ids:
            problems.append("duplicate subject id %r" % sid)
        seen_subject_ids.add(sid)

        fronts = {}
        for topic in subject.get("topics", []):
            if not topic.get("subtopics"):
                problems.append("%s / %s has no sub-topics" % (sid, topic.get("id")))
            for card in topic.get("cards", []):
                front = (card.get("front") or "").strip()
                back = (card.get("back") or "").strip()
                if not front or not back:
                    problems.append("%s / %s has a card with an empty side" % (sid, topic.get("id")))
                key = front.lower()
                if key in fronts:
                    problems.append(
                        "%s: duplicate question %r in topics %s and %s"
                        % (sid, front[:60], fronts[key], topic.get("id"))
                    )
                else:
                    fronts[key] = topic.get("id")
            for sentence in topic.get("cloze", []):
                if not CLOZE_RE.search(sentence or ""):
                    problems.append(
                        "%s / %s has a cloze sentence with no {{c1::...}} gap: %r"
                        % (sid, topic.get("id"), (sentence or "")[:60])
                    )
                if (sentence or "").count("{{") != (sentence or "").count("}}"):
                    problems.append(
                        "%s / %s has unbalanced cloze braces: %r"
                        % (sid, topic.get("id"), (sentence or "")[:60])
                    )
    return problems


# --------------------------------------------------------------------------- #
# Tags
# --------------------------------------------------------------------------- #

def tag_token(text: str) -> str:
    """Anki tags cannot contain spaces; '::' builds a hierarchy."""
    token = re.sub(r"[^0-9A-Za-z]+", "_", str(text)).strip("_")
    return token or "Untitled"


def tags_for(subject: dict, topic: dict, kind: str) -> str:
    parts = [
        "GCSE",
        "Year11",
        tag_token(subject["name"]),
        tag_token(subject["name"]) + "::" + tag_token(topic["name"]),
        tag_token(subject["board"].split()[0]) + "::" + tag_token(subject["specCode"]),
        tag_token(kind),
    ]
    if not subject.get("boardVerified", False):
        parts.append("BOARD_UNVERIFIED")
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return " ".join(out)


# --------------------------------------------------------------------------- #
# Card building
# --------------------------------------------------------------------------- #

def clean(text: str) -> str:
    """Collapse whitespace; keep the text safe for a single CSV field."""
    return re.sub(r"\s+", " ", str(text)).strip()


def source_footer(subject: dict, topic: dict) -> str:
    return (
        '<br><br><span style="font-size:12px;color:#78716c">%s &middot; %s %s &middot; %s</span>'
        % (clean(subject["name"]), clean(subject["board"]), clean(subject["specCode"]), clean(topic["name"]))
    )


def build_basic_rows(data: dict, only: str = None) -> list:
    rows = []
    for subject in data["subjects"]:
        if only and subject["id"] != only:
            continue
        for topic in subject["topics"]:
            for card in topic.get("cards", []):
                front = clean(card["front"])
                back = clean(card["back"]) + source_footer(subject, topic)
                rows.append([front, back, tags_for(subject, topic, "Basic")])
    return rows


CARD_KINDS = ("formula", "def", "quote", "data")


def reference_tags(subject: dict, section: dict) -> str:
    parts = [
        "GCSE",
        "Year11",
        tag_token(subject["name"]),
        tag_token(subject["name"]) + "::Reference::" + tag_token(section["title"]),
        tag_token(subject["board"].split()[0]) + "::" + tag_token(subject["specCode"]),
        "Reference",
    ]
    if not subject.get("boardVerified", False):
        parts.append("BOARD_UNVERIFIED")
    seen, out = set(), []
    for part in parts:
        if part not in seen:
            seen.add(part)
            out.append(part)
    return " ".join(out)


def build_reference_rows(data: dict, only: str = None) -> list:
    """Turn the offline reference sheets into recall cards.

    Only lookup-shaped sections become cards: formulae, definitions, quotations and
    figures. Checklists, methods and sentence stems are read, not recalled, so they
    stay in the notes page only.
    """
    rows = []
    for subject in data["subjects"]:
        if only and subject["id"] != only:
            continue
        offline = subject.get("offline") or {}
        for section in offline.get("sections", []):
            if section["kind"] not in CARD_KINDS:
                continue
            if section["title"] == "Exam-day plan":
                continue
            for item in section["items"]:
                front = (
                    "%s<br><span style=\"font-size:12px;color:#78716c\">%s &middot; %s</span>"
                    % (clean(item["term"]), clean(subject["name"]), clean(section["title"]))
                )
                back = (
                    "%s<br><br><span style=\"font-size:12px;color:#78716c\">%s &middot; %s %s</span>"
                    % (clean(item["detail"]), clean(subject["name"]),
                       clean(subject["board"]), clean(subject["specCode"]))
                )
                rows.append([front, back, reference_tags(subject, section)])
    return rows


def build_cloze_rows(data: dict, only: str = None) -> list:
    rows = []
    for subject in data["subjects"]:
        if only and subject["id"] != only:
            continue
        for topic in subject["topics"]:
            for sentence in topic.get("cloze", []):
                text = clean(sentence)
                extra = "%s &middot; %s (%s %s)" % (
                    clean(topic["name"]), clean(subject["name"]),
                    clean(subject["board"]), clean(subject["specCode"]),
                )
                rows.append([text, extra, tags_for(subject, topic, "Cloze")])
    return rows


def build_matrix_rows(data: dict, only: str = None) -> list:
    rows = [[
        "Subject", "Exam board", "Board verified", "Spec code", "Tier",
        "Papers", "Topic", "Core sub-topics", "Official past papers",
        "Free revision resources", "Basic cards", "Cloze cards", "Board note",
    ]]
    for subject in data["subjects"]:
        if only and subject["id"] != only:
            continue
        resources = " | ".join("%s: %s" % (clean(r["label"]), r["url"]) for r in subject["resources"])
        for topic in subject["topics"]:
            rows.append([
                clean(subject["name"]),
                clean(subject["board"]),
                "yes" if subject.get("boardVerified") else "NO - provisional",
                clean(subject["specCode"]),
                clean(subject["tier"]),
                clean(subject["papers"]),
                clean(topic["name"]),
                "; ".join(clean(s) for s in topic["subtopics"]),
                subject["pastPapers"]["url"],
                resources,
                str(len(topic.get("cards", []))),
                str(len(topic.get("cloze", []))),
                clean(subject.get("boardNote", "")),
            ])
    return rows


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def write_csv(path: str, header_lines: list, column_names: list, rows: list) -> None:
    # newline="" is required by the csv module; utf-8-sig keeps Anki and Excel
    # happy with accented characters such as those in the Spanish deck.
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        for line in header_lines:
            fh.write(line + "\n")
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL, lineterminator="\n")
        if column_names:
            fh.write("# columns: " + ", ".join(column_names) + "\n")
        for row in rows:
            writer.writerow(row)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate Anki-importable CSV flashcards from the shared GCSE data object.")
    parser.add_argument("--data", default=default_data_path(),
                        help="path to data.js (default: ./data.js next to this script)")
    parser.add_argument("--outdir", default=".",
                        help="directory to write the CSV files into (default: current directory)")
    parser.add_argument("--subject", default=None,
                        help="restrict output to one subject id (see --list)")
    parser.add_argument("--list", action="store_true", help="list subject ids and exit")
    parser.add_argument("--check", action="store_true", help="validate the data and exit without writing")
    args = parser.parse_args(argv)

    data = load_data(args.data)

    if args.list:
        print("Subjects in %s:" % args.data)
        for s in data["subjects"]:
            print("  %-20s %s (%s %s, %d topics)"
                  % (s["id"], s["name"], s["board"], s["specCode"], len(s["topics"])))
        return 0

    problems = validate(data)
    if problems:
        print("Data validation found %d problem(s):" % len(problems))
        for p in problems:
            print("  - " + p)
        if args.check:
            return 1
        print("Refusing to write cards from invalid data.")
        return 1

    stored = data.get("dataChecksum")
    recomputed = payload_checksum(data)
    checksum_ok = (stored is None) or (stored == recomputed)

    if args.check:
        print("Data is valid. %d subjects, %d topics, %d sub-topics, %d basic cards, %d cloze sentences."
              % (len(data["subjects"]),
                 sum(len(s["topics"]) for s in data["subjects"]),
                 sum(len(t["subtopics"]) for s in data["subjects"] for t in s["topics"]),
                 sum(len(t.get("cards", [])) for s in data["subjects"] for t in s["topics"]),
                 sum(len(t.get("cloze", [])) for s in data["subjects"] for t in s["topics"])))
        print("Checksum %s (%s)" % (recomputed, "matches data.js" if checksum_ok else "DOES NOT match data.js"))
        return 0

    subject_ids = [s["id"] for s in data["subjects"]]
    if args.subject and args.subject not in subject_ids:
        sys.exit("ERROR: unknown subject id %r. Known ids: %s" % (args.subject, ", ".join(subject_ids)))

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    basic = build_basic_rows(data, args.subject) + build_reference_rows(data, args.subject)
    cloze = build_cloze_rows(data, args.subject)
    matrix = build_matrix_rows(data, args.subject)

    basic_path = os.path.join(outdir, "gcse_flashcards.csv")
    cloze_path = os.path.join(outdir, "gcse_cloze.csv")
    matrix_path = os.path.join(outdir, "gcse_study_matrix.csv")

    write_csv(basic_path, BASIC_HEADER, ["Front", "Back", "Tags"], basic)
    write_csv(cloze_path, CLOZE_HEADER, ["Text", "Back Extra", "Tags"], cloze)
    write_csv(matrix_path, MATRIX_HEADER, matrix[0], matrix[1:])

    print("Source of truth : %s" % os.path.abspath(args.data))
    print("Checksum        : %s%s" % (recomputed, "" if checksum_ok else "  (WARNING: differs from the value stored in data.js)"))
    print("")
    print("Wrote %s  (%d basic cards)" % (basic_path, len(basic)))
    print("Wrote %s  (%d cloze sentences)" % (cloze_path, len(cloze)))
    print("Wrote %s  (%d topic rows)" % (matrix_path, len(matrix) - 1))
    print("")
    unverified = [s["name"] for s in data["subjects"] if not s.get("boardVerified")]
    if unverified:
        print("NOTE: exam board still unconfirmed for: %s" % ", ".join(unverified))
        print("      Those cards carry the tag BOARD_UNVERIFIED so they are easy to find and fix.")
    print("Send the student gcse_flashcards.csv and gcse_cloze.csv. The 3-step import")
    print("instructions are inside each file, at the top.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
