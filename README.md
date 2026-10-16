# Lecture Lab

A local AI Lecture-to-Quiz application. Add lecture material, ask for a topic, and practice using multiple choice, flashcards, or scalar calculations, and generate source-linked cheat sheets. The dark study dashboard is served by Python FastAPI, with SQLite for collections, materials, requests, jobs, quizzes, and progress, plus a persistent local Chroma index for lecture retrieval. Accounts keep private study spaces separate, and study groups share selected practice sets. Open a group to access **Leave group** or **Add study set**. Adding an existing set follows **Collection → Study set → Add to group**; only saved sets from the selected collection are listed. Already-added sets are greyed out and cannot be added twice to the same group. The current group owner can drag a shared set into the bottom trash target to remove that group copy and its shared progress; the original private set remains available. If the owner leaves, ownership passes to the earliest remaining member by join order. Shared sets and practice progress stay available to remaining members, and the invite code can be used to rejoin. Only a group with no members is removed; original private sets and lecture files remain available.

New calculation questions include a displayed LaTeX function, equation, matrix, or update rule plus numerical givens. The model may construct new equations, functions, matrices, coefficients, and example values applying concepts taught in the uploaded material; the exact exercise need not appear in the lecture. The explanation identifies constructed practice, and its citation is labelled **Concept source**. Original quoted lecture excerpts remain unchanged. Missing worked examples alone do not trigger clarification. Generation validation rejects word-only questions, isolated symbols, and givens without a rule, then requests one repair. Existing inline LaTeX equations are promoted to display math without changing their content; numerical givens can also appear in the surrounding prompt. These checks verify problem structure and answer arithmetic; they do not prove mathematical correctness or completeness. Existing saved questions keep their original wording and progress; retry a failed generation or create another set to apply this policy.

Flashcards use flip, hint, star, Explanation, and Back/Continue; revealing a card records it as reviewed without self-rating buttons. In the library, drag a saved set onto the bottom **Delete permanently** target to delete it with no Undo. Its questions, progress, stars, cached hints, and generation request are removed from the app database. Touch supports a short hold then drag, and keyboard users can press Delete on a focused set, then activate the trash target or press Escape to cancel before dropping. Uploaded lecture materials are retained. For calculations, type a number and press **Enter** to grade it. Incorrect answers remain editable for retries. Sound and visual effects distinguish correct and incorrect results. **Explanation** opens the white worked-solution panel over the card. Clicking the panel or Explanation again collapses it without moving Previous/Next.

## Cheat sheets and study guides

Cheat Sheet creates a comprehensive reference guide across the ready lectures in the selected study folder. It chooses subject-appropriate explanations, definitions, comparisons, methods, and equations, with original source links. There is no fixed section quota or five-point/three-formula limit. Large materials are processed in coverage batches; generation failures preserve existing sets and completed guide batches can be reused on retry.

Read the HTML guide in the app. **HTML** downloads a self-contained document with embedded fonts and typeset math; **PDF** downloads an A4 PDF using the same content and KaTeX typesetting. Both formats preserve prose and LaTeX equations without requiring an external LaTeX installation. Source filenames and page/timestamp labels remain in downloads; private source-file links stay in the app. Model content is escaped and rendered through a fixed layout rather than executing model-written HTML.

If PDF export is unavailable, run `.venv/bin/python -m playwright install chromium`. If HTML typesetting is unavailable, run `npm ci`. These exports run locally; they do not upload the guide to another PDF service.

## Academic subjects

Generation infers the subject from your uploaded lecture. Computer science, psychology, physics, and other academic topics use the same upload and RAG workflow, with subject-appropriate concepts and terminology. Qualitative lectures can produce conceptual quizzes and flashcards; physics and other quantitative topics can produce new numerical exercises with equations and stated units. A short quiz samples major topics rather than guaranteeing every detail is tested.

Real authored PDF checks passed for computer-science and psychology multiple choice/flashcards and physics multiple choice/flashcards/calculations. Reproduce these optional paid API checks with `.venv/bin/python scripts/live_subject_check.py`. Fixtures are authored test material, not real course documents. See VERIFICATION.md for scope and limitations.

## Start

The project virtual environment is already installed on this computer. From this folder:

```sh
bash scripts/start.sh
```

Open **http://127.0.0.1:8765**. The app binds to localhost, supports local user accounts, and is not deployed. On another computer, install Python 3.12 and Node.js, then run `bash scripts/setup.sh` first. Setup installs the Python dependencies, npm packages, and Chromium for PDF rendering. Bundled FFmpeg is provided by `imageio-ffmpeg`; use `FFMPEG_PATH` for a separate installation.

## Accounts and study groups

Use **Explore demo** to enter Hefeng's labelled demo profile and retain the existing folders and saved work. **Study groups** opens a seeded Machine Learning group with authored flashcards, a quiz, and a cheat sheet. Its members and content are labelled Demo; they are examples, not real classmates or a new live AI generation.

Email registration/sign-in is functional on this local installation. SQLite stores account names, normalized emails, salted scrypt password hashes, hashed session tokens, collection ownership, groups, memberships, shared-set copies, and individual practice progress. Passwords and session tokens are not stored in plaintext. Sign out flushes pending progress first. Browser study state is namespaced by user; old state is migrated only to the demo profile. New accounts start with empty private libraries.

Create a group, or join using its invite code. In a saved set choose **Share**, select a group, and confirm. You can also select **Share a set** inside the group library. Sharing copies questions/sections, answers, explanations, and citation excerpts. It excludes original uploads, source access IDs, requests, and the author's progress. Group members practice independently; shared practice progress is stored per user. Shared copies survive deletion of the private original. Original page/audio navigation remains available in your own library; shared sets show the citation excerpt without opening private files. Groups do not combine or index each member's private lecture files.

This is a local multi-user demo: users can switch accounts on this installation. Cross-device access, email verification, password reset, moderation, and production hosting are outside this version. Invite codes grant membership to signed-in users who possess the code; the example group's code is LECTURELAB.

### Enable Google sign-in

The Google button uses an authorization-code/OpenID Connect flow with state, nonce, PKCE, verified ID tokens, and server-side sessions. It is implemented, fixture-tested, and has completed a real Google sign-in on this computer. For another installation, configure your own OAuth client:

1. Create a Google OAuth **Web application** client and configure its consent screen/test users.
2. Register `http://127.0.0.1:8765/api/auth/google/callback` as an authorized redirect URI. If using localhost instead, register `http://localhost:8765/api/auth/google/callback` too.
3. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to the ignored `.env`; restart the server.
4. Open the matching local URL and choose **Continue with Google**.

Token verification allows 30 seconds of clock drift while still checking the signature, issuer, audience, nonce, and verified email. Keep the computer clock synchronized. Failed attempts distinguish session expiry, Google connection, configuration, and identity-verification errors; server diagnostics record only the stage and a safe reason, never tokens or credentials. Start a fresh sign-in after an expired attempt.

Google credentials never enter browser storage. Google accounts use the verified provider subject ID; no Google password is stored. If that email already has a local account, sign in by email first and use Google to link it; accounts are not silently merged. Setup follows [Google's web-server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server) and [backend ID-token verification](https://developers.google.com/identity/sign-in/web/backend-auth). A live sign-in, callback verification, session refresh, and joining the demo study group were verified on this computer after configuring the supplied web-client credentials. Use 127.0.0.1 for this configured client; its provided file registered that callback, not the localhost variant.

## Connect OpenAI

Create `.env` using `.env.example` as a reference, then set:

```dotenv
OPENAI_API_KEY=your_key_here
OPENAI_QUIZ_MODEL=gpt-5.4-mini
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Restart after changing `.env`. Connection checks run automatically before material processing and generation. Do not paste keys into chat. `.env`, `.venv/`, and `data/` are ignored by Git. Keys are never sent to the browser, exports, or SQLite. If a key has been shared in chat, revoke it and configure a replacement.

Quiz generation and visual interpretation use the Responses API with structured output and `store=False`. Whisper supplies segment timestamps. API billing and model access depend on your OpenAI account. Material is sent to OpenAI when AI processing/generation runs. `store=False` does not establish zero provider retention.

## Study dashboard

The bottom **Language** menu switches interface controls between **English** and **简体中文** and remembers the choice locally. It replaces the former Import set action. Lecture files, user names, folder/set titles, generated questions, explanations, and equations keep their original text; this preference does not request a new language from the generation model.

The three-line menu expands the sidebar or collapses it to a clickable icon rail. Navigation and folder icons retain accessible names and tooltips. Branding stays within the same sidebar column; on mobile the expanded sidebar overlays content. The appearance preference persists locally.

The interface keeps names, controls, file limits, and essential status. Decorative descriptions and footer annotations are removed; brief UI hints stay under ten words. Lecture content and quiz explanations remain complete.

Click **Create new**, Flashcards, Quiz, Calculation, or Cheat Sheet to start with **Add your lecture**. The first step shows the accepted file types and limits, a drop/browse upload, and an optional notes field. Click **Upload and continue**; topic and practice settings appear only after extraction and search indexing succeed. Failed processing stays on the upload step with a retry control.

The second step lets you enter instructions and choose the format, question count, and difficulty. The chosen module is preselected. Cheat Sheets use sections rather than questions and omit the difficulty control. Collection and earlier-study-set choices are tucked under **Collection & previous practice**. A newly uploaded lecture stays bound to its collection; earlier ready lectures remain available as RAG evidence. You can explicitly **Use saved lectures instead** without another upload. **Create another set** inherits the current quiz context and starts with those ready sources.

If there is no collection, the first upload creates one automatically. Loaded materials, settings, and the creator step survive refresh; active upload processing resumes status checks. Unsubmitted files cannot be restored after a browser refresh.

The chosen format and count are authoritative. If instructions mention a different format, the creator shows a Switch control. Opening a saved quiz does not change the settings of your next request. The app assigns stable question IDs and constrains provider output to the selected question type; source and arithmetic validation remain enabled.

**Create new** is the home page. **Study folders** group lectures by course, with file/note counts, a New folder action, and a trash button beside each folder. Deletion previews its materials and saved sets, and removes uploads, extracted sources, vectors, and saved work after confirmation. Active processing blocks deletion; changed contents require a fresh preview. Saved work remains under Sets and Materials, with search and type filtering. All visible selection controls use styled menus with keyboard navigation, typeahead, selected checkmarks, and consistent disabled states. Saved cards show question or section counts. Materials can be searched by filename, previewed, or removed. Study view supports keyboard flashcard reveal, answer feedback, review, source viewing, and export. Long processing jobs show progress and cancellation controls.

Icons and illustrations, including the Cheat Sheet notepad, are bundled locally from Lucide and Microsoft Fluent Emoji, with source URLs and licenses in [source/ASSET_CREDITS.md](source/ASSET_CREDITS.md). The interface does not depend on a remote icon CDN.

At mobile widths, existing collections can be selected and the study creator works without horizontal overflow. New folder and folder deletion are available on desktop and mobile; first uploads can also create a collection automatically.

## Study agent

Each account has a saved tutor profile: an original pixel avatar, name, and teaching style. Choose **My agent** in a group or **Customize my agent** in the personal Agent tab. Personal generation uses the signed-in student's selected private collection and saved follow-up context; profiles do not create separate model weights or unrestricted access to another account.

Open **Agent** in the sidebar and enter a request such as “Create six questions about gradient descent.” Uploads are optional. Ready lectures in the selected folder are searched first; when no indexed material or relevant passage is available, the agent generates from general knowledge. These results are labelled **General knowledge**, have no lecture citations, and remain saved in the selected folder. If no folder exists, the first Send creates **Agent practice**. The agent supports multiple-choice quizzes, flashcards, numerical calculations, and cheat sheets. **Add materials** opens the upload flow.

The model first translates the conversation into a structured generation request. Quizzes use the collection-scoped RAG pipeline: OpenAI embeddings and Chroma retrieval, optional Cohere reranking, source selection, generation, and validation. Agent cheat sheets check relevance before retaining whole-collection coverage. Missing sources or an insufficient-source selection can use general knowledge; ambiguous topics still request clarification, and provider failures remain retryable errors. General generation retains count, format, answer consistency, LaTeX structure, arithmetic, and repair checks, but does not claim source verification. Earlier chat messages provide context, not factual evidence. The standard upload-first creator continues to require lecture material.

Material processing displays an accessible progress bar without internal unit counts. Reopening either uploader clears old cancellation/error messages; previously saved uploads remain available for processing retry.

Results link to saved sets and the original lecture sources. Click **Start practice** or **Open guide** to open them. Follow-ups such as “Make these harder as flashcards” retain the prior topic and unspecified settings; explicit changes override them. Conversations persist in SQLite per account and folder. Interrupted generation can be retried, repeated network submissions are idempotent, and removed sets cannot be reopened through chat. The agent is limited to study-set creation; it is not a general Q&A tutor or a measure of student mastery.

## Practice my mistakes

After a saved multiple-choice or calculation quiz, **Practice my mistakes** appears in the summary when the current submitted answers include incorrect or skipped questions. Choose the questions to revisit and generate four new questions. The follow-up keeps the original format and difficulty, opens as a separate saved set, and retains its parent relationship. Original quiz content and progress are preserved.

The server regrades saved choices and numerical submissions rather than trusting browser correctness flags. Newly submitted calculations retain a separate graded value so editing an unsubmitted retry does not change the recorded attempt. Latest correct retries are excluded. Flashcard viewing, sample/imported sets, shared group copies, and unanswered questions are not treated as graded mistakes.

Retrieval is restricted to ready, indexed materials cited by the selected questions. Their prompts define the search focus; previous quiz questions only provide context for avoiding repetition. An additional model check reviews topical focus and novelty, with up to two repair attempts. Source/citation checks and numerical validation remain enabled. Wording similarity checks allow changed numerical givens. These checks do not prove factual correctness or diagnose a student's ability.

Generation supports cancellation, retry, idempotent network resubmission, and saved-job recovery. A completed background follow-up takes precedence over the parent's initial URL after refresh. Parent deletion detaches the previous-question and attempt context while preserving independently saved follow-ups.

## Mathematical notation

Equations render through a locally bundled KaTeX 0.19.0 library, including accessible MathML. Generation requests LaTeX in prompts, choices, answers, explanations, worked steps, and cheat-sheet formulas. Use `\( ... \)` for inline equations and `\[ ... \]` for standalone equations; paired dollar delimiters are supported for math content as well.

New/old value labels display as upright superscripts, for example `W_new` or `W_{\mathrm{new}}` becomes `W^{\mathrm{new}}`. Genuine component indices such as `W_i` remain subscripts. Variable case, mathematical values, saved answers, grading fields, and stored source excerpts remain unchanged. Saved plain-text expressions receive conservative formatting for variable indices, exponents, Greek-gradient notation, and scientific notation. Quotes and extracted content are formatted for reading while their stored text stays verbatim. Unknown notation is not reconstructed or guessed. Malformed/unsupported TeX remains visible as escaped original text with a formatting-error tooltip.

The renderer applies to individual questions, flashcard faces/hints, feedback, review, question bank, shared sets, and cheat sheets. Numeric answer fields remain scalar numbers for grading. Original PDF/images stay available through the existing source viewer. Fonts and scripts are local, so displaying saved math requires no CDN or extra AI call. Renderer options prohibit trusted HTML/links and bound macro expansion. Typesetting itself does not verify a model's mathematics; existing arithmetic and source validation remain enabled.

For frontend development/tests, run `npm install` once. Runtime assets are already bundled under `source/vendor/katex`; starting the Python app does not require npm. Math checks: `node scripts/check_math.mjs`.

## Functionality

- Create, rename, and delete study folders for courses or topics. Add PDFs, images, audio, video, text files, or pasted notes over multiple sessions.
- Generate across ready materials in the selected collection using semantic retrieval. Pending or failed additions do not replace earlier material.
- Build on a saved quiz with an editable request, inherited settings, and previous-question context. Exact repeated parent question prompts are rejected; differently worded repetitions may still occur.
- Background processing with progress, cancellation, and retry; processed material is reusable.
- PDFs: native text plus rendered-page interpretation. Images: vision interpretation.
- Audio: five-minute normalized WAV chunks under the transcription upload limit. Video: full audio plus one sampled slide frame per minute.
- Topic requests, three practice formats, three difficulties, and 4/6/8/10 questions.
- Comprehensive Cheat Sheets with model-selected sections, explanatory text, formulas, navigation, and original source links. Generation traverses the ready collection snapshot in batches.
- Cheat Sheet HTML/PDF downloads and JSON import/export.
- Validated model output, source-ID checking, and quotation matching against extracted content.
- Source viewer for the original PDF page, image, audio/video timestamp, and sampled video frame.
- Previous/Next practice navigation, feedback, flashcard recall, scalar numeric grading, and review. Quizzes show a light question card, numbered two-column answer choices (stacked on mobile), and clickable progress segments. Selecting an option grades it immediately; Don’t know reveals the answer. Correct and incorrect selections play distinct short synthesized sounds once; the speaker control mutes them and remembers the preference locally. Returning to a graded question shows its saved feedback without replaying sound. Completion shows reviewed/answered and remaining counts, optional recall/score results, and an expandable question summary. Restart flashcards (or quiz) resets session answers while preserving the saved set, stars, and hints; Back to last question and Home provide clear exits. The study view's top-left Home control returns to Sets.
- Server-saved quizzes and progress; optional browser persistence for sample/imported sessions.
- Quiz JSON import and cheat-sheet JSON export/import without raw uploads or API credentials. Practice screens omit export actions.
- Removal previews affected quizzes and deletes the material, its extracted content and embeddings, and quizzes that cite it. Quizzes using other material remain available.

## Limits

| Input | Limit |
|---|---|
| Material set | 4 files, 1 GB combined |
| PDF | 25 MB each, 100 pages combined |
| Image | 10 MB each: PNG, JPEG, WebP |
| Audio/video | 500 MB each; maximum 30 minutes |
| Text | 100,000 characters of pasted notes or per text file |

Audio: MP3, WAV, OGG, FLAC, M4A. Video: MP4, WebM. Recordings need readable sound. Once-per-minute video sampling may miss brief slides. Uploading a slide deck alongside a recording improves visual coverage.

Calculation answers are finite scalar numbers (including scientific notation), graded with an absolute tolerance. A restricted arithmetic parser checks the generated numeric and displayed answer. It does not prove that the model chose the correct formula. Symbolic, vector, and unrestricted written-answer grading are outside this version.

Supporting quotations are matched to extracted text, which can contain interpretation/transcription errors. Page and timestamp references come from application records. Review unclear equations against the original source. An absent topic or ambiguous relevant notation should prompt clarification.

Cancellation stops scheduling further work; an in-flight API request may finish first. Completed transcripts and source units are retained for retry. One active job per material set and one quiz generation per collection are allowed. New uploads can process while a quiz uses a frozen snapshot of ready material. Interrupted jobs are marked at startup and can be retried.

Material is retained in ignored local `data/` until deletion. Deletion is permanent. Exported files and browser copies of imported quizzes are independent.

## OA demonstration

Sample buttons are removed from the interface. Authored lecture fixtures in `samples/` can be uploaded for a real generation demonstration. Imported or restored authored quizzes retain their sample labels.

For a genuine AI demo:
1. Create a Machine Learning collection, then upload `samples/gradient-descent.pdf`, `samples/gradient-descent.png`, or paste `samples/gradient-descent.txt`.
2. Ask: Generate six multiple-choice questions about gradient descent. Include the update rule, learning rate, and a numerical example.
3. Answer correctly and incorrectly; inspect explanations, source references, and review.
4. Add another lecture to the same collection. Use Build on this quiz, then edit the topic, format, or difficulty.
5. Process a real recording ahead of the presentation, then show its genuine saved transcript/source results.

Sample mode is a labeled UI demonstration, not evidence of live LLM generation. The saved library also contains genuine OpenAI-generated quizzes, identified by source filename and format. Demo audio uses system-synthesized speech; the demo video combines it with a still slide.

## Verification

```sh
.venv/bin/python -m pytest -q
node scripts/check_frontend.mjs
node --check source/app.js
node --check source/local.js
```

Python tests use a fixture AI provider. They exercise actual PDF/image validation, API routes, persistence, source resolution, cancellation/retry, and generated 30-minute audio/video files processed by real FFmpeg. Live OpenAI checks also passed for the authored PDF, image, audio, and video samples. All 151 backend tests pass (see the latest verification entry for scope). The original six genuine generated quizzes are preserved, and the Growing Library Demo collection contains live-generated multiple choice, calculation, and flashcard sets, including a new set linking an existing PDF with added learning-rate schedule notes. These checks do not establish quality on arbitrary university lectures. See VERIFICATION.md for the full record.

## Retrieval and storage

SQLite remains authoritative. Extracted source text is split into approximately 800-token chunks with 100-token overlap, preserving exact character offsets and source identity. OpenAI text-embedding-3-small creates vectors (1,536 dimensions by default), stored locally in `data/chroma/`. A query retrieves up to 24 chunks from the selected collection. When COHERE_API_KEY is configured, Cohere Rerank orders these passages and returns up to 12 before the LLM checks relevance and source sufficiency. Without a key or if the service fails, generation uses the existing vector results and LLM selection. Reranking status, model, scores, and fallback reason are saved with the request; it does not establish factual correctness. Source selection is restricted to retrieved chunk IDs. Quiz generation chooses application-assigned evidence IDs; the server attaches their exact quotes and original PDF pages or recording locations. Cheat sheets use a separate whole-lecture coverage path: all ready, indexed source chunks in the request snapshot are visited in batches of ten, rather than limiting coverage to top-k search results. Completed generation batches are cached for retries. The model chooses useful section, point, and equation counts; the old question-count setting is ignored for guides. Cheat sheets use constrained excerpt IDs, and all citations are checked against supplied lecture chunks. Visiting every chunk does not guarantee that every fact appears in the final guide. Numerical validation remains enabled.

Requests, resolved settings, parent quiz IDs, retrieval snapshots, and actual source dependencies are saved in SQLite. Earlier quiz questions are follow-up context, not source evidence. The model is not trained or fine-tuned on the growing library. Source-backed retrieval does not establish factual correctness.

Changing OPENAI_EMBEDDING_MODEL requires indexing sources again. On startup, ready legacy materials with an incomplete current-model index receive resumable index jobs. Material cards show index availability and a Process / retry control. Completed extraction and transcription are reused. Indexes for different models are kept separate.

The first collections migration creates one named collection per legacy material set and retains quiz IDs, source IDs, and progress. `data/lecture_lab.pre_collections.sqlite3` is the original database backup. Installation also creates a dated backup under `data/backups/`. Keep the database, uploads, and Chroma directory together when backing up the library. They may contain private lecture content.

Local collections do not need an account or a separate database server. Upload limits apply per addition, not to the accumulated collection. The tokenizer downloads its vocabulary on first setup; after caching, chunking runs locally.

## API additions

- GET/POST `/api/collections`; GET/PATCH `/api/collections/{id}` for detail and rename.
- POST `/api/materials`: multipart files/notes plus collectionId to append a material set.
- POST `/api/quizzes`: collectionId, prompt, optional format/count/difficulty, optional parentQuizId. Missing settings inherit from the parent, otherwise default to multiple choice, six questions, intermediate difficulty. Legacy materialId requests still resolve their collection.
- GET `/api/quizzes?collectionId=...` filters the library. GET quiz detail includes request metadata and progress.
- POST `/api/materials/{id}/index` starts a resumable index job. GET `/api/materials/{id}/deletion-impact` previews dependent quiz removal.
- Uploads and generation return job IDs; the interface polls progress every two seconds. Collection status refreshes every four seconds without replacing unchanged focused controls.

## Project boundary

The older Worker starter and `.openai/hosting.json` are retained but unused. This local-only implementation does not deploy the registered Site or change the portfolio. Run `app.py`, not the Worker starter.

Cheat Sheet citations use app-assigned excerpt IDs in the model schema. The app resolves each ID to the exact stored excerpt and checks its source ownership. This avoids model-rewritten quotations; it does not establish that every generated statement is factually correct. Structured output schemas follow the [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs).


## Cohere reranking

Set `COHERE_API_KEY` in the ignored server-side `.env` file, then restart. `COHERE_RERANK_MODEL` defaults to `rerank-v4.0-fast`. Only retrieved lecture passages and the request are sent to Cohere. SQLite still scopes eligibility to the selected study folder and original material snapshot. Calls time out after 15 seconds; missing credentials, provider failures, or invalid returned indices preserve the existing retrieval path. Original source records provide citations. No additional SDK dependency is needed.

Generated quiz/flashcard screens omit the AI-generated badge and use Previous/Next. Authored samples and imports remain labelled. Cheat-sheet export and print remain available.


## Flashcards and question bank

Click the large card to flip between question and answer. Enter and Space work when the card is focused. Back and Continue navigate, with a card counter between them. Flipping preserves recall grading; the front hides the answer, explanation, and citation.

Get a hint uses the card's original lecture passage and the configured OpenAI model. Hints are cached in SQLite, capped at 140 characters, and checked for direct answer text before saving. Source inspection remains available; these checks do not establish unrestricted instructional correctness. Hint failure preserves the card and answers.

Star a generated lecture flashcard to save it in the selected folder's Question bank tab. Practice starred opens all matching saved cards, or select one card. Search filters both the list and practice queue. Stars persist across refresh and restart; unstar removes a bookmark. Question identities include their original quiz, so cards from different sets do not collide. Saved banks up to 500 cards can restore their current session from local browser state; the stars and source-backed originals live in SQLite. Imported and authored sample cards can flip, but their hint/star controls require a saved generated source. Deleting a material or folder removes dependent stars and cached hints.

## Dedicated study pages

Opening a quiz, flashcard set, or calculation set enters a dedicated study page with the app’s navy palette and Home navigation. Saved private quizzes use `/study/quiz/{id}` and group sets use `/study/shared/{id}`; authored samples, imports, and bank sessions use `/study/local`. Refresh resolves saved sets through the existing authenticated APIs. Home and browser Back leave practice without discarding saved answers.

Multiple-choice answers grade immediately. A correct response plays its existing sound and advances after 550 ms; an incorrect response opens a scrollable explanation dialog with citations and Continue. Answers can be reviewed through Explanation without regrading. The final advance opens the completion summary. Previous and Next are grouped at the bottom center. Card and navigation dimensions remain stable when answering or flipping a flashcard; longer content scrolls inside the card. Flashcard explanations use the same dialog, and flipping back hides the answer.

Calculation prompts and worked steps use locally bundled KaTeX. Existing saved questions with double-escaped math delimiters render normally after refresh. New generation requests numerical givens and functions on standalone LaTeX equation lines, with the answer hidden until checking. Scalar numerical grading and source records remain unchanged.

Each saved set has a Rename button. Renaming preserves its questions, request, sources, and practice progress. The top-left arrow slides the sidebar in or out and remembers the layout preference after refresh. The quiz Remove button is omitted from the current interface.


## Collaborative pixel classroom

Open a study group, select one or two member-owned tutors, enter a topic, and choose Discuss, Quiz, Flashcards, Calculation, or Cheat sheet. The selected teachers respond sequentially: the second receives the first response and can add another explanation or correction. Generated practice opens as a group-owned shared artifact; the group owner retains the existing drag-to-trash permission. Private quizzes and progress are not moved into the group.

The classroom uses only study sets explicitly shared to that group, including their shared excerpts. It caches embeddings in SQLite keyed by group, source hash, and embedding model, ranks candidate passages by cosine similarity, optionally applies Cohere Rerank, and uses the existing model selection stage. Current membership and current shared rows determine eligibility on every request. Selecting another member's avatar never authorizes access to that member's private lectures or practice history. When no relevant shared material exists, the teachers use labelled general knowledge.

Tutor roles use the configured OpenAI model with distinct saved teaching styles; agreement between roles is not independent fact checking. The generation step receives the teaching discussion as context, while cited shared passages remain the evidence. Structured answer/citation checks, numerical arithmetic checks, and one repair attempt remain enabled. Ambiguity and provider failures stay visible rather than silently producing unrelated content.

Classroom jobs run through the background worker, with saved discussion history, cancellation, idempotent submission, and membership rechecks. Shared sets used by active teaching jobs cannot be removed until processing stops. An interrupted classroom request can be submitted again. Empty-group cleanup removes its classroom history and vector cache.

Pixel occupants independently walk to bounded floor positions, reserve desks, sit to read and write, and move to the front during an actual teacher reply. The animations are illustrative, not measurements of student activity. Teacher selection remains stationary. Reduced-motion preferences disable roaming and animated poses. The original transparent avatar atlas, generation prompt, and provenance are in [source/art/agents/README.md](source/art/agents/README.md).
