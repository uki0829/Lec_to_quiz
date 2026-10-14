# Build prompt: Lecture Lab

Build a working AI Lecture-to-Quiz web application called Lecture Lab. The user is a student who has lecture slides, notes, a question sheet, or a lecture recording, and wants targeted active practice instead of rereading material.

The central interaction is: add lecture material -> describe what to practice -> select a quiz format -> generate -> answer interactively -> review explanations and source references.

Accept PDF files, lecture images, audio recordings, video recordings, and pasted notes. Explain supported formats and size limits. Use a real multimodal LLM to interpret uploaded material; do not show an upload as processed unless it was actually sent to the model. Keep provider credentials on the server or transiently supplied by the user, never embedded in source or stored in browser storage. Tell the user that generation sends their material to the provider.

Let the user choose:
- Flashcards: show a question, reveal the answer, and mark it as known or needing review.
- Multiple choice: select one option, submit it, and receive feedback explaining the correct answer and the misconception behind distractors.
- Calculation practice: enter a numeric answer, receive feedback using an explicit tolerance, and reveal worked solution steps.

Include a prompt box such as: "Generate 6 multiple-choice questions about gradient descent from these computer science slides. Start with the update rule, then cover learning rate and one numerical example."

Also provide question count and difficulty controls. Scope questions to the requested topic and uploaded sources. Preserve notation, definitions, and course-specific conventions. If the topic is missing, the input is unreadable, or an equation is ambiguous, explain the limitation and ask for useful clarification. Do not invent source quotations, page numbers, or timestamps. Each question must include a source filename, available page or timestamp locator, and a brief supporting excerpt. Treat source references as model-provided and let users inspect the original material.

Use a strict structured question schema, validate the model response, and render it as UI rather than displaying raw generated text. A question has an ID, type, prompt, answer/explanation, steps, and source reference. Multiple-choice questions also have options and a correct-option index. Calculation questions have a numeric answer and absolute tolerance. Check simple numeric answers in application code, while recognizing that the correctness of a model-generated solution still needs source review.

Build keyboard-accessible navigation, one question at a time, progress, a review screen, retrying missed questions, and JSON export/import of quiz content. Keep answers hidden until the student submits or reveals them. Preserve a previous quiz if new generation fails. Show useful loading, missing-key, file-size, unreadable-source, and provider-error states.

Use a clean academic workspace with a source panel and a practice panel, readable typography, calm blue accents, and responsive layouts. Prefer useful interactions over decorative animation. Support reduced motion.

Include a sample gradient-descent lecture and a clearly labeled sample quiz for interface demonstration without API credentials. Sample mode must never imply it analyzed the user's uploads or that a fixture was generated live. Keep actual LLM generation as a separate action.

Acceptance demonstration:
1. Add real computer science notes or slides.
2. Request gradient-descent multiple choice and generate a grounded quiz with an actual LLM.
3. Answer correctly and incorrectly; inspect feedback and source references.
4. Generate flashcards and calculation practice.
5. Try an unrelated topic and a missing time/notation detail; show honest clarification or limitations.
6. Verify sample mode, validation, numeric grading, accessibility, and failure handling. Report which provider and upload paths were tested live and which remain unverified.

For the first prototype, use JavaScript with a small server endpoint and Gemini's multimodal generateContent API with structured JSON output. Allow PDFs, images, and short audio/video samples within a documented upload limit. Use a Files API and transcription/chunking pipeline in a later version for full-length recordings; do not claim that long recordings are already supported.
