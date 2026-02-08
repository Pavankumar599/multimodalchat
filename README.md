This project is an **end-to-end multimodal AI assistant** (a mini ChatGPT-like app) that:

- Takes **user input as text** (typed) or **audio** (microphone)
- Converts audio → text using **Speech-to-Text**
- Understands what the user wants (**intent detection / routing**)
- Calls the correct generator and returns the output inside the chat UI:
  - **Text output**: answers, explanations, summaries, code, etc.
  - **Image output**: AI art / posters / logos / illustrations
  - **Video output**: short generated clips (via Sora)

It also supports **multi-turn iteration**: if the user says “make it more realistic”, “add rain”, “change style”, etc., the app keeps generating improved results until the user is satisfied.
