# Example Scripts for IncuBrix B‑Roll Video Engine

This repository provides three ready‑to‑use example scripts that demonstrate the engine’s ability to generate accurate, semantically‑matched B‑roll video from plain‑text narration.

| Example | Description | Voice | Expected Scenes |
|---|---|---|---|
| **finance_example.txt** | Personal savings story – shows money‑saving and investment visuals. | `en-US‑Matthew` | Budget spreadsheet → piggy bank deposit → digital dashboard → animated coins → calm office reminder |
| **tech_example.txt** | Python web‑scraper tutorial – visualizes coding, data crawling, and results. | `en-US‑Matthew` | Laptop with VS Code → spider‑web crawl animation → CSV filling → city skyline data streams |
| **business_example.txt** | Startup pitch – highlights teamwork, real‑time dashboards, and secure cloud sync. | `en-US‑Matthew` | Modern coworking space → live dashboard → document sync with lock → handshake over digital globe |

**How to use**
1. Ensure the API service is running (`uvicorn src.main:app --port 8000`).
2. Submit a job via the UI or API using the script file as the `script` field and the selected voice.
3. The engine will automatically select appropriate footage from its internal library and return the rendered video.

No external video files are required – the engine handles footage selection internally.

---
*These examples are versioned alongside the code to simplify testing and demoing.*