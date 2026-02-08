## What is this project?

This project is an **end-to-end multimodal AI assistant** (a mini ChatGPT-like app) that:

- Takes **user input as text** (typed) or **audio** (microphone)
- Converts audio → text using **Speech-to-Text**
- Understands what the user wants (**intent detection / routing**)
- Calls the correct generator and returns the output inside the chat UI:
  - **Text output**: answers, explanations, summaries, code, etc.
  - **Image output**: AI art / posters / logos / illustrations
  - **Video output**: short generated clips (via Sora)

It also supports **multi-turn iteration**: if the user says “make it more realistic”, “add rain”, “change style”, etc., the app keeps generating improved results until the user is satisfied.

---

## Why do we use this project?

Most AI demos only do **one thing** (only chat, only image generation, or only video generation).  
In real products, users want a single experience where they can ask naturally and the app decides what to do.

This project is useful when you want to build:

- A **single UI** for multiple AI capabilities (text + image + video)
- A system where the model **understands user intent** and automatically selects the right tool
- A prototype for an “AI assistant product” similar to ChatGPT, but customized to your use case
- An internal tool for teams (marketing, design, content) to generate assets quickly

---

## How intent detection (routing) works

When the user sends a message, the backend runs a small “router” model that returns structured JSON:

- If the message is about writing/explaining → route to **text**
- If the message is about drawing/art/poster/logo → route to **image**
- If the message is about animation/clip/video → route to **video**

This keeps the app simple for users: they just ask normally and the app chooses the right output type.

---

## How multi-turn improvement works (“until user likes it”)

The project keeps a session per user in memory.

- **Text**: uses chat history so follow-ups improve the answer
- **Image**: uses the previous image generation response as context so “make it brighter” edits the last image instead of starting from scratch
- **Video**: generates the first video, then uses remix/variation for follow-up improvements

This is important because real users almost always iterate (first output is rarely perfect).

# =======================================
# How to Execute (macOS + Windows)

This project has two parts:
- **Backend (FastAPI, Python)** → runs on `http://localhost:8000`
- **Frontend (React, Vite)** → runs on `http://localhost:5173`

You must run both in separate terminals.

---
# =========================================
## ✅ macOS (zsh) / Linux

### 1) Clone repo
```bash
git clone https://github.com/<your-username>/multimodal-chat.git
cd multimodal-chat
```
### 2) Backend setup (FastAPI)
```bash
cd server
cp .venv .venv
```
Edit .venv and set your OPENAI API key:

Create venv + install:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run backend:
```bash
uvicorn app:app --reload --port 8000
```
Backend is now running at:

http://localhost:8000

Keep this terminal running.

### 3) Frontend setup (React)
```bash
cd web
npm install
npm run dev
```
Frontend is now running at:

http://localhost:5173

# =======================================
### ✅ Windows (PowerShell)
#
## 1) Clone repo
```bash
git clone https://github.com/<your-username>/multimodal-chat.git
cd multimodal-chat
```

# 2) Backend setup (FastAPI)
``` bash
cd server
Copy-Item .venv .venv
```

Edit .venv and set:

Create venv + install
```bsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run backend
```bash
uvicorn app:app --reload --port 8000
```

Backend is now running at:

http://localhost:8000

Keep this terminal running.

# 3) Frontend setup (React)
```bash
cd web
npm install
npm run dev
```
Frontend is now running at:

http://localhost:5173





