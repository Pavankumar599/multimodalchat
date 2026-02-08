import React, { useEffect, useMemo, useRef, useState } from "react";
import { sendMessage, transcribeAudio, ChatResponse } from "./api";

type Msg =
  | { id: string; role: "user"; kind: "text"; text: string }
  | { id: string; role: "assistant"; kind: "text"; text: string }
  | { id: string; role: "assistant"; kind: "image"; url: string }
  | { id: string; role: "assistant"; kind: "video"; url: string };

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  // Audio recording
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, busy]);

  const canSend = useMemo(() => input.trim().length > 0 && !busy, [input, busy]);

  async function onSend(text: string) {
    const cleaned = text.trim();
    if (!cleaned) return;

    setBusy(true);
    const userMsg: Msg = { id: uid(), role: "user", kind: "text", text: cleaned };
    setMessages((m) => [...m, userMsg]);
    setInput("");

    try {
      const resp: ChatResponse = await sendMessage(sessionId, cleaned);
      setSessionId(resp.session_id);

      if (resp.content_type === "text") {
        setMessages((m) => [...m, { id: uid(), role: "assistant", kind: "text", text: resp.text }]);
      } else if (resp.content_type === "image") {
        setMessages((m) => [...m, { id: uid(), role: "assistant", kind: "image", url: `http://localhost:8000${resp.asset_url}` }]);
      } else {
        setMessages((m) => [...m, { id: uid(), role: "assistant", kind: "video", url: `http://localhost:8000${resp.asset_url}` }]);
      }
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        { id: uid(), role: "assistant", kind: "text", text: `⚠️ Error: ${e.message || String(e)}` }
      ]);
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    if (recording || busy) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });

    audioChunksRef.current = [];
    mr.ondataavailable = (evt) => {
      if (evt.data.size > 0) audioChunksRef.current.push(evt.data);
    };

    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunksRef.current, { type: "audio/webm" });
      setRecording(false);
      setBusy(true);
      try {
        const text = await transcribeAudio(blob);
        setInput((prev) => (prev ? `${prev} ${text}` : text));
      } catch (e: any) {
        setMessages((m) => [
          ...m,
          { id: uid(), role: "assistant", kind: "text", text: `⚠️ Transcription error: ${e.message || String(e)}` }
        ]);
      } finally {
        setBusy(false);
      }
    };

    mediaRecorderRef.current = mr;
    mr.start();
    setRecording(true);
  }

  function stopRecording() {
    const mr = mediaRecorderRef.current;
    if (mr && mr.state !== "inactive") mr.stop();
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="title">Multimodal Chat</div>
        <div className="subtitle">Text + Mic → Text / Image / Video (iterate until satisfied)</div>
      </header>

      <main className="chat">
        {messages.length === 0 ? (
          <div className="empty">
            <div className="emptyTitle">Try:</div>
            <ul>
              <li>“Write a short product description for a smart bottle.”</li>
              <li>“Generate an image of a neon cyberpunk street food stall.”</li>
              <li>“Create a 4-second video of a calico cat playing piano on stage.”</li>
              <li>Then refine: “Make it more realistic”, “Add rain”, “Change camera angle”, etc.</li>
            </ul>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`row ${m.role}`}>
              <div className={`bubble ${m.role}`}>
                {m.kind === "text" && <div className="text">{m.text}</div>}
                {m.kind === "image" && <img className="image" src={m.url} alt="generated" />}
                {m.kind === "video" && (
                  <video className="video" src={m.url} controls playsInline />
                )}
              </div>
            </div>
          ))
        )}

        {busy && (
          <div className="row assistant">
            <div className="bubble assistant">
              <div className="typing">Thinking…</div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <footer className="composer">
        <button
          className={`mic ${recording ? "active" : ""}`}
          onClick={recording ? stopRecording : startRecording}
          disabled={busy}
          title={recording ? "Stop recording" : "Record audio"}
        >
          {recording ? "■ Stop" : "🎤 Mic"}
        </button>

        <textarea
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message… (or use 🎤 Mic)"
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend(input);
            }
          }}
        />

        <button className="send" onClick={() => onSend(input)} disabled={!canSend}>
          Send
        </button>
      </footer>
    </div>
  );
}
