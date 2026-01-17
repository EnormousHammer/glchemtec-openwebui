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
import httpx
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio

app = FastAPI(title="OpenAI Responses Proxy")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
DEBUG = os.environ.get("PROXY_DEBUG", "true").lower() == "true"

# Regex to find PDF markers: [__PDF_FILE_B64__ filename=xxx.pdf]base64data[/__PDF_FILE_B64__]
PDF_MARKER_RE = re.compile(
    r"\[__PDF_FILE_B64__ filename=([^\]]+)\]([A-Za-z0-9+/=]+)\[/__PDF_FILE_B64__\]",
    re.DOTALL
)


def log(msg: str):
    if DEBUG:
        print(f"[PROXY] {msg}")


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


async def call_responses_api(model: str, user_text: str, pdfs: list[dict], images: list[dict] = None) -> dict:
    """
    Call OpenAI Responses API with PDF files and/or images.
    """
    content_items = []
    
    # Add PDF files first
    for pdf in pdfs:
        content_items.append({
            "type": "input_file",
            "filename": pdf["filename"],
            "file_data": pdf["base64"],
        })
        log(f"Adding PDF: {pdf['filename']}")
    
    # Add images if any
    if images:
        for img in images:
            content_items.append({
                "type": "input_image",
                "image_url": img.get("url", ""),
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
        resp = await client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload
        )
        
        if resp.status_code >= 400:
            log(f"Responses API error: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        
        return resp.json()


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
    all_pdfs = []
    all_images = []
    
    for msg in messages:
        if msg.get("role") != "user":
            continue
        
        content = msg.get("content")
        text = extract_text_from_content(content)
        
        # Extract PDFs from text
        cleaned_text, pdfs = extract_pdfs_and_clean_text(text)
        all_text += cleaned_text + "\n"
        all_pdfs.extend(pdfs)
        
        # Also check for existing image_url items
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    img_url = item.get("image_url", {})
                    if isinstance(img_url, dict):
                        all_images.append({"url": img_url.get("url", "")})
                    elif isinstance(img_url, str):
                        all_images.append({"url": img_url})
    
    all_text = all_text.strip()
    
    log(f"Found {len(all_pdfs)} PDF(s), {len(all_images)} image(s)")
    
    # If we have PDFs, use Responses API
    if all_pdfs:
        log("Using Responses API for PDF analysis")
        try:
            resp_data = await call_responses_api(model, all_text, all_pdfs, all_images)
            result = responses_to_chat_completion(resp_data, model)
            
            if stream:
                # Fake streaming for compatibility
                async def fake_stream():
                    content = result["choices"][0]["message"]["content"]
                    chunk = {
                        "id": result["id"],
                        "object": "chat.completion.chunk",
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": content},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(fake_stream(), media_type="text/event-stream")
            
            return JSONResponse(content=result)
            
        except Exception as e:
            log(f"Responses API failed: {e}")
            # Fall back to chat completions
            pass
    
    # No PDFs or Responses API failed - use standard Chat Completions
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
