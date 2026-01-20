"""
OpenAI Responses API Proxy for OpenWebUI

This proxy intercepts Chat Completions requests from OpenWebUI,
detects embedded PDF markers, and forwards them to OpenAI's Responses API
with proper input_file support for vision analysis.

Run with: uvicorn openai_responses_proxy:app --host 0.0.0.0 --port 8000
"""

import os
import re
import json
import base64
import mimetypes
import httpx
import csv
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse  # type: ignore
import asyncio

app = FastAPI(title="OpenAI Responses Proxy")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEBUG = os.environ.get("PROXY_DEBUG", "true").lower() == "true"
MAX_FILE_MB = 10
MAX_TOTAL_MB = 40
MAX_DOCX_CHARS = 40000  # safety cap
MAX_CSV_ROWS = 1000
MAX_CSV_COLS = 50
MAX_XLSX_ROWS = 500
MAX_XLSX_COLS = 50
MAX_TEXT_CHARS = 40000
MAX_JSON_BYTES = 1_000_000

# Regex to find PDF markers: [__PDF_FILE_B64__ filename=xxx.pdf]base64data[/__PDF_FILE_B64__]
PDF_MARKER_RE = re.compile(
    r"\[__PDF_FILE_B64__ filename=([^\]]+)\]([A-Za-z0-9+/=]+)\[/__PDF_FILE_B64__\]",
    re.DOTALL
)


def log(msg: str):
    if DEBUG:
        print(f"[PROXY] {msg}")


def _get_file_path(file_obj: Dict[str, Any]) -> str:
    if not isinstance(file_obj, dict):
        return ""
    if isinstance(file_obj.get("file"), dict):
        f = file_obj["file"]
        path = f.get("path", "") or ""
        if not path and isinstance(f.get("meta"), dict):
            path = f["meta"].get("path", "") or ""
        return path.strip()
    return (file_obj.get("path") or "").strip()


def _get_file_name(file_obj: Dict[str, Any]) -> str:
    if not isinstance(file_obj, dict):
        return ""
    if isinstance(file_obj.get("file"), dict):
        f = file_obj["file"]
        name = f.get("filename") or f.get("name") or ""
        if not name and isinstance(f.get("meta"), dict):
            name = f["meta"].get("name") or ""
        return name.strip()
    return (file_obj.get("name") or file_obj.get("filename") or "").strip()


def _extract_all_files(body: dict, messages: list) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    if isinstance(body.get("files"), list):
        files.extend(body["files"])
    for msg in messages:
        if isinstance(msg.get("files"), list):
            files.extend(msg["files"])
        if isinstance(msg.get("attachments"), list):
            files.extend(msg["attachments"])
        if isinstance(msg.get("sources"), list):
            for source_obj in msg["sources"]:
                if isinstance(source_obj, dict):
                    source = source_obj.get("source", {})
                    if source.get("type") == "file" and isinstance(source.get("file"), dict):
                        files.append({"file": source["file"]})
    # Deduplicate by path
    seen = set()
    unique = []
    for f in files:
        path = _get_file_path(f)
        if path and path not in seen:
            seen.add(path)
            unique.append(f)
    return unique


def _file_size_bytes(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def _is_pdf(name: str, mime: str) -> bool:
    return name.lower().endswith(".pdf") or mime == "application/pdf"


def _is_image(mime: str) -> bool:
    return mime.startswith("image/")


def _is_docx(name: str, mime: str) -> bool:
    return name.lower().endswith((".docx",)) or mime in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",)


def _is_csv(name: str, mime: str) -> bool:
    return name.lower().endswith(".csv") or mime in ("text/csv", "application/csv")


def _is_xlsx(name: str, mime: str) -> bool:
    return name.lower().endswith((".xlsx", ".xlsm")) or mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",)


def _is_txt(name: str, mime: str) -> bool:
    return name.lower().endswith((".txt", ".log")) or mime.startswith("text/")


def _is_md(name: str, mime: str) -> bool:
    return name.lower().endswith((".md", ".markdown"))


def _is_tsv(name: str, mime: str) -> bool:
    return name.lower().endswith(".tsv") or mime in ("text/tab-separated-values", "text/tsv")


def _is_json_file(name: str, mime: str) -> bool:
    return name.lower().endswith(".json") or mime in ("application/json", "text/json")


def _extract_docx_text(path: str) -> str:
    try:
        from docx import Document  # type: ignore
    except Exception as e:
        log(f"DOCX import failed: {e}")
        return ""
    try:
        doc = Document(path)
        parts = []
        for para in doc.paragraphs:
            if para.text:
                parts.append(para.text)
            if sum(len(p) for p in parts) > MAX_DOCX_CHARS:
                break
        text = "\n".join(parts)
        if len(text) > MAX_DOCX_CHARS:
            text = text[:MAX_DOCX_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"DOCX parse failed: {e}")
        return ""


def _extract_csv_text(path: str) -> str:
    try:
        rows = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh)
            for i, row in enumerate(reader):
                if i >= MAX_CSV_ROWS:
                    rows.append(["[truncated rows]"])
                    break
                rows.append(row[:MAX_CSV_COLS])
        lines = [", ".join(row) for row in rows]
        return "\n".join(lines).strip()
    except Exception as e:
        log(f"CSV parse failed: {e}")
        return ""


def _extract_xlsx_text(path: str) -> str:
    try:
        import openpyxl  # type: ignore
    except Exception as e:
        log(f"XLSX import failed: {e}")
        return ""
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheet = wb.active
        rows = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= MAX_XLSX_ROWS:
                rows.append(["[truncated rows]"])
                break
            limited = []
            for j, cell in enumerate(row):
                if j >= MAX_XLSX_COLS:
                    limited.append("[truncated cols]")
                    break
                limited.append("" if cell is None else str(cell))
            rows.append(limited)
        lines = ["\t".join(r) for r in rows]
        return "\n".join(lines).strip()
    except Exception as e:
        log(f"XLSX parse failed: {e}")
        return ""


def _extract_text_file(path: str, max_chars: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            data = fh.read(max_chars + 1)
            if len(data) > max_chars:
                data = data[:max_chars] + "\n[truncated]"
            return data.strip()
    except Exception as e:
        log(f"Text parse failed: {e}")
        return ""


def _extract_tsv_text(path: str) -> str:
    try:
        rows = []
        with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.reader(fh, delimiter="\t")
            for i, row in enumerate(reader):
                if i >= MAX_CSV_ROWS:
                    rows.append(["[truncated rows]"])
                    break
                rows.append(row[:MAX_CSV_COLS])
        lines = ["\t".join(row) for row in rows]
        return "\n".join(lines).strip()
    except Exception as e:
        log(f"TSV parse failed: {e}")
        return ""


def _extract_json_text(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_JSON_BYTES + 1)
        truncated = len(data) > MAX_JSON_BYTES
        if truncated:
            data = data[:MAX_JSON_BYTES]
        try:
            obj = json.loads(data.decode("utf-8", errors="ignore"))
            text = json.dumps(obj, indent=2)
        except Exception:
            text = data.decode("utf-8", errors="ignore")
        if truncated or len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"JSON parse failed: {e}")
        return ""


async def _post_with_retry(client: httpx.AsyncClient, url: str, headers: dict, payload: dict, attempts: int = 3, base_delay: float = 1.0, stream: bool = False):
    """
    POST with bounded retry/backoff for transient 429/5xx.
    """
    for attempt in range(1, attempts + 1):
        try:
            if stream:
                return await client.stream(
                    "POST",
                    url,
                    headers=headers,
                    json=payload,
                )
            resp = await client.post(
                url,
                headers=headers,
                json=payload,
            )
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                log(f"Transient error {resp.status_code}, retrying in {delay:.1f}s ({attempt}/{attempts})")
                await asyncio.sleep(delay)
                continue
            return resp
        except httpx.RequestError as e:
            if attempt >= attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log(f"Request error {e}, retrying in {delay:.1f}s ({attempt}/{attempts})")
            await asyncio.sleep(delay)
    raise HTTPException(status_code=502, detail="Upstream retry exhausted")


def _extract_text_from_responses_chunk(data: dict) -> str:
    """
    Pull incremental text from Responses API stream chunk.
    """
    parts = []

    # Top-level delta style: {"delta":{"output":[...]}}
    delta = data.get("delta")
    if isinstance(delta, dict):
        for item in delta.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if not isinstance(c, dict):
                        continue
                    t = c.get("text") or (c.get("delta") or {}).get("text") or (c.get("delta") or {}).get("output_text")
                    if t:
                        parts.append(t)

    # Full output style: {"output":[{"type":"message","content":[...]}]}
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if not isinstance(c, dict):
                    continue
                if c.get("type") in ("output_text", "text"):
                    t = c.get("text")
                    if t:
                        parts.append(t)
                delta_block = c.get("delta") or {}
                if isinstance(delta_block, dict):
                    t = delta_block.get("text") or delta_block.get("output_text")
                    if t:
                        parts.append(t)

    return "".join(parts)


def extract_pdfs_and_clean_text(text: str) -> tuple[str, list[dict]]:
    """
    Extract PDF markers from text and return cleaned text + list of PDFs.
    """
    pdfs = []
    
    for match in PDF_MARKER_RE.finditer(text):
        filename = match.group(1).strip()
        b64_data = match.group(2).strip()
        pdfs.append({
            "filename": filename,
            "base64": b64_data
        })
    
    # Remove markers from text
    cleaned = PDF_MARKER_RE.sub("", text).strip()
    return cleaned, pdfs


def extract_text_from_content(content) -> str:
    """Extract text from message content (string or list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # Keep image URLs as-is for now
                    pass
        return "\n".join(parts)
    return str(content) if content else ""


def _load_files_from_request(body: dict, messages: list) -> tuple[list[dict], list[dict], list[str]]:
    """
    Extract real uploaded files (PDFs, images, and doc text) into lists for Responses API.
    Returns (pdfs, images, texts). Images returned as data URLs for input_image.
    """
    files = _extract_all_files(body, messages)
    if not files:
        return [], [], []

    max_file_bytes = MAX_FILE_MB * 1024 * 1024
    max_total_bytes = MAX_TOTAL_MB * 1024 * 1024
    total_bytes = 0

    pdfs: List[dict] = []
    images: List[dict] = []
    texts: List[str] = []

    for f in files:
        path = _get_file_path(f)
        name = _get_file_name(f) or os.path.basename(path)
        if not path or not os.path.exists(path):
            raise HTTPException(status_code=400, detail=f"File not found: {name or path}")

        size = _file_size_bytes(path)
        if size < 0:
            raise HTTPException(status_code=400, detail=f"Cannot read file size: {name}")
        if size > max_file_bytes:
            raise HTTPException(status_code=400, detail=f"File too large (> {MAX_FILE_MB} MB): {name}")
        if total_bytes + size > max_total_bytes:
            raise HTTPException(status_code=400, detail=f"Total upload size exceeds {MAX_TOTAL_MB} MB limit")

        mime, _ = mimetypes.guess_type(name)
        mime = mime or "application/octet-stream"

        if _is_pdf(name, mime):
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("utf-8")
            pdfs.append({"filename": name or "document.pdf", "base64": b64})
            total_bytes += size
            continue

        if _is_image(mime):
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode("utf-8")
            images.append({"url": f"data:{mime};base64,{b64}"})
            total_bytes += size
            continue

        # Text-first ingestion for DOCX/CSV/XLSX
        text_block = ""
        if _is_docx(name, mime):
            text_block = _extract_docx_text(path)
        elif _is_csv(name, mime):
            text_block = _extract_csv_text(path)
        elif _is_xlsx(name, mime):
            text_block = _extract_xlsx_text(path)
        elif _is_tsv(name, mime):
            text_block = _extract_tsv_text(path)
        elif _is_md(name, mime) or _is_txt(name, mime):
            text_block = _extract_text_file(path, MAX_TEXT_CHARS)
        elif _is_json_file(name, mime):
            text_block = _extract_json_text(path)

        if text_block:
            texts.append(f"=== File: {name} ===\n{text_block}")
            total_bytes += size
            continue

        # Non-supported types: skip silently but keep base functionality intact
        log(f"Skipping unsupported file type: {name} ({mime})")

    return pdfs, images, texts


async def call_responses_api(model: str, user_text: str, pdfs: list[dict], images: list[dict] = None, texts: list[str] = None) -> dict:
    """
    Call OpenAI Responses API with PDF files and/or images.
    """
    content_items = []
    
    # Add PDF files first (using data URL format)
    for pdf in pdfs:
        content_items.append({
            "type": "input_file",
            "filename": pdf["filename"],
            "file_data": f"data:application/pdf;base64,{pdf['base64']}",
        })
        log(f"Adding PDF: {pdf['filename']}")
    
    # Add images if any
    if images:
        for img in images:
            content_items.append({
                "type": "input_image",
                "image_url": img.get("url", ""),
            })

    # Add extracted text blocks (DOCX/CSV/XLSX)
    if texts:
        for t in texts:
            if t:
                content_items.append({
                    "type": "input_text",
                    "text": t
                })
    
    # Add user text
    if user_text:
        content_items.append({
            "type": "input_text",
            "text": user_text
        })
    else:
        content_items.append({
            "type": "input_text",
            "text": "Analyze the attached document(s). Extract all visible content including text, tables, charts, diagrams, chemical structures, and spectra. For any spectra (NMR, HPLC, MS), read peak values if legible."
        })
    
    payload = {
        "model": model,
        "input": [{
            "role": "user",
            "content": content_items
        }]
    }
    
    log(f"Calling Responses API with model: {model}")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await _post_with_retry(
            client,
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        
        if resp.status_code >= 400:
            log(f"Responses API error: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        
        return resp.json()


async def stream_responses_api(model: str, user_text: str, pdfs: list[dict], images: list[dict] = None, texts: list[str] = None):
    """
    Stream OpenAI Responses API SSE and convert to chat-completion chunks.
    """
    content_items = []
    
    for pdf in pdfs:
        content_items.append({
            "type": "input_file",
            "filename": pdf["filename"],
            "file_data": f"data:application/pdf;base64,{pdf['base64']}",
        })
        log(f"Adding PDF: {pdf['filename']}")
    
    if images:
        for img in images:
            content_items.append({
                "type": "input_image",
                "image_url": img.get("url", ""),
            })

    if texts:
        for t in texts:
            if t:
                content_items.append({
                    "type": "input_text",
                    "text": t
                })
    
    if user_text:
        content_items.append({
            "type": "input_text",
            "text": user_text
        })
    else:
        content_items.append({
            "type": "input_text",
            "text": "Analyze the attached document(s). Extract all visible content including text, tables, charts, diagrams, chemical structures, and spectra. For any spectra (NMR, HPLC, MS), read peak values if legible."
        })
    
    payload = {
        "model": model,
        "input": [{
            "role": "user",
            "content": content_items
        }],
        "stream": True,
    }

    url = f"{OPENAI_BASE_URL}/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    attempts = 3
    base_delay = 1.0

    for attempt in range(1, attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with await _post_with_retry(client, url, headers, payload, attempts=1, stream=True) as resp:
                    if resp.status_code >= 400:
                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                            delay = base_delay * (2 ** (attempt - 1))
                            log(f"Responses stream error {resp.status_code}, retrying in {delay:.1f}s ({attempt}/{attempts})")
                            await asyncio.sleep(delay)
                            continue
                        text = await resp.aread()
                        raise HTTPException(status_code=resp.status_code, detail=text.decode() if hasattr(text, "decode") else str(text))

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data = line[len("data:"):].strip()
                            if data == "[DONE]":
                                yield "data: [DONE]\n\n"
                                return
                            try:
                                parsed = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            chunk_text = _extract_text_from_responses_chunk(parsed)
                            if not chunk_text:
                                continue
                            chunk = {
                                "id": parsed.get("id", "resp_proxy"),
                                "object": "chat.completion.chunk",
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": chunk_text},
                                    "finish_reason": None
                                }]
                            }
                            yield f"data: {json.dumps(chunk)}\n\n"
                    # If stream completed without [DONE], send a terminator
                    yield "data: [DONE]\n\n"
                    return
        except Exception as e:
            if attempt >= attempts:
                log(f"Responses stream failed: {e}")
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log(f"Responses stream exception {e}, retrying in {delay:.1f}s ({attempt}/{attempts})")
            await asyncio.sleep(delay)



async def call_chat_completions(body: dict) -> dict:
    """
    Forward to standard Chat Completions API (fallback when no PDFs).
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body
        )
        
        if resp.status_code >= 400:
            log(f"Chat Completions error: {resp.status_code}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        
        return resp.json()


def responses_to_chat_completion(resp_data: dict, model: str) -> dict:
    """
    Convert Responses API output to Chat Completions format for OpenWebUI.
    """
    output_text = ""
    
    for item in resp_data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    output_text += c.get("text", "")
    
    return {
        "id": resp_data.get("id", "resp_proxy"),
        "object": "chat.completion",
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": output_text.strip() or "(No output from model)"
            },
            "finish_reason": "stop"
        }],
        "usage": resp_data.get("usage", {})
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Main endpoint - intercepts Chat Completions, upgrades to Responses API if PDFs found.
    """
    body = await request.json()
    
    model = body.get("model", "gpt-4o")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    
    log(f"Received request for model: {model}, messages: {len(messages)}, stream: {stream}")
    
    # Collect all text and find PDF markers
    all_text = ""
    marker_pdfs = []
    marker_images = []
    upload_pdfs = []
    upload_images = []
    upload_texts = []
    
    for msg in messages:
        if msg.get("role") != "user":
            continue
        
        content = msg.get("content")
        text = extract_text_from_content(content)
        
        # Extract PDFs from text
        cleaned_text, pdfs = extract_pdfs_and_clean_text(text)
        all_text += cleaned_text + "\n"
        marker_pdfs.extend(pdfs)
        
        # Also check for existing image_url items
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    img_url = item.get("image_url", {})
                    if isinstance(img_url, dict):
                        marker_images.append({"url": img_url.get("url", "")})
                    elif isinstance(img_url, str):
                        marker_images.append({"url": img_url})
    
    all_text = all_text.strip()

    # Load real uploaded files (PDF/images/text) from body/messages
    try:
        upload_pdfs, upload_images, upload_texts = _load_files_from_request(body, messages)
    except HTTPException as e:
        # User-facing error for size/not-found issues
        raise e
    except Exception as e:
        log(f"File load failed: {e}")
        upload_pdfs, upload_images, upload_texts = [], [], []

    all_pdfs = marker_pdfs + upload_pdfs
    all_images = marker_images + upload_images
    all_text_blocks = upload_texts
    
    log(f"Found {len(all_pdfs)} PDF(s), {len(all_images)} image(s), {len(all_text_blocks)} text block(s) (markers+uploads)")
    
    # If we have PDFs/images/text blocks, use Responses API
    if all_pdfs or all_images or all_text_blocks:
        log("Using Responses API for document/image/text analysis")
        try:
            if stream:
                async def proxied_stream():
                    async for event in stream_responses_api(model, all_text, all_pdfs, all_images, all_text_blocks):
                        yield event

                return StreamingResponse(proxied_stream(), media_type="text/event-stream")

            resp_data = await call_responses_api(model, all_text, all_pdfs, all_images, all_text_blocks)
            result = responses_to_chat_completion(resp_data, model)
            return JSONResponse(content=result)
            
        except Exception as e:
            log(f"Responses API failed: {e}")
            # Fall back to chat completions
            pass
    
    # No docs/images or Responses API failed - use standard Chat Completions
    log("Using standard Chat Completions API")
    
    # Clean PDF markers from messages before forwarding
    cleaned_messages = []
    for msg in messages:
        new_msg = msg.copy()
        content = msg.get("content")
        if isinstance(content, str):
            cleaned, _ = extract_pdfs_and_clean_text(content)
            new_msg["content"] = cleaned
        cleaned_messages.append(new_msg)
    
    body["messages"] = cleaned_messages
    
    if stream:
        # Stream from Chat Completions
        async def stream_response():
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{OPENAI_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=body
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        
        return StreamingResponse(stream_response(), media_type="text/event-stream")
    
    result = await call_chat_completions(body)
    return JSONResponse(content=result)


@app.get("/v1/models")
async def list_models():
    """Forward models list request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{OPENAI_BASE_URL}/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
        )
        return JSONResponse(content=resp.json())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "OpenAI Responses Proxy", "status": "running"}
