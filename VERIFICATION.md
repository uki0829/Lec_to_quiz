# Verification record

## Permanent deletion and academic subjects, October 14, 2026

- Drag deletion now permanently removes quiz bodies/progress, source dependency links, collection links, stars, hints, generation requests, and their completed generation jobs in one transaction. Undo UI/state and the restore endpoint are removed. Lecture uploads/extracted content/vectors remain available. Existing follow-up sets remain, with deleted-parent references and saved parent-question context detached. Explicitly shared group snapshots remain independent copies.
- Deletion tests verify actual SQLite row removal, inability to restore or access after reopening the store, atomic owner/folder validation, active-follow-up blocking, associated-data cleanup, and preserved independent follow-ups/shared snapshots. No existing user set was deleted during verification; permanent-delete checks used test databases.
- Extraction, retrieval selection, and generation now receive subject-neutral instructions for computer science, psychology, physics, and other academic subjects. Conceptual topics do not require equations. Broad requests distribute questions across major concepts; a short set does not guarantee exhaustive coverage. Physics calculation prompts explicitly request units for givens and answers.
- Real end-to-end authored PDF checks completed extraction, embeddings, retrieval/reranking, source selection, and generation: computer science MCQ/flashcards (8 items), psychology MCQ/flashcards (8), and physics MCQ/flashcards/calculations (12). All 28 items passed validation, source-page/preview resolution, and local math rendering. Qualitative items were reviewed for relevance. These checks establish representative subject support, not universal factual correctness.
- A targeted live physics check after strengthening unit instructions produced four new problems specifying kg, m/s, m/s^2, N, and requested newton/joule answers. Hand-checked answers were 18, 50, 98, and 72, with valid LaTeX. Ignored artifact: data/physics-units-live-check.json.
- Reproducible optional live check: scripts/live_subject_check.py with fixtures/subject-lectures.json. Final regression run: 115 Python tests and all JavaScript behavior/syntax checks passed.

## Plain Explanation text and trash alignment, October 14, 2026

- Explanation uses purple text rgb(191,194,255), transparent background, zero border, and no shadow across all quiz types. Hover stays transparent; keyboard focus uses an underline. Existing control sizing and disclosure behavior are retained.
- The fixed trash target accounts for the desktop sidebar width, the narrower desktop breakpoint, and collapsed/mobile layouts. Browser checks in an isolated fixture confirmed matching content/trash centers at x=876 with a 240px sidebar and x=756 when collapsed, in a 1512px viewport. No sets were deleted for this check.
- Frontend behavior and drag/Undo checks passed. Screenshots in portfolio output: lecture-lab-purple-text-explanation.png and lecture-lab-trash-content-centered.png.

## Consistent practice controls, October 14, 2026

- Explanation controls across multiple choice, flashcards, and calculations share one class and style. Browser computed styles matched exactly: inherited Avenir Next font, 14 px, weight 700, foreground rgb(246,248,255), navy rgb(39,49,66), and 140 by 44 px, with matching borders and interaction states. Check and navigation use the same type and sizing tokens with their existing primary/secondary roles.
- Removed the calculation tolerance paragraph and result annotation, and removed the Not quite label from multiple choice. Tolerance grading, stored answers, invalid-number errors, and explanation toggling remain enabled.
- Targeted frontend behavior, practice-route, and JavaScript syntax checks passed. Browser checks used an isolated fixture database; user progress was not modified. Screenshot: portfolio output/lecture-lab-consistent-buttons.png.

## Card controls and calculation disclosure, October 14, 2026

- Removed flashcard self-rating buttons and handlers. Reveals record review progress; library counts include reviewed cards without marking them correct or incorrect. Existing progress is preserved.
- Saved library cards support native mouse drag to a bottom trash target, touch hold-and-drag, and Delete/Escape keyboard controls. Removal uses the existing owner/folder-scoped recoverable API, preserves lecture materials, updates parent/current-set context, and offers persisted Undo. External drops, cancelled drags, failed removal, and folder changes do not delete a set.
- Calculation Check remains beside a closed-by-default Explanation disclosure after submission. The worked solution overlays within the question card; clicking its noninteractive content collapses it, while citation controls remain usable. Reopening/revisiting starts collapsed and retains the graded answer.
- Browser checks used a separate fixture database at port 8766. Confirmed flashcard rating buttons absent, reviewed count persisted, wrong calculation hidden until requested, panel click collapse, and unchanged centered navigation. A real mouse drag removed a fixture quiz (3 sets to 2); Undo restored 3 sets. Keyboard pickup revealed the trash target; Escape cancelled it. User study data was not deleted during testing.
- Automated checks: 109 Python tests and all JavaScript behavior checks passed, including native drag handlers, touch hold/drop versus scrolling, cancellation, foreign-drop rejection, deletion failure, folder isolation, and Undo. Native touch input was covered through event fixtures, not a physical touchscreen.
- Screenshots in the portfolio output folder: lecture-lab-calculation-explanation-toggle.png and lecture-lab-drag-trash.png.

## Constructed calculation practice, October 14, 2026

- Replaced the requirement that example equations and numerical values appear in the lecture. Selection now retrieves supporting concepts even without worked examples; generation may construct new relevant functions, equations, matrices, assumptions, and numerical givens. Source quotations remain verbatim and are labelled Concept source for newly generated calculations.
- The structured calculation contract requires a separate problemEquation field. The app inserts it as display LaTeX if absent from the prompt, without duplicating a whitespace-equivalent equation. Inline equations are promoted to display math; standalone computational expressions and matrices are accepted. Numerical givens can be stated elsewhere in the visible prompt.
- Calculation generation uses medium reasoning. Arithmetic checks remain enforced. Repair feedback includes the previous attempt and identifies inconsistent answer fields, allowing the model to preserve valid questions while repairing errors.
- Replayed the failed six-question PDF request against its retrieved lecture passages using the real model. The final implementation produced six validated questions in one attempt. Independently checked answers were 0.6, 16000, 15, 4, 60, and 6144; all prompts and worked solutions typeset in local KaTeX without errors. An earlier low-reasoning replay was rejected for an inconsistent displayed answer; no invalid quiz was saved.
- A separate real generation check used concept-only gradient-descent notes with no equations or numerical data. Four new quadratic exercises passed validation and typesetting, with hand-checked answers 0.3, 1, 1.7, and -0.35. Ignored artifacts: data/calculation-pdf-concept-check.json and data/calculation-concept-only-concept-check.json. These targeted checks do not establish correctness on arbitrary generated problems.
- Final regression run: 108 Python tests, all JavaScript behavior checks, syntax checks, and diff whitespace checks passed. Restarted the idle local server with the updated generation policy; the homepage returned HTTP 200. Existing user quizzes and practice progress were not rewritten.

## Calculation problem statements, October 14, 2026

- Added generation-only checks requiring standalone LaTeX with an actual function/equation/rule and numerical givens. Regression cases cover the missing-loss screenshot, isolated symbols, inline-only math, and givens without a rule.
- Worker tests verify automatic repair and rejection after failed repair while preserving earlier saved quizzes.
- A real OpenAI request on an authored four-example fixture produced gradient-update, minibatch-step, Hessian-condition-number, and quadratic-loss questions on the first attempt. Independently checked answers were 2.4, 32, 10, and 9. Every prompt contained displayed equations and givens; local KaTeX rendered all prompts and worked solutions without formatting errors. Artifact: ignored `data/calculation-equation-check.json`. This check does not establish accuracy across arbitrary lectures.
- Full automated run: 99 Python tests passed, with all JavaScript behavior checks passing. Original saved question wording and progress are preserved.

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


## Cohere Rerank and simple practice navigation — 2026-10-14

Added reranking.py using Cohere's authenticated v2 Rerank REST endpoint, configurable model (default rerank-v4.0-fast), and the existing httpx dependency. The ignored server-side .env holds the separate key; config responses, quiz exports, and ranking audit records do not contain credentials. Up to 24 SQLite-eligible vector matches are sent for ranking, and up to 12 are passed to the existing constrained LLM source-selection stage. Provider indices map back to original local chunks. Eligibility is rechecked after ranking. Exact citation and arithmetic validation remain enabled.

Missing credentials, authentication/rate-limit/service failures, timeouts, malformed scores, duplicate or out-of-range indices fall back to original vector results. Ranking provider/model/status/scores and a sanitized fallback reason are saved with each request. Tests isolate local credentials so fixture requests never call the real account.

Live ranking tests on the uploaded BI lecture found Page 17 first for grain and Page 18 first for additive/semi-additive/non-additive measures. Vector search already ranked these pages first, so these two checks establish working integration and relevant first results, not an accuracy improvement benchmark. Lower-ranked passages changed. Reports are in ignored data/cohere-retrieval-check.json.

A browser request combining grain and measure definitions returned insufficient_source. Page 17's extracted text is only “Grain”; its summary mentions a definition, but summaries are not treated as evidence. Both pages were retrieved by Cohere. No fabricated grain definition was generated. A second browser request restricted to supported measure definitions succeeded: job 933b9c36d17147039f2b8450f762401a saved four flashcards in quiz 550cd07526a64dacb384f91309915e34. Request audit reports applied Cohere reranking of 24 candidates down to 12. All four flashcards cite original Page 18, with quotes checked against source text. Earlier saved sets remain available.

Generated practice hides the AI-generated badge. Question footers use Previous and Next with no export control. Results replace Practice unfinished or missed, Return to questions, and Export quiz with Previous (last question) and Next (study folder). Source viewing, grading, saved progress, generation retry, and labelled sample/imported modes remain. Cheat-sheet export/print remain separate.

All 63 Python tests passed, including ranking contract, malformed/duplicate/foreign indices, authentication and service failure, timeout/cancellation, collection isolation, fallback audit, and preserved prior quizzes. Existing frontend creator/grading/sheet checks passed; new navigation checks validate the two-button results flow, saved quiz identity, removed export, hidden generated annotation, and labelled samples. Browser verification exercised flashcard question navigation and both results buttons. At 390×844, page and content widths were both 390. The temporary viewport was reset. Preview: output/lecture-lab-simple-results.png in the portfolio workspace.


## Reversible flashcards, hints, and question bank — 2026-10-14

Created a large light card within the existing dark interface, with a centered question/answer, independent Get a hint and star controls, Back/Continue navigation, and a counter. Click, Enter, and Space reverse the card. Flipping back hides explanation/source text as well as the answer, while preserving submitted recall results. Reduced-motion preferences suppress the small face transition. Lucide lightbulb and star controls were downloaded from the official repository; star-filled.svg derives from its star path.

Additive SQLite tables starred_questions and question_hints were added after a code/database backup. Stars use original quiz/question identity and remain collection-scoped. Question bank supports search, individual cards, and Practice starred, with qualified IDs in combined queues. Bank practice can restore from browser state up to 500 cards. Original generated quiz progress remains in SQLite; bank session progress uses local browser state. Source-dependent deletion cleans both new tables, and deleting a backing quiz clears active bank practice. Sample/imported cards remain distinct and reversible; source-backed hint/star controls require a saved generated card.

The server creates brief hints with the configured OpenAI model from the original source passage, caches them, and retries once for overlong or direct-answer output. Missing/deleted cards, unsupported question types, and provider failure produce actionable errors without overwriting quizzes. Literal-answer checks and prompt instructions do not guarantee semantic quality. A live hint was reviewed and the cue prompt tightened to avoid blending related definitions. The final live hint for non-additive facts, “Think of the example ‘unit price’”, matches the original Page 18 example and leaves the full answer hidden.

All 70 Python tests passed: existing processing/retrieval/generation regressions plus new star idempotence, cross-course isolation, same question ID across multiple saved sets, hint caching, failure/answer-leak handling, unchanged answers/progress, deletion cleanup, and persistence after reopening the store. Frontend checks cover reversible flips, preserved grading, hidden answers on the front, bank origin identities, star/unstar, cached hint toggles, and restoration of a 64-card bank while retaining import limits. Existing creator/folder/grading/cheat-sheet checks passed.

Browser verification used the saved Fact Table Measures set: mouse and keyboard flips, live hint request, star saving, refresh restoration, bank listing, and Practice starred launching a source-backed card. The live star/hint checks used original quiz 550cd07526a64dacb384f91309915e34, question q3. Bookmarks can be toggled independently while the cached hint remains reusable. Existing recall grading was preserved. SQLite reopening tests verified bookmark persistence; the live browser verified refresh restoration. User activity can independently change bookmarks. At 390×844, page/content widths were 390, card width 358, and flip width 356; Back and Continue were visible with no horizontal overflow. The viewport override was reset. No new lecture extraction or embeddings were required.

Final flashcard preview: output/lecture-lab-flippable-card.png in the portfolio workspace.


## Completion summary and Home navigation — 2026-10-14

The final Continue/Next opens a light completion panel with completed/remaining counts, optional recall or correctness counts, an expandable per-question summary, Restart flashcards/quiz, Back to last question, and Home. Flashcards count as reviewed when their answer is revealed; flipping back preserves that review marker. Unsubmitted multiple-choice/calculation questions and unrevealed cards remain incomplete. Skipping to the end shows Session summary rather than claiming completion.

Restart keeps the quiz identity, source records, stars, and cached hints while resetting session answers, index, and summary state. Home returns to Sets, and the top-left study control is renamed Home. Cached home-card progress updates on restart. Incidental browser snapshots preserve the current summary state rather than clearing it.

Both frontend check scripts and JS syntax checks passed. New assertions cover incomplete/complete summaries, review versus recall, question status, all three actions, preserved stars/hints/identity, reset progress payloads, current home counts, and summary state on Home navigation. The focused backend saved-progress/deletion test passed, including review-marker round-trip and empty restart progress with unchanged questions.

Browser verification used the genuine Fact Table Measures saved set for summary, per-question detail, final-card return, Home, and refresh restoration. An explicitly labelled six-card authored sample tested reveal-only completion and restart followed by refresh at card 1/6, without resetting the user's generated set. At 390×844 the page width remained 390; controls fitted the stacked mobile layout. The temporary viewport was reset. Final screenshot: output/lecture-lab-completion-summary.png in the portfolio workspace. No new AI generation calls or processing changes were needed.


## Question-first flashcard navigation — 2026-10-14

Question and answer faces now share text color #293348. Reopening a set, moving Back/Continue, using question navigation, or returning from the completion summary resets the destination flashcard to its question face. Answers and explanation controls stay hidden until the student flips the card. Existing reviewed, submitted, correct, hint, and star data is preserved; legacy revealed cards receive a reviewed marker before their face is hidden.

Both frontend check scripts and JS syntax checks passed. Navigation assertions cover saved revealed state, backward/forward return, completion return, re-reveal, retained grading, and unaffected MCQ feedback. In Chrome, question and answer computed colors both resolved to rgb(41, 51, 72). Genuine saved-set checks verified returning to a revealed card and refreshing show the question with no explanation control; no recall results were reset. Screenshots: output/lecture-lab-answer-color.png and output/lecture-lab-question-first.png in the portfolio workspace.


## Quiz reference layout and answer sounds — 2026-10-14

Multiple-choice practice uses a light question card, numbered two-column options, clickable per-question progress segments, and a Don’t know action. At mobile widths options stack. Selecting an option grades immediately, locks the response, marks correct/incorrect choices with color and check/cross labels, and retains explanations and original sources. Skip reveals the answer without a grading sound; question summaries identify it as Skipped. Previously saved answer selections and progress remain supported.

Correct answers schedule a short ascending three-note sine chime; incorrect answers schedule a softer descending two-note cue. Web Audio starts only in response to answer selection, reuses its context, releases nodes, and fails safely without affecting grading. A speaker control toggles sound with a browser-local persisted preference. Restore/render/navigation never schedules feedback audio. No third-party recordings or API calls are used. Speaker icons were downloaded from the official Lucide repository with existing license coverage.

Both frontend check scripts passed, plus JS syntax validation. New checks verify immutable instant grading, correct/incorrect option labels, progress counts, three versus two tone schedules, no replay on render/resubmission, mute persistence, skip silence, and suspended-context failure handling. Browser tests used the labelled authored sample for correct and incorrect selections, Enter selection, mute/refresh, and retained responses. No user's generated answers were overwritten. Browser console showed no errors. The generated data-warehousing quiz was inspected and restored for the final preview. At 390×844 the page width remained 390, options used a single 312px column, and source links/navigation remained readable. Temporary viewport and mute were restored. Browser playback was invoked by these answer interactions; automated sound checks verify synthesis scheduling rather than measuring speaker output. Screenshot: output/lecture-lab-quiz-layout.png in the portfolio workspace.


## Accounts, Google sign-in, and study groups — 2026-10-14

An SQLite/code backup was created before additive identity/group migrations. Accounts store names, normalized email, salted scrypt password hashes, verified Google subject IDs, and hashed server-side session tokens. Cookie sessions are HttpOnly and SameSite=Lax for the local application. Private collection ownership filters lists and protects direct material, job, quiz, source, and file requests. Legacy work was retained under the labelled demo profile; new accounts start with empty libraries. Browser state is namespaced by account. Sign out flushes pending practice progress before revoking the session.

Groups support creation, invite-code joining, member lists, sharing saved quizzes/flashcards/cheat sheets, and member-only practice. Shares are immutable learning-content copies: questions/sections, answers, explanations, and citation excerpts. Original file IDs, uploads, requests, author progress, stars, and hints are excluded. Original files stay private; shared sources show excerpts. Practice progress is stored independently per member. The seeded Machine Learning group uses authored fixtures and labelled demo members/content rather than private uploaded lectures. The local email/group browser check created a separate Demo Student account and Demo exam prep group for verification.

Google's authorization-code flow uses state, nonce, PKCE, registered redirect URIs, and google-auth ID-token verification. The supplied OAuth web-client JSON was parsed without displaying secrets. Its values were installed in the ignored server-side .env while preserving existing API settings; file mode is 0600. The file includes the 127.0.0.1:8765 callback. After confirming no active jobs, the server restarted. A real flow used the already signed-in Google account, displayed the requested basic profile/email permissions, returned to Lecture Lab, created a Google profile in SQLite, and retained the session after refresh. That Google profile joined the labelled demo group with its invite code and could view all three example formats. Google passwords and OAuth client secrets do not enter the browser's storage or quiz exports.

All 77 Python tests passed: the original 70 regressions plus account hashing/session/revocation/throttling, private access and owner filtering, group membership restrictions, all three share formats, per-member progress, snapshot survival, state/nonce/PKCE, invalid and replayed callbacks, mocked verified Google identity, and persistence across a reopened app. Test factories explicitly disable authentication only for legacy single-user processing tests; new account/group tests exercise authentication enabled. Frontend grading/creator/social scripts passed; new social checks verify real control IDs, registration/login switching, user-scoped state, shared progress/source privacy, and share submission/confirmation. Browser checks caught and fixed a missing registration subtitle ID before the successful email registration/login test.

Browser verification covered email registration/sign-in/sign-out, creation/joining, sharing dropdowns, shared flashcard reveal/grading/refresh at card 2/6, real Google sign-in and session restoration, and membership through the demo invite. Real private lecture sets were not shared as test data; backend fixture tests and the frontend contract check exercised sharing. At 390×844, sign-in and group pages both remained 390px wide, account/sign-out controls stayed available, and set cards stacked. Temporary viewport was reset. Screenshots: output/lecture-lab-sign-in.png and output/lecture-lab-study-groups.png in the portfolio workspace. The final tab shows the Google profile in the demo group.

This remains a local demo, without cross-device deployment, email verification, password reset, moderation, or group-copy removal controls. Demo profiles/content are explicitly labelled. Sharing does not grant RAG access to other members' private lecture collections.


## LaTeX math display — 2026-10-14

Bundled KaTeX 0.19.0 locally with its fonts/license. Added escaped prose + LaTeX rendering across questions/options, flashcard question/answer/hint, explanations/steps, source excerpts and extracted content, review, question bank, shared sets, and cheat sheets. New/old status labels render as upright superscripts with the original variable case. Genuine numeric/component subscripts remain below the variable. Saved text, exports, source records, answer keys, and numerical grading fields are not rewritten. Unknown notation is not reconstructed; malformed/unsupported TeX keeps escaped original text with an error tooltip. Renderer trust is disabled, macro state is isolated, and expansion/size is bounded.

The generation instructions previously forbade LaTeX delimiters. Quiz and sheet prompts now request inline/standalone LaTeX, preserve evidence IDs/quotes, and explicitly retain bare scalar calculation answers and plain restricted arithmetic. Future and existing content use the same display layer. Small compatibility rules handle saved ASCII/Unicode variable labels, Greek gradient/loss subscripts, numeric exponents and scientific notation; currency and prose remain ordinary text. Native dropdown values remain plain text rather than embedding math markup.

Math checks passed for W superscript new, genuine component subscripts, Greek gradient/loss notation, fractions, matrices, sums, scientific notation, explicit inline/display math, currency/prose, malicious HTML/TeX, malformed formulas, and unchanged underlying answers/sources. Existing frontend, creator, and social check scripts passed. All ten targeted AI tests and the saved-progress/deletion check passed; generation tests assert LaTeX instructions and the bare-scalar/source-preservation contract.

A real OpenAI generation using an authored gradient-descent source fixture returned four validated MCQs with 14 LaTeX-bearing fields. Supporting quotes passed validation, all generated display fields typeset without errors, and the hand-checked update remains 3 - 0.1*6 = 2.4. This was a model-formatting/source validation check, not a new PDF upload journey or a retrieval benchmark. The test artifact is data/math-generation-check.json and is not inserted into the user's library. New-value typography is normalized in the presentation layer even when the model emits a new-label subscript.

Browser checks inspected the user's saved regression/computation quiz without grading it: vector subscripts, transpose/exponent notation, and gradient/loss notation rendered with no formatting errors. The labelled authored sample verified superscript new in quiz options and the flashcard answer. Its answer retained rgb(41,51,72), matching the question color. Fonts reported loaded. At 390×844 the page remained 390px wide, with one superscript and no formatting errors; long math can scroll within its container. Temporary viewport was reset. Previews: output/lecture-lab-math-quiz.png and output/lecture-lab-math-flashcard.png in the portfolio workspace. The app was restarted only after checking there were no active jobs.

## Dedicated study pages and stable answer flow — 2026-10-14

Opening a saved set now uses `/study/quiz/{id}` or `/study/shared/{id}`. Samples, imports, and bank sessions use `/study/local`. The server returns the interface shell; authenticated existing APIs supply set content. The dedicated page hides library chrome, centers a bounded light practice card, and reserves navigation space. Long content scrolls within the card. Flashcard reveal keeps a reserved recall row; explanation and citations open in a native modal rather than expanding the card.

Correct MCQ submissions retain sound and grading, then advance after 550 ms. Wrong and skipped responses open the explanation modal and wait for Continue. Manual navigation, Home, set replacement, and sign-out cancel the timer; stale callbacks verify their quiz, index, epoch, and active view. Returning to submitted questions neither regrades nor auto-advances. Final advancement uses the existing completion summary.

Five frontend scripts and JS syntax checks passed, including new deep-link/history recovery checks and guarded timer, modal, final-question, keyboard-dismissal tests. A targeted backend route test passed for local/private/shared study paths and missing-set API behavior; the full backend suite was not rerun for this UI and shell-route change.

Browser checks used authored sample responses and inspected an existing genuine saved quiz without changing its answers. Its private study URL survived refresh; Home returned to the library. Browser Back/Forward preserved sample answers. Correct submission advanced to question 2, wrong submission opened explanation, and Escape returned focus to Explanation. Source inspection opened the existing viewer from the modal.

At 390×844, the quiz card stayed at top 170, height 592, and the navigation stayed at top 780, height 48 before and after wrong-answer feedback. Page width remained 390. Desktop flashcard reveal preserved the card height (589) and navigation position. Mobile flashcard navigation remained visible. Temporary viewport overrides were reset. Screenshots in the portfolio output folder: lecture-lab-study-quiz.png and lecture-lab-study-flashcard.png.

## Study palette and centered navigation — 2026-10-14

Study pages now use the library's navy background (#141820), dark card surface (#222a39), light blue primary buttons, and pale text. Answer states, flashcards, explanation dialogs, and completion summaries use matching dark surfaces. Previous/Next are grouped at bottom center, retaining the flashcard counter between them. Mobile request metadata no longer overlaps the title.

Existing frontend interaction and study-route checks passed. Browser measurements confirmed the navigation midpoint at x=756 in a 1512px desktop viewport and x=195 in a 390px mobile viewport. Flashcard question and answer both computed to rgb(246,248,255), with unchanged card/footer bounds after revealing the answer. Authored-sample explanation and completion screens were visually checked. The user's saved quiz was inspected without submitting answers, then restored. Temporary viewport override was reset. Screenshot: output/lecture-lab-study-dark.png in the portfolio workspace.

## Calculation LaTeX delimiter repair — 2026-10-14

The saved calculation quiz contained double-escaped math delimiters after JSON decoding. The renderer now consumes complete delimiter runs while preserving LaTeX commands, matrix row separators, and explicit row spacing. This is a presentation repair: stored question text, source quotes, scalar answers, numerical tolerance, and arithmetic grading are unchanged.

All 24 question/answer/explanation/step fields from the user's four-question calculation set rendered without math errors. Browser inspection confirmed the first problem renders B=128 and n=4096 as actual KaTeX math with no raw delimiters or math-error elements. No answers were submitted to that saved quiz.

Generation instructions now request standalone mathematical givens/functions and correct backslash handling after JSON decoding. A direct live OpenAI check using an authored gradient-descent/minibatch fixture produced four validated calculation questions, all with standalone equations. All 17 prompt/explanation/step fields typeset without errors. This check did not run a new PDF extraction or RAG journey, and the fixture quiz was not inserted into the user's library. Artifacts: data/calculation-render-check.json and data/calculation-latex-generation-check.json.

Math regression checks passed for double-escaped inline/display delimiters, original numbers, fractions, matrices and optional row spacing, malformed formulas, literal-mode preservation, and unsafe link rejection. Existing frontend interaction checks, JS syntax checks, and all 10 AI contract tests passed.

## Remove sample entry points and connection panel — 2026-10-14

Removed the sidebar sample button, library sample shelf, empty-study sample button, and bottom AI connection section from the HTML. Removed their event bindings. Connection checks still run automatically during startup and before processing/generation, without referencing the deleted controls. File-size errors no longer direct users to that removed panel.

Existing frontend interaction, creator/recovery, and JS syntax checks passed. Browser startup displayed the saved library and study folders with no sample entry points or AI connection section. Screenshot: output/lecture-lab-clean-library.png in the portfolio workspace.

## Saved-set names and sliding sidebar — 2026-10-14

Added saved-set renaming with owner-authorized PATCH, trimmed title validation, and unchanged questions, request records, source dependencies, and progress. The initially requested bulk-removal implementation uses an additive quiz_removals table and a pre_set_actions SQLite backup, preserving source data and allowing restoration. All 84 backend tests passed, including six new cases covering title changes, removal/restore persistence, ownership/folder boundaries, atomic selections, active-parent-job blocking, and source-deletion cleanup.

Following the user's subsequent instruction, removed the quiz Remove button and selection controls from the interface, retaining Rename and recovery for any previously removed sets. Updated frontend checks pass for naming, blank/failed rename recovery, unchanged active practice/follow-up context, absent Remove controls, and prior-removal Undo isolation. Existing frontend, creator, social, and JS syntax checks passed.

Added an accessible top-left sidebar toggle using the existing Lucide chevron asset. The navigation slides away, becomes inert/aria-hidden, and the content column expands; reduced-motion settings disable transitions. A browser-local appearance preference survives refresh. Browser checks confirmed desktop content expands from 1272px to 1512px when the 240px sidebar closes. At 390×844, both sidebar states fit the viewport with page width 390, and no quiz Remove controls were present. The Rename dialog was inspected and cancelled; no real quizzes were renamed or removed. Temporary viewport override was reset. Screenshot: output/lecture-lab-sidebar-toggle.png in the portfolio workspace.
