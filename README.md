# GCSE Year 11 Revision and Study Dashboard

Static, free, account-free revision system mapped to the **King Edward VI Five Ways School** (Birmingham) Year 11 curriculum. Hosted on GitHub Pages. The student needs only a browser, plus the free Anki app for flashcards.

## Files

| File | What it is |
| --- | --- |
| `index.html` | Deliverable 2 - revision tracker: Shaky/Nearly/Solid ratings on a spaced-review ladder, due-today queue, blurt mode, focus timer, past-paper log, week rota, exam countdown, JSON export/import, dark mode |
| `study.html` | Deliverable 3 - AI room: Ask it, Quiz me, Check my blurt, Teach it back. Browser-only, key stored in localStorage, ratings write straight into the tracker |
| `data.js` | **Single source of truth.** `const GCSE_DATA = {...}` - every subject, topic, sub-topic, flashcard and link |
| `STUDY_MATRIX.md` | Deliverable 1 - the topic matrix, generated from `data.js` |
| `make_flashcards.py` | Deliverable 4 - Anki CSV generator, standard library only |
| `make_matrix.py` | Regenerates `STUDY_MATRIX.md` from `data.js` |
| `build_data.py` | Rebuilds `data.js` from the per-subject files in `src/` |
| `src/*.json` | Editable per-subject source files |
| `gcse_flashcards.csv` | 334 basic Anki cards (Front, Back, Tags) |
| `gcse_cloze.csv` | 163 cloze-deletion Anki cards (Text, Back Extra, Tags) |
| `gcse_study_matrix.csv` | The matrix as a spreadsheet, for reference |

## Deployment guide (10 steps)

1. Sign in at [github.com](https://github.com) and click **New repository**. Name it `gcse-revision`, set it to **Public**, and click **Create repository**.
2. On the new repository page click **uploading an existing file**.
3. Drag in `index.html`, `study.html`, `data.js`, `README.md`, `STUDY_MATRIX.md` and the three `.py` files, plus the `src` folder. Click **Commit changes**.
4. Click the **Settings** tab, then **Pages** in the left sidebar.
5. Under *Build and deployment* set **Source** to `Deploy from a branch`.
6. Set **Branch** to `main` and the folder to `/ (root)`, then click **Save**.
7. Wait two or three minutes, then reload the Pages settings screen. It shows the live address, in the form `https://YOUR-USERNAME.github.io/gcse-revision/`.
8. Open that address, tap **AI room** in the bottom bar, then **Set up**, and paste a free API key from [console.groq.com/keys](https://console.groq.com/keys). Click **Save**, then **Test connection**.
9. Send the student the address. Tell him to bookmark it and to press **Export progress** every Sunday, keeping the downloaded file in his cloud drive.
10. On your own machine run `python3 make_flashcards.py`, then email him `gcse_flashcards.csv` and `gcse_cloze.csv`. The import instructions are inside each file.

## Editing the content later

1. Edit the relevant file in `src/` (for example `src/biology.json`).
2. Run `python3 build_data.py` - this regenerates `data.js` and prints a new checksum.
3. Run `python3 make_matrix.py` and `python3 make_flashcards.py`.
4. Commit and push. All four deliverables stay in step automatically because they all read `data.js`.

## Exam board status

Verified from KEFW Curriculum Intent documents: Biology AQA 8461, Chemistry AQA 8462, Physics AQA 8463, Geography Pearson Edexcel B 1GB0, Spanish Pearson Edexcel 1SP1 (the 2024 reformed specification, which is what a Year 11 sits in summer 2027; the legacy 1SP0 papers are kept as a secondary link because there is more back catalogue).

**Unconfirmed - check with the school:** English Language (AQA 8700 assumed), English Literature (AQA 8702 and the Power and Conflict cluster assumed), Mathematics (Pearson Edexcel 1MA1 assumed; AQA 8300 is the alternative). KEFW publishes no consolidated exam-board list on its curriculum or subjects pages. These subjects are flagged in the dashboard, in `STUDY_MATRIX.md`, and with the Anki tag `BOARD_UNVERIFIED`.

## How the study system works

Built from what students actually report using, not from what looks impressive.

- **Rate, do not tick.** Every sub-topic is Shaky, Nearly or Solid. Ticking a box records that you looked at something; rating records whether you could retrieve it. Solid moves the item up a spaced-review ladder (1, 3, 7, 21, 60 days), Nearly brings it back in two days, Shaky brings it back tomorrow.
- **Due for a second look.** The Today tab interleaves whatever has come back round, mixed across subjects rather than blocked by subject.
- **Blurt mode.** Five-minute timer, book shut, type everything you remember, then reveal the checklist and mark what you missed. The AI room's *Check my blurt* does the same job against the specification and returns what you got, what is missing, what is muddled and what to do next.
- **Teach it back.** The AI plays a Year 8 who knows nothing. If your explanation is vague, the questions it asks show you exactly where.
- **Focus sessions.** 25, 35 or 45 minutes split into look over it, recall it blind, check and mark, then break. The plant on screen grows for that session only and is gone afterwards, so there is nothing to protect and nothing to lose.
- **Past-paper log.** Marks plus one reason per paper (knowledge gap, exam technique, ran out of time, misread the question, careless slip). After a few entries it names the commonest cause, because that is usually the fastest thing to fix.
- **Deliberately absent:** leaderboards, XP, badges, a streak that punishes a missed day, and any gate that demands 100 percent before letting you move on. Those are the features students complain about most.

## Privacy

No backend, no analytics, no accounts. Revision progress is stored in the browser's localStorage and only leaves the device when the student exports the JSON file. The AI key is stored in localStorage on the deployer's device and is sent only to the chosen provider.
