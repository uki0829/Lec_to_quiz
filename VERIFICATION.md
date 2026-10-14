# Verification record

Verified October 13, 2026, during local implementation.

## Automated

- 21 Python tests pass. AI calls are replaced by a fixture provider.
- Tests cover PDF/image uploads, all three generated-question formats, persisted progress, source-file resolution, source/quote validation, arithmetic checks, missing-topic results, missing keys, provider failures, cancellation/retry, interrupted jobs, invalid files, and the localhost origin boundary.
- Real FFmpeg processes generated 30-minute audio and video fixtures. Each recording is split into six transcription-size-safe chunks. Video produces 30 sampled frames, and transcript timestamps are restored to the original time scale. These fixtures do not establish recognition quality on real lectures.
- JavaScript checks pass for all sample quiz schemas, fixed six-question sample count, scientific notation, numeric tolerance boundaries, invalid numeric inputs, and invalid quiz imports.
- Both frontend scripts pass Node syntax checks. The sample PDF has three pages with verified text fit; the first page was rendered and visually inspected.

## Browser

- Desktop interface inspected; upload-panel layout corrected.
- Multiple-choice correct and incorrect feedback verified.
- Flashcard reveal and recall controls verified.
- Calculation answer `2.4e0` graded correctly; worked solution and source reference displayed.
- Sample source viewer opened successfully.
- Actual pasted notes processed through the local server and appeared as a saved ready material set.
- Refresh restored sample quiz progress and the review screen.
- Missing-key generation displayed a useful setup message without replacing the existing quiz.
- Review distinguished missed and unanswered questions.
- Export produced a six-question JSON file; its mode is sample and it contains no credential fields.
- Mobile layout tested at 390 × 844; document width equals viewport width, with no horizontal overflow. Temporary viewport override restored.
- Browser automation of JSON import was blocked by the Chrome extension's file-URL permission. Import schema checks pass, but the browser file-selection path remains unverified. No browser permissions were changed.

## Verified with real OpenAI API calls

After the user supplied a key, it was configured in ignored local `.env` with owner-only filesystem permissions. The key was not printed or sent to the browser.

- The sample PDF was interpreted by the actual model and produced all three question formats through the live smoke check.
- Saved demo preparation through the running local API produced six multiple-choice questions, six flashcards, and six calculation questions from the three-page PDF.
- The authored first-page PNG produced a four-question multiple-choice quiz.
- A 45.5-second authored lecture, spoken with the system voice, was transcribed through Whisper and produced a four-question multiple-choice quiz.
- A video combining that speech and an authored still slide was transcribed and visually interpreted, then produced a four-question multiple-choice quiz.
- All generated quizzes passed answer/format/source validation. The six saved PDF calculation expressions and answers were inspected and agree with the lecture examples.
- A request for numerical examples from a slide without numerical examples returned a useful insufficient-source message rather than invented examples.
- The real generated PDF quiz was opened in the browser. Its original PDF page and extracted source were displayed successfully; the viewer now uses a rendered original page to avoid browser PDF-extension dependency.

Six genuine AI-generated quizzes are saved in the local library. The recordings are deliberately labeled authored/synthesized demo sources, not real university lecture recordings.

The 30-minute processing limit was verified using generated media with a fixture AI provider, not 30 minutes of live provider transcription. Full-length real-lecture quality and API performance remain unmeasured. Brief video content can be missed by once-per-minute frame sampling.

To repeat a live check after configuring a replacement key:

```sh
.venv/bin/python scripts/live_check.py
```

To prepare/reuse saved demo results through the running server:

```sh
.venv/bin/python scripts/prepare_demo.py --all-media
```

These commands send the authored sources to OpenAI and use normal API billing. A successful smoke check does not establish broad mathematical or pedagogical accuracy.


## Collections and RAG extension — 2026-10-13

Implemented in `/Users/zhanghefeng/Desktop/Lec_to_quiz`. The prior database and changed code were backed up at `data/backups/20261013-224154-pre-rag/`; the additive migration also saved `data/lecture_lab.pre_collections.sqlite3`. Credentials were preserved in the ignored environment file.

### Automated checks

28 backend tests passed (including the original real FFmpeg 30-minute audio/video fixtures). Frontend numeric-grading/sample-schema checks and JavaScript syntax checks passed. New tests cover collection isolation, added-material reuse, multi-material citations, follow-up inheritance/overrides, frozen ready-material snapshots, indexing retries, Unicode chunk offsets/token limits, model-change reindexing, legacy migration, and SQLite exclusion of stale deleted vectors with cleanup retry. Test AI outputs are fixtures; these tests do not assess general LLM accuracy.

### Real OpenAI checks

A real PDF upload and an added authored text lecture were processed into a named collection. OpenAI embeddings and structured generation produced six multiple-choice questions citing both the PDF and added text lecture. Source links resolved; original PDF preview returned a genuine rendered PNG page.

A follow-up produced four calculation questions with the inherited intermediate difficulty. Arithmetic and the referenced examples were independently checked: first update from w=4 at eta=0.75 gives -2, its loss is 4, the next update from -2 is 1, and the loss at w=1 is 1. These checks cover the supplied examples, not unrestricted mathematical reasoning.

The browser's Build on this quiz action then generated four flashcards using the supplement lecture. Request editing, parent context, source evidence, answer reveal, and recall grading worked.

Demo collection: `a76a5d69c2934bc48c4d04a213a4c83f`
Multiple-choice quiz: `a970c7c688ab49cda5a914d563554afa`
Calculation follow-up: `041d9440cd0343e1b20d14a3c81ca71c`
Flashcard follow-up: `3207a6ccce5648f3b4c2815bc8df5fcc`

### Persistence and browser checks

All six original quizzes were preserved; nine genuine generated quizzes are now saved. A fresh process opened the persistent index (12 indexed chunks) and performed a real semantic query about parameter-change size and convergence. Its top sources were the learning-rate supplement and the original PDF's learning-rate page; no source embeddings were regenerated.

Saved correct and incorrect answers and flashcard recall survived restarting the process. The app restarted without scheduling unnecessary indexing jobs. Browser verification covered collection creation, source previews, quiz selection, original request display, follow-up generation, feedback, flashcard reveal/recall, and restoration after refresh. At 390 × 844, document width equaled viewport width (390), with no horizontal overflow. The temporary viewport override was reset.

### Practical limits

Retrieval ranks a bounded set of chunks. This check demonstrates retrieval and source-backed generation for authored lecture samples; it does not establish recall or factual accuracy across arbitrary large course libraries. Exact parent question prompts are rejected in follow-ups, but semantically repeated questions with different wording may still occur. Existing source extraction, transcription, and numerical-validation limits still apply. Browser import is covered by parser/schema checks; the previously noted browser extension file-picker limitation remains.


## Study dashboard redesign and validation repair — 2026-10-14

Installed in the Desktop project. Database and prior code backup: `data/backups/20261014-002041-before-study-redesign/`. The production database was retained, not replaced with preview data. All nine quizzes present before this change remain available; the live check added one new flashcard set.

The recorded failed job requested mcq while its prompt asked for flashcards. The raw model output was not retained, so the earlier combined validation message alone could not distinguish duplicate IDs from a wrong question type. The repair constrains generation to the selected type using a format-specific structured schema and assigns IDs in the app. The format and count controls take precedence over contradictory prompt wording. Opening a saved quiz no longer overwrites the creator's format/count. Existing source, excerpt, and calculation validation remain intact.

33 Python tests passed. New checks verify selected-format schemas, app-assigned IDs despite duplicate/missing model IDs, rejected wrong types, safe failed-request editing metadata, and library card counts. Frontend checks verify prompt-format detection and that opening an older MCQ quiz preserves flashcard creation settings. Sample schemas, numeric/scientific-notation grading, and JavaScript syntax checks passed.

A copied-library preview retried the original failed request with real OpenAI calls and produced four valid multiple-choice questions in the explicitly selected format. Preview results were not copied into the user's database.

The installed app's Flashcards tile was tested end to end: paste new learning-rate schedule notes, select an earlier MCQ quiz as context, request four flashcards, process/index the added material, and generate a source-backed set. Quiz `d1167edeec264bb6a141afa23e20ff45` contains exactly four flashcards with IDs q0–q3 and parent quiz `a970c7c688ab49cda5a914d563554afa`. Questions cite both the earlier PDF (Page 1) and the new notes source. The worked schedule example gives eta=0.2/(1+0.1*10)=0.1, consistent with the authored notes.

Browser checks passed for the module creator, explicit format-conflict Switch control, previous-set selection, search cards, refresh restoration, keyboard answer reveal, recall grading, and opening the original PDF page. All bundled images loaded. At 390×844, document width equals viewport width (390), and the creator's content width equals its client width (350). The temporary viewport override was reset. The additional mobile collection-creation control edit was declined and not applied; collection creation remains available through the desktop sidebar.

The dashboard uses 26 downloaded Lucide SVGs and four Microsoft Fluent Emoji illustrations. Licenses and origin URLs are bundled under source/. Live generation checks cover authored examples and do not establish factual correctness across arbitrary lecture material. The prior browser file-picker automation limitation remains; multipart file processing is covered by backend tests, and the new browser live journey used pasted notes.


## Upload-first creator — 2026-10-14

Create new and all three module tiles now begin with accepted file types, file limits, upload/drop, and optional pasted notes. Practice settings remain hidden until extraction and indexing complete. An explicit saved-lecture shortcut supports RAG without re-uploading. A new upload remains bound to its owning collection, and a first upload can create a collection automatically.

`node scripts/check_creator.mjs` passed upload-stage gating, explicit saved-source selection, failed and cancelled processing, indexed-source readiness, collection ownership, module retention, generation guard, first-upload collection creation, and refresh format restoration. Existing `node scripts/check_frontend.mjs` grading/schema checks and JS syntax checks passed. Python processing and generation code was unchanged in this update.

The installed app completed a genuine browser journey: Flashcards tile → pasted authored gradient-descent notes → upload and extraction/indexing → customize → generate four flashcards. Quiz `16fd76d819ae4014bfc167def48beb75` is stored in the existing demo collection. All ten previous quizzes remain; eleven genuine quizzes are now saved. Settings and the loaded lecture survived refresh; flashcards remained selected after correcting a disabled-button restoration bug. Enter revealed a generated answer with a source citation. New settings remained hidden while processing.

Both steps were inspected at 390×844: document width 390, dialog client/content width 350, no horizontal overflow. The saved-source shortcut opened the settings step. The viewport override was reset. File-picker automation remains unverified in this browser environment; this update's live browser upload used pasted notes. Existing multipart file processing is unchanged.


## Minimal interface copy — 2026-10-14

Removed dashboard taglines, card descriptions, footer annotations, duplicate upload headings, upload destination paragraphs, and repeated settings summaries. Retained function names, controls, collection/file names, source links, processing/error status, and file limits. Authored UI hints are under ten words; source material, user requests, question content, and explanations are not truncated. Source uncertainty is available through an expandable Source notes control. JavaScript syntax, existing grading/schema checks, and creator gating/recovery checks passed.

Browser verification covered the minimal dashboard, upload-first gating, saved-lecture shortcut, and settings controls. At 390×844 the document width was 390 and dialog client/content widths were both 350; the viewport override was reset. No new live API calls were needed for these copy-only changes.


## Cheat Sheets and Library — 2026-10-14

Added a fourth Cheat Sheet module using the upload-first flow and existing collection RAG. Sheets are stored in SQLite with their original request, retrieval snapshot, and actual section citation dependencies. The reference view displays key points, formulas, section navigation, source viewing, JSON export, and Print. Section count replaces question count, and difficulty is hidden for sheets. Sample sheets are visibly marked as authored samples.

Library now has one visible Library heading, a collection selector, Sets/Materials tabs, type filtering, and search for both sets and filenames. Copy remains limited to names, controls, essential status, and short hints. The new notepad illustration was downloaded from Microsoft's Fluent Emoji repository; its URL and license are in source/ASSET_CREDITS.md.

38 Python tests passed, including new tests for sheet schema/evidence validation, PDF source navigation, saving/reopening, absent topics, provider failure preservation, follow-up context, two-lecture collection isolation, and citation-dependent deletion. Existing grading/schema and creator recovery checks passed. New frontend checks cover sheet import rejection, sample/rendering, section counts, type filtering, filename search, and sheet-specific settings. pytest.ini limits collection to current tests rather than code backups.

A genuine authored three-page PDF was uploaded through the local multipart API into Cheat Sheet Demo, collection 730578f0ba73424fba9da9515f56ab81. Real extraction and embeddings finished; the browser requested and saved four sections using the live model. Saved sheet: 37cf3f532ba44470bfbb5922aef55486. Sections cite real PDF pages 1–3, and the original Page 1 viewer opened successfully. The supplied scalar example 3−0.1×6=2.4 and vector update [2,−1]−0.25[4,−2]=[1,−0.5] agree with the authored lecture. These checks concern the supplied examples, not unrestricted factual correctness.

The first live attempt exposed rewritten source quotations. A draft schema using full multiline quotation literals was rejected by the API. The final schema uses bounded app-assigned excerpt IDs instead. IDs are validated against the cited chunk; the application inserts exact source text. The successful live retry retained strict quotation/source validation and reused the processed PDF.

The browser Export action created Downloads/lecture-lab-cheatsheet.json. Its sections exactly matched the saved sheet and passed frontend import validation. The browser download-event waiter timed out, but the actual file was verified; a fresh preview tab recovered browser control. A fresh tab restored the saved sheet, and Library navigation, set-type filtering, and filename search worked. At 390×844, document width was 390 and sheet content width was 358, with no horizontal overflow. The viewport override was reset. Print is wired to the browser dialog with print styles; the print dialog/PDF output was not exercised. File-picker automation remains outside the verified browser journey; real PDF upload was through the existing API.


## Create new, Study folders, and styled menus — 2026-10-14

Replaced the Library page title and home/back navigation labels with Create new. Cheat Sheet tile text is white (verified computed RGB 255,255,255), with a darker gold background for readability. The sidebar now uses Study folders, a seven-word course-grouping hint, New folder, readable names, file/note counts, and file-type labels for filename-based folder names. Stored names and IDs are retained; filename cleanup is a display label only. The collections listing now includes fileCount and noteCount computed from actual uploaded records.

Five visible selects are enhanced by source/menus.js: main study folder, set type, creator study folder, previous set, and difficulty. Native select values and existing change handlers remain authoritative. Menus use app styling, selected checkmarks, bounded scrolling, viewport-aware placement, labelled combobox/listbox roles, typeahead, arrows, Home/End, Enter/Space, Escape, and Tab. They reflect dynamic options, visibility, and disabled attributes. Popups inside a modal are attached to that dialog.

Browser checks covered folder changes, type filtering via typeahead, previous-set context, difficulty selection, Escape without closing the creator, and Tab moving to the next control. An issue where focus scrolling closed a menu was corrected by repositioning it rather than closing it during in-view scroll. Folder editor labels were inspected without creating test folders. At 390×844, page width was 390; the folder menu spanned x=16–374 and y=450.9–750.9, inside the viewport. New folder and the folder strip were visible on mobile. Materials hides the type-filter wrapper. The viewport override was reset. Existing frontend creator, grading, and sheet checks and JS syntax checks passed. This update did not request new AI generation.

The final backend regression run passed all 38 tests. Final previews are saved as lecture-lab-create-new.png and lecture-lab-create-new-styled-menus.png in the workspace output folder.


## Compact home and folder deletion — 2026-10-14

Removed the noninteractive Create new hero above the tool tiles and the header AI ready/Local labels. Kept the actual Create new buttons and expandable AI connection settings. The Cheat Sheet tile is violet (#6252bd) with white text, matching the cool blue/purple card palette.

Every study folder has a separate labelled trash button. A custom dialog lists the affected material sets and saved quizzes/cheat sheets. Cancel receives initial focus; Escape cancels. Deletion removes folder membership, uploads, extracted sources, chunk metadata, saved sets, requests, and jobs transactionally in SQLite, then removes upload directories and cleans vectors. Vector tombstones survive failed cleanup; SQLite excludes stale vectors immediately. Active material, indexing, or generation jobs prevent deletion. A revision check rejects confirmations made before new content or a rename. Upload commits recheck folder existence so an upload streaming during deletion cannot recreate the deleted folder. Existing work in other folders is retained.

Eight fixture-based deletion tests cover a populated folder with PDF files, notes, a quiz and cheat sheet; unrelated source-backed practice; restart persistence; active extraction/indexing/generation; cancellation boundaries; stale previews and renames; empty/missing folders; vector cleanup recovery; and concurrent upload commit. Frontend checks cover dependent-state cleanup, preserved unrelated practice, stale-preview errors, and cancellation, alongside existing creator/grading/sheet checks.

Browser verification opened the real Cheat Sheet Demo deletion preview and cancelled it. Its PDF and saved cheat sheet remained available. Mobile (390×844) page/content widths were both 390; the dialog client/content widths were both 368. Escape restored focus to the trash button. Computed tile background was RGB 98,82,189 and text RGB 255,255,255. The viewport override was reset. No user folders were deleted during browser verification, and no new AI requests were needed.

Final regression: all 46 Python tests passed, along with frontend creator, folder-state, grading, cheat-sheet, and JavaScript syntax checks. The running local server was restarted with the final backend changes. Preview: output/lecture-lab-folders-delete.png in the portfolio workspace.


## PDF generation source-reference fix — 2026-10-14

The user's 29-page INFO 4555/5556 data-warehousing PDF extracted and indexed successfully. Its first generation failed during source selection (invalid IDs); its retry failed during flashcard validation (a source reference outside the selected chunks). Selection and non-cheat-sheet question schemas had unconstrained reference strings. The frontend collapsed the latter into a generic validation message.

Source selection now restricts IDs to the retrieved snapshot. Quiz generation chooses short application-assigned evidence IDs. Each ID binds one exact source excerpt to its chunk, so the model does not independently reconstruct opaque chunk IDs or rewrite quotes. Validation binds the source/page and still rejects unsupported evidence, wrong counts/formats, inconsistent answers, and invalid arithmetic. Existing verbatim-quote fixture contracts and the cheat-sheet excerpt mechanism remain supported. Frontend failures now identify source-check problems or show the specific validation reason. This does not establish automatic factual correctness: explanations and supporting originals remain inspectable.

The implementation uses supported Structured Outputs enums, verified against official documentation: https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas. Evidence text stays in the input; only short IDs appear in the new quiz enum.

Live retry of the exact original flashcard request succeeded, reusing the existing extraction and embeddings. Job 60a5f9b03c9d4c858d563eb44ae694b5 saved quiz ddab8fc0c53448f591f8601fdd560ec7: six flashcards citing pages 2, 3, 6, 15, 8, and 18. All six quotes were checked against stored source text; all six PDF page previews returned PNGs. Browser checks exercised reveal, source quotation, original page 2, recalled/not-recalled grading, unfinished review, retry, and progress restoration after refresh.

A second generation through the browser's Quiz tile and saved-lecture shortcut created six MCQs from the same real PDF, using the request for data warehousing, OLTP/OLAP, dimensional modeling, fact tables, and measures. Job fd347da2b30345008f1e43ab7b65bd61 saved quiz f438be090fda4c9c9f6998ac072243d9, citing pages 5, 6, 11, 20, 21, and 18. Incorrect OLTP feedback and correct OLAP feedback worked, with page 6's exact supporting text visible. Both generated sets remain saved in the existing lecture folder.

A separate temporary local application completed a fresh upload of samples/gradient-descent.pdf, real OpenAI page extraction, embeddings, and four calculation questions. Restricted arithmetic validation passed. Hand-checks: 5−0.2×3=4.4; 2×7=14; (1−2×0.25)×4=2; and a zero gradient leaves 9 unchanged. Temporary test data was removed; user uploads and saved sets were retained.

All 50 Python tests passed. New tests enforce retrieved-only source selection and evidence/source/page binding across MCQ, flashcard, and calculation generation; they reject fabricated, conflicting, or stale evidence IDs. Existing frontend creator, folder-state, grading, cheat-sheet checks and JS syntax checks passed. Browser screenshot: output/lecture-lab-pdf-generation-fixed.png in the portfolio workspace. No new recording or image tests were repeated because their extraction paths were unchanged.


## Rename prominence and reading contrast — 2026-10-14

Rename folder now uses a filled blue button, light border, full label, official Lucide Pencil icon, and a 44px minimum height. Opening the button's editor was verified without changing any folder name. Body text now uses weight 500 with brighter foreground/muted tokens; quiz options and inputs use 550. Source quotations, explanations, menu metadata, folder counts, and upload hints received targeted contrast/weight updates. Light cheat-sheet panels keep their dark foregrounds.

The desktop page was visually inspected. At 390×844, page and content widths both measured 390. Rename folder measured approximately 148×44px and remained beside Add materials. The viewport override was reset. These were HTML/CSS/asset changes; no backend or generation changes or new API requests were made. Preview: output/lecture-lab-readable-text.png in the portfolio workspace.
