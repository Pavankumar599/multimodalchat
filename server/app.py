import os
import time
import uuid
import base64
from typing import Literal, Optional, Dict, Any, List

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from openai import OpenAI

load_dotenv()

# ---------- Config ----------
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gpt-4o-mini")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gpt-5.2")
STT_MODEL = os.getenv("STT_MODEL", "gpt-4o-mini-transcribe")

VIDEO_MODEL = os.getenv("VIDEO_MODEL", "sora-2")
VIDEO_SECONDS = os.getenv("VIDEO_SECONDS", "4")
VIDEO_SIZE = os.getenv("VIDEO_SIZE", "720x1280")
VIDEO_POLL_SECONDS = float(os.getenv("VIDEO_POLL_SECONDS", "2"))
VIDEO_TIMEOUT_SECONDS = float(os.getenv("VIDEO_TIMEOUT_SECONDS", "180"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = OpenAI()

# ---------- App ----------
app = FastAPI(title="Multimodal Chat (Text+Audio → Text/Image/Video)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated assets
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# ---------- Models ----------
Intent = Literal["text", "image", "video"]

class RouteDecision(BaseModel):
    intent: Intent = Field(description="Which generator to use: text, image, or video.")
    prompt: str = Field(description="A clean prompt to send to the generator.")
    # Optional hints for video:
    seconds: Optional[Literal["4", "8", "12"]] = Field(default=None, description="Video length in seconds.")
    size: Optional[Literal["720x1280", "1280x720", "1024x1792", "1792x1024"]] = Field(default=None, description="Video resolution.")
    # Optional hint for images:
    style: Optional[str] = Field(default=None, description="Optional style hint for images (e.g. 'pixel art', 'cinematic').")

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    text: str

class ChatResponse(BaseModel):
    session_id: str
    intent: Intent
    content_type: Literal["text", "image", "video"]
    text: Optional[str] = None
    asset_url: Optional[str] = None
    debug: Optional[Dict[str, Any]] = None

class SessionState(BaseModel):
    messages: List[Dict[str, str]] = Field(default_factory=list)  # [{role, content}, ...]
    last_intent: Optional[Intent] = None

    # For multi-turn image edits via previous_response_id:
    last_image_response_id: Optional[str] = None

    # For multi-turn video remix:
    last_video_id: Optional[str] = None
    last_video_completed: bool = False

SESSIONS: Dict[str, SessionState] = {}

# ---------- Helpers ----------
def get_or_create_session(session_id: Optional[str]) -> tuple[str, SessionState]:
    if session_id and session_id in SESSIONS:
        return session_id, SESSIONS[session_id]
    sid = session_id or str(uuid.uuid4())
    SESSIONS[sid] = SessionState()
    return sid, SESSIONS[sid]

def route_intent(user_text: str, session: SessionState) -> RouteDecision:
    """
    Uses Structured Outputs (Pydantic) to return a guaranteed schema.
    """
    # Include lightweight context so "make it brighter" routes correctly.
    last_few = session.messages[-6:]
    convo = "\n".join([f"{m['role']}: {m['content']}" for m in last_few]) if last_few else "(none)"

    system = (
        "You are an intent router for a multimodal assistant.\n"
        "Decide whether the user wants TEXT, IMAGE (art), or VIDEO output.\n"
        "Return a RouteDecision with:\n"
        "- intent: one of text|image|video\n"
        "- prompt: a clean standalone prompt for the generator\n"
        "- seconds, size only if intent=video\n"
        "- style only if intent=image and it helps\n"
        "Rules:\n"
        "- If the user asks to 'draw', 'generate image', 'logo', 'poster', 'art', pick image.\n"
        "- If the user asks for 'video', 'animation', 'clip', 'Sora', pick video.\n"
        "- Otherwise pick text.\n"
        "- If the user is refining the previous output (e.g. 'make it more realistic'), keep the same intent as context suggests.\n"
    )

    resp = client.responses.parse(
        model=ROUTER_MODEL,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Recent conversation:\n{convo}\n\nUser message:\n{user_text}"},
        ],
        text_format=RouteDecision,
    )
    return resp.output_parsed

def save_bytes(ext: str, data: bytes) -> str:
    fname = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "wb") as f:
        f.write(data)
    return f"/outputs/{fname}"

def generate_text(session: SessionState, prompt: str) -> str:
    # Add user message to history, then call model with all messages
    session.messages.append({"role": "user", "content": prompt})
    resp = client.responses.create(
        model=TEXT_MODEL,
        input=session.messages,
    )
    text = resp.output_text or ""
    session.messages.append({"role": "assistant", "content": text})
    return text

def generate_image(session: SessionState, prompt: str, style: Optional[str]) -> str:
    # If user is iterating on image, we can use previous_response_id for higher fidelity edits.
    input_prompt = prompt if not style else f"{prompt}\n\nStyle: {style}"

    kwargs = {}
    if session.last_intent == "image" and session.last_image_response_id:
        kwargs["previous_response_id"] = session.last_image_response_id

    resp = client.responses.create(
        model=TEXT_MODEL,
        input=input_prompt,
        tools=[{"type": "image_generation"}],
        **kwargs,
    )

    session.last_image_response_id = resp.id

    image_b64 = None
    for item in resp.output:
        # SDK returns typed objects; be defensive.
        t = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if t == "image_generation_call":
            image_b64 = getattr(item, "result", None) or (item.get("result") if isinstance(item, dict) else None)
            break

    if not image_b64:
        raise HTTPException(status_code=500, detail="No image generated in response output.")

    img_bytes = base64.b64decode(image_b64)
    return save_bytes("png", img_bytes)

def poll_video_until_done(video_id: str) -> Any:
    deadline = time.time() + VIDEO_TIMEOUT_SECONDS
    while time.time() < deadline:
        job = client.videos.retrieve(video_id)
        status = getattr(job, "status", None)
        if status == "completed":
            return job
        if status == "failed":
            raise HTTPException(status_code=500, detail=f"Video job failed: {video_id}")
        time.sleep(VIDEO_POLL_SECONDS)
    raise HTTPException(status_code=504, detail=f"Video generation timed out: {video_id}")

def download_video_mp4(video_id: str) -> str:
    response = client.videos.download_content(video_id=video_id)
    video_bytes = response.read()
    return save_bytes("mp4", video_bytes)

def generate_video(session: SessionState, prompt: str, seconds: Optional[str], size: Optional[str]) -> str:
    use_seconds = seconds or VIDEO_SECONDS
    use_size = size or VIDEO_SIZE

    # If iterating on a completed video, remix it.
    if session.last_intent == "video" and session.last_video_id and session.last_video_completed:
        job = client.videos.remix(
            video_id=session.last_video_id,
            prompt=prompt,
        )
    else:
        job = client.videos.create(
            prompt=prompt,
            model=VIDEO_MODEL,
            seconds=use_seconds,
            size=use_size,
        )

    session.last_video_id = job.id
    session.last_video_completed = False

    poll_video_until_done(job.id)
    session.last_video_completed = True

    return download_video_mp4(job.id)

# ---------- Routes ----------
@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Accepts audio blobs recorded in the browser and returns a transcript.
    """
    try:
        # UploadFile.file is a SpooledTemporaryFile; OpenAI SDK can read it.
        transcript = client.audio.transcriptions.create(
            model=STT_MODEL,
            file=file.file,
            response_format="text",
        )
        return {"text": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

@app.post("/api/message", response_model=ChatResponse)
async def handle_message(req: ChatRequest) -> ChatResponse:
    session_id, session = get_or_create_session(req.session_id)

    user_text = (req.text or "").strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Empty message.")

    decision = route_intent(user_text, session)

    # Store the raw user text too (for context), but generator may use decision.prompt.
    session.messages.append({"role": "user", "content": user_text})

    try:
        if decision.intent == "text":
            out_text = generate_text(session, decision.prompt)
            session.last_intent = "text"
            return ChatResponse(
                session_id=session_id,
                intent="text",
                content_type="text",
                text=out_text,
                debug={"routed_prompt": decision.prompt},
            )

        if decision.intent == "image":
            url = generate_image(session, decision.prompt, decision.style)
            session.last_intent = "image"
            # Add a lightweight assistant message so routing has context.
            session.messages.append({"role": "assistant", "content": f"[image generated] {url}"})
            return ChatResponse(
                session_id=session_id,
                intent="image",
                content_type="image",
                asset_url=url,
                debug={"routed_prompt": decision.prompt, "style": decision.style},
            )

        if decision.intent == "video":
            url = generate_video(session, decision.prompt, decision.seconds, decision.size)
            session.last_intent = "video"
            session.messages.append({"role": "assistant", "content": f"[video generated] {url}"})
            return ChatResponse(
                session_id=session_id,
                intent="video",
                content_type="video",
                asset_url=url,
                debug={"routed_prompt": decision.prompt, "seconds": decision.seconds, "size": decision.size},
            )

        raise HTTPException(status_code=500, detail="Unknown intent.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
