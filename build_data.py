#!/usr/bin/env python3
"""Assemble the single source of truth (data.js) from the per-subject JSON files.

Run:  python3 build_data.py
Output: ./data.js  and prints a SHA-256 of the canonical JSON payload.
"""
import datetime
import hashlib
import re
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT_DIR = HERE  # data.js sits next to index.html so GitHub Pages serves it

ORDER = [
    "english-language",
    "english-literature",
    "maths",
    "biology",
    "chemistry",
    "physics",
    "geography",
    "spanish",
    "religious-studies",
    "food-technology",
]

REQUIRED_SUBJECT_KEYS = {
    "id", "name", "board", "boardVerified", "boardNote",
    "specCode", "tier", "accent", "papers", "pastPapers", "resources", "topics",
    "exams", "examNote", "offline",
}

OFFLINE_KINDS = {"formula", "def", "list", "quote", "method", "phrase", "data"}

DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")


def load_subject(sid):
    path = os.path.join(SRC, sid + ".json")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    missing = REQUIRED_SUBJECT_KEYS - set(data)
    if missing:
        sys.exit("ERROR %s missing keys: %s" % (sid, sorted(missing)))
    if data["id"] != sid:
        sys.exit("ERROR %s has mismatched id %r" % (sid, data["id"]))
    seen = set()
    for topic in data["topics"]:
        for key in ("id", "name", "subtopics", "cards", "cloze"):
            if key not in topic:
                sys.exit("ERROR %s topic %r missing %r" % (sid, topic.get("name"), key))
        if topic["id"] in seen:
            sys.exit("ERROR duplicate topic id %s in %s" % (topic["id"], sid))
        seen.add(topic["id"])
        if not topic["subtopics"]:
            sys.exit("ERROR %s topic %s has no subtopics" % (sid, topic["id"]))
    off = data["offline"]
    for key in ("commandWords", "sections"):
        if not off.get(key):
            sys.exit("ERROR %s offline block missing or empty %r" % (sid, key))
    for cw in off["commandWords"]:
        if set(cw) != {"word", "means", "doThis"}:
            sys.exit("ERROR %s command word %r has wrong keys" % (sid, cw.get("word")))
    titles = set()
    for sec in off["sections"]:
        if not set(sec) <= {"title", "kind", "items", "note"}:
            sys.exit("ERROR %s offline section %r has unexpected keys" % (sid, sec.get("title")))
        for key in ("title", "kind", "items"):
            if key not in sec:
                sys.exit("ERROR %s offline section %r missing %r" % (sid, sec.get("title"), key))
        if sec["kind"] not in OFFLINE_KINDS:
            sys.exit("ERROR %s offline section %r has bad kind %r" % (sid, sec["title"], sec["kind"]))
        if sec["title"] in titles:
            sys.exit("ERROR %s has duplicate offline section title %r" % (sid, sec["title"]))
        titles.add(sec["title"])
        if len(sec["items"]) < 6:
            sys.exit("ERROR %s offline section %r has only %d items"
                     % (sid, sec["title"], len(sec["items"])))
        for item in sec["items"]:
            if set(item) != {"term", "detail"}:
                sys.exit("ERROR %s offline item in %r has wrong keys: %s"
                         % (sid, sec["title"], sorted(item)))
            if not item["term"].strip() or not item["detail"].strip():
                sys.exit("ERROR %s offline item in %r is empty" % (sid, sec["title"]))
    if not any(s["title"] == "Exam-day plan" for s in off["sections"]):
        sys.exit("ERROR %s offline block has no 'Exam-day plan' section" % sid)
    if not data["boardVerified"]:
        sys.exit("ERROR %s is not board-verified; every KEFW board is now confirmed" % sid)
    if not data["exams"]:
        sys.exit("ERROR %s has no exams listed" % sid)
    for exam in data["exams"]:
        for key in ("code", "name", "date", "session", "duration"):
            if key not in exam:
                sys.exit("ERROR %s exam %r missing %r" % (sid, exam.get("code"), key))
        if not DATE_RE.match(exam["date"]):
            sys.exit("ERROR %s exam %s has bad date %r" % (sid, exam["code"], exam["date"]))
        try:
            datetime.date(*[int(p) for p in exam["date"].split("-")])
        except ValueError:
            sys.exit("ERROR %s exam %s date is not a real date" % (sid, exam["code"]))
    return data


def main():
    subjects = [load_subject(sid) for sid in ORDER]

    payload = {
        "schemaVersion": 3,
        "title": "GCSE Year 11 Revision Dashboard",
        "school": "King Edward VI Five Ways School, Birmingham",
        "curriculumSource": "https://www.kefw.org/academic/curriculum/",
        "academicYear": "Year 11, academic year 2026 to 2027",
        "boardVerificationNote": (
            "Every board below is verified against the examination boards list published by "
            "King Edward VI Five Ways School, cross-checked against the KEFW Curriculum "
            "Intent PDFs for each subject. Year 11 boards: English AQA, English Literature "
            "OCR, Maths Pearson Edexcel, Biology / Chemistry / Physics AQA, Geography "
            "Pearson Edexcel B, Spanish Pearson Edexcel, Religious Studies AQA, Food "
            "Technology AQA."
        ),
        "boardSource": (
            "https://view.publitas.com/king-edward-vi-five-ways-schoo/examination-boards/page/1"
        ),
        "examSeries": {
            "name": "Summer 2027 (June series)",
            "firstExam": "2027-05-10",
            "lastExam": "2027-06-18",
            "contingencyDay": "2027-06-23",
            "resultsDay": "2027-08-19",
            "source": "https://www.jcq.org.uk/wp-content/uploads/sites/2/2026/05/Key_Dates_June2027_FINAL.pdf",
            "note": (
                "National common-timetable dates from JCQ key dates for the June 2027 series. "
                "Per-paper dates come from the AQA provisional timetable (v1.0, January 2026), "
                "the Pearson Edexcel provisional summer 2027 timetable and the OCR final "
                "June 2027 timetable. The AQA and Pearson dates can still move."
            ),
        },
        "subjects": subjects,
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    payload["dataChecksum"] = digest

    pretty = json.dumps(payload, indent=2, ensure_ascii=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_js = os.path.join(OUT_DIR, "data.js")
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("/* GCSE Year 11 Revision Dashboard - SINGLE SOURCE OF TRUTH\n")
        fh.write(" * Generated by build_data.py from src/*.json. Do not hand-edit.\n")
        fh.write(" * Consumed identically by index.html, study.html and make_flashcards.py.\n")
        fh.write(" * SHA-256 of canonical payload: %s\n" % digest)
        fh.write(" */\n")
        fh.write("const GCSE_DATA = ")
        fh.write(pretty)
        fh.write(";\n")
        fh.write("if (typeof module !== 'undefined') { module.exports = GCSE_DATA; }\n")

    topics = sum(len(s["topics"]) for s in subjects)
    subtopics = sum(len(t["subtopics"]) for s in subjects for t in s["topics"])
    cards = sum(len(t["cards"]) for s in subjects for t in s["topics"])
    cloze = sum(len(t["cloze"]) for s in subjects for t in s["topics"])

    print("Wrote %s" % out_js)
    off_sections = sum(len(s["offline"]["sections"]) for s in subjects)
    off_items = sum(len(sec["items"]) for s in subjects for sec in s["offline"]["sections"])
    off_cw = sum(len(s["offline"]["commandWords"]) for s in subjects)

    print("subjects=%d topics=%d subtopics=%d basic_cards=%d cloze_cards=%d total_cards=%d"
          % (len(subjects), topics, subtopics, cards, cloze, cards + cloze))
    print("offline: sections=%d items=%d command_words=%d"
          % (off_sections, off_items, off_cw))
    print("checksum=%s" % digest)


if __name__ == "__main__":
    main()
