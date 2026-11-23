# AI_USE.md: Disclosure of AI Tools Used

In accordance with Rule 1 of the IncuBrix Engineering Assessment 3 ("Disclose everything... list every AI coding tool you used (and for what) in AI_USE.md"), this document details the AI tools and assistants used during development.

---

## 1. AI Coding Assistants Used

| Tool | Provider | Purpose / Scope of Usage |
| :--- | :--- | :--- |
| **Antigravity AI (Google DeepMind)** | Google | Primary development assistant. Utilized for architecture design, writing service adapters, writing automated pytest suites, optimizing FFmpeg filter graphs, crafting the web UI frontend, and preparing documentation. |
| **Claude / Copilot** | Anthropic / GitHub | Utilized during initial prototyping of word boundary timestamp alignment heuristics and regular expression design for double-meaning keyword detection. |

---

## 2. Granular Task Breakdown

### A. Architecture & Schema Modeling
- Used AI to translate the IncuBrix Assessment 3 PDF specification into clean Pydantic V2 models and OpenAPI 3.1 specifications.
- Defined standard error structures conforming to `UPPER_SNAKE_CASE` codes (`INVALID_INPUT`, `SILENT_AUDIO`, `SWAP_INVALID_SCENE`, etc.).

### B. FFmpeg Pipeline Design
- Designed color grading and contrast equalization filter chains (`eq=contrast=1.05:brightness=0.01:saturation=1.12`) to unify footage from disparate sources.
- Designed smart reframing equations for 9:16 portrait and 1:1 square crops from landscape stock.
- Developed zero-latency segment concatenation via FFmpeg's concat demuxer for fast partial clip swapping.

### C. Testing & Edge Case Generation
- Generated test suite spanning unit, API route, integration pipeline, and hard-case tests (silence detection, wrong file types, double meanings, clip swaps).
- Formulated test inputs across 10 distinct genres (tech tutorials, product promos, travel stories, multilingual Hindi/Tamil voiceovers, abstract financial metrics).

---

## 3. Candidate Attestation

- All generated code has been reviewed, tested, and verified locally by the candidate.
- The candidate understands the design, the architecture, and every line of code implemented, and is prepared to explain and modify any component during the 60-90 minute live technical evaluation session.
