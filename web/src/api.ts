export type ChatResponse =
  | {
      session_id: string;
      intent: "text" | "image" | "video";
      content_type: "text";
      text: string;
      asset_url?: string | null;
      debug?: any;
    }
  | {
      session_id: string;
      intent: "text" | "image" | "video";
      content_type: "image" | "video";
      text?: string | null;
      asset_url: string;
      debug?: any;
    };

const API_BASE = "http://localhost:8000";

export async function sendMessage(sessionId: string | null, text: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, text })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");

  const res = await fetch(`${API_BASE}/api/transcribe`, {
    method: "POST",
    body: fd
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  const data = await res.json();
  return data.text as string;
}
