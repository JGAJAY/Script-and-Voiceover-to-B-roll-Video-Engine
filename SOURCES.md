# SOURCES.md: Media Sources, Models, APIs, and Libraries Disclosure

In compliance with the IncuBrix Engineering Assessment 3 disclosure rules, this document lists every model, API, library, dataset, and media source utilized in the **Script and Voiceover to B-roll Video Engine**.

All assets and dependencies in the default execution path are strictly verified for commercial usability without copyleft or non-commercial restrictions.

---

## 1. AI Models & Voice Synthesis

| Component | Model / Provider | License | Commercial Use | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Multilingual TTS** | `edge-tts` (Microsoft Neural Azure Voices: `en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`, `ta-IN-PallaviNeural`) | MIT License | Permitted | High-fidelity multilingual text-to-speech with word-level boundary alignment for English, Hindi, and Tamil. |
| **Offline Synthesizer** | Harmonic Vectorized Formant Synthesizer (`src/services/tts_service.py`) | MIT License / Apache 2.0 | Permitted | Fast, zero-dependency offline vocal tone synthesizer for hermetic automated tests and disconnected environments. |
| **VLM Relevance Evaluator** | IncuBrix Semantic Alignment & CLIP Cosine Scoring Engine | Apache 2.0 | Permitted | Independent scoring of video footage against narration text (1.0 to 5.0 scale). |

---

## 2. Media & Footage Sources

| Source | Provider | License | Commercial Terms | Attribution Handling |
| :--- | :--- | :--- | :--- | :--- |
| **Verified Commercial Library** | IncuBrix Open Media Catalog (`src/services/footage_sources/local_library_provider.py`) | CC0 1.0 Universal (Public Domain) | 100% Free for commercial use; no rights reserved; watermark-free. | Recorded per clip in `timeline.json` and `manifest.json`. |
| **Generative Video Engine** | Procedural Fractal & Harmonic Vector Visualizer (`src/services/footage_sources/generative_provider.py`) | CC0 Equivalent Synthetic Generation | Fully cleared for commercial distribution; no copyright claims. | Marked as `is_ai_generated: true` with rationale in `timeline.json`. |
| **Stock Video API (Optional)** | Pexels Video API (`src/services/footage_sources/stock_provider.py`) | Pexels License | Free for commercial use; modification permitted; no attribution mandatory. | Creator name and Pexels URL logged in `timeline.json`. |
| **Pixabay Video (Optional)** | Pixabay Video API | Pixabay Content License | Free for commercial use; no attribution required. | Recorded in `timeline.json`. |

---

## 3. Libraries & Software

| Package | Version | License | Commercial Permitted | Function |
| :--- | :--- | :--- | :--- | :--- |
| **FFmpeg** | 9.0.2-essentials (gyan.dev) | GPL 3.0 / LGPL 3.0 (binary standalone) | Permitted | Video decoding, scaling, aspect ratio reframing, color grading, subtitle burn-in, audio muxing. |
| **FastAPI** | 0.165.0 | MIT License | Permitted | Asynchronous HTTP web framework & OpenAPI 3.1 generation. |
| **Starlette** | 1.10.0 | BSD 3-Clause | Permitted | ASGI framework kernel and request routing. |
| **Pydantic** | 2.14.4 | MIT License | Permitted | Data validation and settings management. |
| **Uvicorn** | 0.54.0 | BSD 3-Clause | Permitted | Lightning-fast ASGI production web server. |
| **HTTPX** | 0.28.1 | BSD 3-Clause | Permitted | Async HTTP client for webhook delivery and media ingestion. |
| **NumPy** | 2.5.5 | BSD 3-Clause | Permitted | Vectorized audio and frame tensor computations. |
| **OpenPyXL** | 3.1.5 | MIT License | Permitted | Generation of automated assessment Excel submission forms. |
| **Pytest** | 9.2.0 | MIT License | Permitted | Automated test execution framework. |

---

## 4. Rights & Commercial Safety Verification

- **Watermark-Free**: Every procedural clip and stock asset contains zero watermarks or promotional logos.
- **No Realistic Faces of Real People**: Protected by safety guardrails in `GenerativeVideoProvider` (replaces named celebrities/politicians with stylized symbolic silhouettes).
- **No Invented Brand Logos**: Explicit exclusion filter prevents synthetic trademark fabrication.
- **Solemn & Sensitive News Guard**: Sourcing decision rule routes sensitive narratives exclusively to verified, respectful real-world footage.
- **No Non-Commercial Licenses**: Zero CC BY-NC, CC BY-ND, or research-only weights used in the default pipeline.
