# Lecture Lab

A local AI Lecture-to-Quiz application. Add lecture material, ask for a topic, and practice using multiple choice, flashcards, or scalar calculations, and generate source-linked cheat sheets. The dark study dashboard is served by Python FastAPI, with SQLite for collections, materials, requests, jobs, quizzes, and progress, plus a persistent local Chroma index for lecture retrieval.

## Start

The project virtual environment is already installed on this computer. From this folder:

```sh
bash scripts/start.sh
```

Open **http://127.0.0.1:8765**. The app binds to localhost, has no login, and is not deployed. On another computer, install Python 3.12 and run `bash scripts/setup.sh` first. Bundled FFmpeg is provided by `imageio-ffmpeg`; use `FFMPEG_PATH` for a separate installation.

## Connect OpenAI

Create `.env` using `.env.example` as a reference, then set:

```dotenv
OPENAI_API_KEY=your_key_here
OPENAI_QUIZ_MODEL=gpt-5.4-mini
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Restart after changing `.env`. The interface's AI connection section reports whether a key is configured. Do not paste keys into chat. `.env`, `.venv/`, and `data/` are ignored by Git. Keys are never sent to the browser, exports, or SQLite. If a key has been shared in chat, revoke it and configure a replacement.

Quiz generation and visual interpretation use the Responses API with structured output and `store=False`. Whisper supplies segment timestamps. API billing and model access depend on your OpenAI account. Material is sent to OpenAI when AI processing/generation runs. `store=False` does not establish zero provider retention.

## Study dashboard

The interface keeps names, controls, file limits, and essential status. Decorative descriptions and footer annotations are removed; brief UI hints stay under ten words. Lecture content and quiz explanations remain complete.

Click **Create new**, Flashcards, Quiz, Calculation, or Cheat Sheet to start with **Add your lecture**. The first step shows the accepted file types and limits, a drop/browse upload, and an optional notes field. Click **Upload and continue**; topic and practice settings appear only after extraction and search indexing succeed. Failed processing stays on the upload step with a retry control.

The second step lets you enter instructions and choose the format, question count, and difficulty. The chosen module is preselected. Cheat Sheets use sections rather than questions and omit the difficulty control. Collection and earlier-study-set choices are tucked under **Collection & previous practice**. A newly uploaded lecture stays bound to its collection; earlier ready lectures remain available as RAG evidence. You can explicitly **Use saved lectures instead** without another upload. **Create another set** inherits the current quiz context and starts with those ready sources.

If there is no collection, the first upload creates one automatically. Loaded materials, settings, and the creator step survive refresh; active upload processing resumes status checks. Unsubmitted files cannot be restored after a browser refresh.

The chosen format and count are authoritative. If instructions mention a different format, the creator shows a Switch control. Opening a saved quiz does not change the settings of your next request. The app assigns stable question IDs and constrains provider output to the selected question type; source and arithmetic validation remain enabled.

**Library** has a collection selector, Sets and Materials tabs, search, and a set-type filter. Saved cards show question or section counts. Materials can be searched by filename, previewed, or removed. Study view supports keyboard flashcard reveal, answer feedback, review, source viewing, and export. Long processing jobs show progress and cancellation controls.

Icons and illustrations, including the Cheat Sheet notepad, are bundled locally from Lucide and Microsoft Fluent Emoji, with source URLs and licenses in [source/ASSET_CREDITS.md](source/ASSET_CREDITS.md). The interface does not depend on a remote icon CDN.

At mobile widths, existing collections can be selected and the study creator works without horizontal overflow. Named collection creation uses the desktop sidebar; first uploads can also create a collection automatically.

## Functionality

- Create and rename study collections for courses or topics. Add PDFs, images, audio, video, text files, or pasted notes over multiple sessions.
- Generate across ready materials in the selected collection using semantic retrieval. Pending or failed additions do not replace earlier material.
- Build on a saved quiz with an editable request, inherited settings, and previous-question context. Exact repeated parent question prompts are rejected; differently worded repetitions may still occur.
- Background processing with progress, cancellation, and retry; processed material is reusable.
- PDFs: native text plus rendered-page interpretation. Images: vision interpretation.
- Audio: five-minute normalized WAV chunks under the transcription upload limit. Video: full audio plus one sampled slide frame per minute.
- Topic requests, three practice formats, three difficulties, and 4/6/8/10 questions.
- Cheat Sheets with 4/6/8/10 sections, key points, formulas, section navigation, and original source links. Saved sheets use the same SQLite request/dependency records and collection-scoped RAG retrieval as quizzes.
- Cheat Sheet JSON export/import and a Print action using the browser print dialog.
- Validated model output, source-ID checking, and quotation matching against extracted content.
- Source viewer for the original PDF page, image, audio/video timestamp, and sampled video frame.
- Question navigation, feedback, flashcard recall, scalar numeric grading, review, and retry.
- Server-saved quizzes and progress; optional browser persistence for sample/imported sessions.
- Quiz JSON export/import without raw uploads or API credentials.
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

## Sample mode and OA demonstration

Try the sample lecture uses an authored lecture and six authored questions in the selected format. It is visibly labeled and never analyzes user uploads or the topic request. It works without credentials.

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

Python tests use a fixture AI provider. They exercise actual PDF/image validation, API routes, persistence, source resolution, cancellation/retry, and generated 30-minute audio/video files processed by real FFmpeg. Live OpenAI checks also passed for the authored PDF, image, audio, and video samples. All 33 backend tests pass. The original six genuine generated quizzes are preserved, and the Growing Library Demo collection contains live-generated multiple choice, calculation, and flashcard sets, including a new set linking an existing PDF with added learning-rate schedule notes. These checks do not establish quality on arbitrary university lectures. See VERIFICATION.md for the full record.

## Retrieval and storage

SQLite remains authoritative. Extracted source text is split into approximately 800-token chunks with 100-token overlap, preserving exact character offsets and source identity. OpenAI text-embedding-3-small creates vectors (1,536 dimensions by default), stored locally in `data/chroma/`. A query retrieves up to 24 chunks from the selected collection; the model selects up to 12 for quiz generation. Quotes are checked against those chunks, and citations resolve to original PDF pages or recording locations. Numerical validation remains enabled.

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
