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
import io
import uuid
import math
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import quote_plus
from fastapi import FastAPI, Request, HTTPException  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse  # type: ignore
import asyncio
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage  # type: ignore
from reportlab.lib.pagesizes import letter  # type: ignore
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore
from reportlab.lib import colors  # type: ignore
from docx import Document  # type: ignore
from docx.shared import Pt  # type: ignore
from openpyxl import load_workbook  # type: ignore

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
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_ZIP_FILES = 500
MAX_JCAMP_BYTES = 2 * 1024 * 1024

# Simple in-memory metrics (non-persistent)
METRICS = {
    "requests_total": 0,
    "responses_api_calls": 0,
    "chat_completions_calls": 0,
    "errors_total": 0,
    "last_error": "",
    "last_latency_ms": 0.0,
}

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


def _is_doc(name: str, mime: str) -> bool:
    return name.lower().endswith(".doc") or mime in ("application/msword",)


def _is_xls(name: str, mime: str) -> bool:
    return name.lower().endswith(".xls") or mime in ("application/vnd.ms-excel",)


def _is_odt(name: str, mime: str) -> bool:
    return name.lower().endswith(".odt") or mime in ("application/vnd.oasis.opendocument.text",)


def _is_rtf(name: str, mime: str) -> bool:
    return name.lower().endswith(".rtf") or mime in ("application/rtf", "text/rtf")


def _is_bruker_zip(name: str, mime: str) -> bool:
    return name.lower().endswith(".zip") and ("application/zip" in mime or "zip" in mime)


def _is_jcamp(name: str, mime: str) -> bool:
    return name.lower().endswith((".jdx", ".dx", ".jcamp")) or ("jcamp" in mime.lower() if mime else False)


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


def _extract_doc_text(path: str) -> str:
    """
    Best-effort DOC extraction: try to use textract if available; otherwise return empty.
    """
    try:
        import textract  # type: ignore
    except Exception:
        log("DOC parse skipped: textract not available")
        return ""
    try:
        text = textract.process(path).decode("utf-8", errors="ignore")
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"DOC parse failed: {e}")
        return ""


def _extract_xls_text(path: str) -> str:
    """
    Best-effort XLS extraction via xlrd if available.
    """
    try:
        import xlrd  # type: ignore
    except Exception:
        log("XLS parse skipped: xlrd not available")
        return ""
    try:
        book = xlrd.open_workbook(path, on_demand=True)
        sheet = book.sheet_by_index(0)
        lines = []
        for r in range(min(sheet.nrows, MAX_XLSX_ROWS)):
            row_vals = []
            for c in range(min(sheet.ncols, MAX_XLSX_COLS)):
                val = sheet.cell_value(r, c)
                row_vals.append("" if val is None else str(val))
            lines.append("\t".join(row_vals))
        text = "\n".join(lines)
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"XLS parse failed: {e}")
        return ""


def _extract_odt_text(path: str) -> str:
    try:
        from odf.opendocument import load  # type: ignore
        from odf import text as odf_text  # type: ignore
    except Exception:
        log("ODT parse skipped: odfpy not available")
        return ""
    try:
        doc = load(path)
        paras = []
        for p in doc.getElementsByType(odf_text.P):
            txt = "".join(t.data for t in p.childNodes if hasattr(t, "data"))
            if txt:
                paras.append(txt)
            if sum(len(x) for x in paras) > MAX_TEXT_CHARS:
                break
        text = "\n".join(paras)
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"ODT parse failed: {e}")
        return ""


def _extract_rtf_text(path: str) -> str:
    try:
        from striprtf.striprtf import rtf_to_text  # type: ignore
    except Exception:
        log("RTF parse skipped: striprtf not available")
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            data = fh.read()
        text = rtf_to_text(data)
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS] + "\n[truncated]"
        return text.strip()
    except Exception as e:
        log(f"RTF parse failed: {e}")
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


def _extract_bruker_zip(path: str) -> str:
    """
    Parse Bruker NMR zip for key metadata. Metadata-only (no peak picking).
    """
    import zipfile
    try:
        if os.path.getsize(path) > MAX_ZIP_BYTES:
            raise HTTPException(status_code=400, detail=f"Zip too large (> {MAX_ZIP_BYTES/1024/1024:.0f} MB)")
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            if len(namelist) > MAX_ZIP_FILES:
                raise HTTPException(status_code=400, detail="Zip has too many entries")

            # Detect Bruker structure
            lower_names = [n.lower() for n in namelist]
            if not any("acqus" in n for n in lower_names):
                return ""

            def read_text_member(name):
                try:
                    with zf.open(name, "r") as fh:
                        return fh.read().decode("utf-8", errors="ignore")
                except Exception:
                    return ""

            meta_sections = []

            acqus_files = [n for n in namelist if n.lower().endswith("acqus")]
            procs_files = [n for n in namelist if n.lower().endswith("procs")]
            title_files = [n for n in namelist if n.lower().endswith("title")]

            def parse_param(block, keys):
                lines = block.splitlines()
                out = []
                for key in keys:
                    for line in lines:
                        if line.strip().startswith(f"##${key}="):
                            out.append(f"{key}: {line.split('=',1)[1].strip()}")
                            break
                return out

            if acqus_files:
                data = read_text_member(acqus_files[0])
                vals = parse_param(data, ["SW", "TD", "O1", "SFO1", "NUC1", "TE", "RG", "D", "NS", "DATE"])
                if vals:
                    meta_sections.append("ACQUS:\n" + "\n".join(vals))

            if procs_files:
                data = read_text_member(procs_files[0])
                vals = parse_param(data, ["SF", "SI", "SSB", "LB", "WDW"])
                if vals:
                    meta_sections.append("PROCS:\n" + "\n".join(vals))

            if title_files:
                data = read_text_member(title_files[0])
                if data.strip():
                    meta_sections.append("TITLE:\n" + data.strip())

            if not meta_sections:
                return ""

            return "\n\n".join(meta_sections)
    except HTTPException:
        raise
    except Exception as e:
        log(f"Bruker zip parse failed: {e}")
        return ""


def _extract_jcamp_text(path: str) -> str:
    """
    Simple JCAMP-DX peak/metadata extraction (no external deps).
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_JCAMP_BYTES + 1)
        truncated = len(raw) > MAX_JCAMP_BYTES
        data = raw[:MAX_JCAMP_BYTES].decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"JCAMP read failed: {e}")
        return ""

    lines = data.splitlines()
    meta = {}
    for ln in lines[:200]:  # scan headers
        l = ln.strip()
        if not l.startswith("##"):
            continue
        if "=" in l:
            key, val = l[2:].split("=", 1)
            meta[key.strip().upper()] = val.strip()

    title = meta.get("TITLE", "")
    nucleus = meta.get(".OBSERVENUCLEUS") or meta.get("NUCLEUS") or meta.get(".NUCLEUS") or ""
    solvent = meta.get(".SOLVENT") or meta.get("SOLVENT") or meta.get("$SOLVENT") or ""
    freq = meta.get(".OBSERVEFREQUENCY") or meta.get("OBSERVE FREQUENCY") or meta.get("$SFO1") or ""
    temp = meta.get(".TEMPERATURE") or meta.get("TEMP") or meta.get("$TE") or ""

    # Extract peak table
    peak_section = ""
    if "##PEAKTABLE=" in data:
        try:
            start = data.index("##PEAKTABLE=")
            rest = data[start:].split("##", 2)
            if len(rest) >= 2:
                peak_section = rest[1]  # after PEAKTABLE tag until next ##
            else:
                peak_section = rest[0]
        except ValueError:
            pass
    peaks = []
    if peak_section:
        for ln in peak_section.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("##"):
                continue
            # Expect "shift, intensity" pairs
            parts = [p.strip() for p in ln.replace(";", ",").split(",") if p.strip()]
            if len(parts) >= 1:
                try:
                    shift = float(parts[0])
                    intensity = float(parts[1]) if len(parts) > 1 else 1.0
                    peaks.append(f"{shift:.2f} s 1H (int {intensity:.0f})")
                except Exception:
                    continue

    body = []
    if title:
        body.append(f"Title: {title}")
    if nucleus:
        body.append(f"Nucleus: {nucleus}")
    if solvent:
        body.append(f"Solvent: {solvent}")
    if freq:
        body.append(f"Freq: {freq} MHz")
    if temp:
        body.append(f"Temp: {temp}")
    if peaks:
        body.append("Peaks:")
        body.extend(peaks[:200])
    elif truncated:
        body.append("[JCAMP truncated; no peaks found]")

    return "\n".join(body).strip()


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
            images.append({"url": f"data:{mime};base64,{b64}", "name": name})
            total_bytes += size
            continue

        # Text-first ingestion for DOCX/CSV/XLSX/others
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
        elif _is_doc(name, mime):
            text_block = _extract_doc_text(path)
        elif _is_xls(name, mime):
            text_block = _extract_xls_text(path)
        elif _is_odt(name, mime):
            text_block = _extract_odt_text(path)
        elif _is_rtf(name, mime):
            text_block = _extract_rtf_text(path)
        elif _is_bruker_zip(name, mime):
            text_block = _extract_bruker_zip(path)
        elif _is_jcamp(name, mime):
            text_block = _extract_jcamp_text(path)

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
    _content_filter(user_text or "")
    METRICS["responses_api_calls"] += 1
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
            attempts=3,
            base_delay=1.0,
            stream=False,
        )
        if resp.status_code >= 400:
            log(f"Responses API error: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def stream_responses_api(model: str, user_text: str, pdfs: list[dict], images: list[dict] = None, texts: list[str] = None):
    """
    Stream OpenAI Responses API SSE and convert to chat-completion chunks.
    """
    _content_filter(user_text or "")
    METRICS["responses_api_calls"] += 1
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
        resp = await _post_with_retry(
            client,
            f"{OPENAI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            payload=body,
            attempts=3,
            base_delay=1.0,
            stream=False,
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
    start = time.perf_counter()
    METRICS["requests_total"] += 1
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

    # If any images are present, add conditional NMR instructions for the model
    nmr_image = bool(upload_images or marker_images)
    augmented_text = all_text
    if nmr_image:
        nmr_prompt = (
            "\n\n[INSTRUCTION FOR NMR IMAGES]\n"
            "- If any attached image is an NMR spectrum, extract a peak table: δ (ppm), multiplicity, integration, J (Hz) if visible, assignment if clear.\n"
            "- Then generate an ACS-style summary (Journal of Organic Chemistry style) with proper nuclei symbols and δ notation.\n"
            "- State nucleus (¹H or ¹³C) inferred from axis/labels; if unclear, note the uncertainty.\n"
            "- If image is not an NMR spectrum, say it is not an NMR spectrum.\n"
        )
        augmented_text = (all_text + nmr_prompt).strip()
    
    # If we have PDFs/images/text blocks, use Responses API
    if all_pdfs or all_images or all_text_blocks:
        log("Using Responses API for document/image/text analysis")
        try:
            if stream:
                async def proxied_stream():
                    async for event in stream_responses_api(model, augmented_text, all_pdfs, all_images, all_text_blocks):
                        yield event

                return StreamingResponse(proxied_stream(), media_type="text/event-stream")

            resp_data = await call_responses_api(model, augmented_text, all_pdfs, all_images, all_text_blocks)
            result = responses_to_chat_completion(resp_data, model)
            return JSONResponse(content=result)
            
        except Exception as e:
            METRICS["errors_total"] += 1
            METRICS["last_error"] = str(e)
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
    
    try:
        result = await call_chat_completions(body)
    except Exception as e:
        METRICS["errors_total"] += 1
        METRICS["last_error"] = str(e)
        raise
    latency_ms = (time.perf_counter() - start) * 1000
    METRICS["last_latency_ms"] = latency_ms
    return JSONResponse(content=result)


def _safe_slug(text: str, default: str = "report") -> str:
    """Create a simple filename-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", text).strip("-")
    return slug or default

def _is_enabled(env_key: str, default: bool = True) -> bool:
    return os.environ.get(env_key, "true" if default else "false").lower() == "true"


def _content_filter(text: str) -> None:
    """Basic content filter hook."""
    banned = ["password", "apikey", "secret", "token", "private key"]
    lower = text.lower()
    if any(b in lower for b in banned):
        raise HTTPException(status_code=400, detail="Content blocked by filter")


async def _post_with_retry(client: httpx.AsyncClient, url: str, headers: dict, payload: dict, attempts: int = 3, base_delay: float = 1.0, stream: bool = False):
    for i in range(attempts):
        try:
            if stream:
                resp = await client.stream("POST", url, headers=headers, json=payload)
            else:
                resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code in (429, 500, 502, 503, 504) and i < attempts - 1:
                await asyncio.sleep(base_delay * (2 ** i))
                continue
            resp.raise_for_status()
            return resp
        except Exception:
            if i == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** i))


def render_report_pdf(report: dict) -> bytes:
    """
    Render a simple, professional PDF report.
    Expected keys: title, subtitle, author, date, sections [{heading, body, bullets, table{headers, rows}, images[{url,data_url,caption}]}], footer.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    flow = []

    title = report.get("title") or "Report"
    subtitle = report.get("subtitle", "")
    author = report.get("author", "")
    date = report.get("date", "")
    footer = report.get("footer", "")
    sections = report.get("sections", [])

    flow.append(Paragraph(title, styles["Title"]))
    if subtitle:
        flow.append(Paragraph(subtitle, styles["Heading3"]))
    if author or date:
        meta = " | ".join([x for x in [author, date] if x])
        if meta:
            flow.append(Paragraph(meta, styles["Normal"]))
    flow.append(Spacer(1, 12))

    for sec in sections:
        heading = sec.get("heading", "")
        body = sec.get("body", "")
        bullets = sec.get("bullets", [])
        table = sec.get("table")
        images = sec.get("images", [])

        if heading:
            flow.append(Paragraph(heading, styles["Heading2"]))
        if body:
            flow.append(Paragraph(body.replace("\n", "<br/>"), styles["Normal"]))
        if bullets and isinstance(bullets, list):
            for b in bullets:
                flow.append(Paragraph(f"• {b}", styles["Normal"]))
        if table and isinstance(table, dict):
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            data = []
            if headers:
                data.append(headers)
            data.extend(rows)
            if data:
                t = Table(data, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1d2b3a")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                flow.append(Spacer(1, 6))
                flow.append(t)
        if images and isinstance(images, list):
            for img in images[:5]:  # limit
                src = img.get("data_url") or img.get("url") or ""
                caption = img.get("caption", "")
                img_bytes = None
                if src.startswith("data:"):
                    try:
                        b64data = src.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64data)
                    except Exception:
                        img_bytes = None
                elif os.path.exists(src):
                    with open(src, "rb") as f:
                        img_bytes = f.read()
                if img_bytes:
                    tmp = io.BytesIO(img_bytes)
                    try:
                        flow.append(RLImage(tmp, width=400, preserveAspectRatio=True))
                        if caption:
                            flow.append(Paragraph(caption, styles["Italic"]))
                    except Exception:
                        pass
        flow.append(Spacer(1, 12))

    if footer:
        flow.append(Spacer(1, 24))
        flow.append(Paragraph(footer, styles["Normal"]))

    doc.build(flow)
    return buffer.getvalue()


def render_report_docx(report: dict) -> bytes:
    """Render a DOCX report with similar structure."""
    doc = Document()
    title = report.get("title") or "Report"
    subtitle = report.get("subtitle", "")
    author = report.get("author", "")
    date = report.get("date", "")
    sections = report.get("sections", [])
    footer = report.get("footer", "")

    doc.add_heading(title, level=1)
    if subtitle:
        doc.add_paragraph(subtitle)
    meta = " | ".join([x for x in [author, date] if x])
    if meta:
        doc.add_paragraph(meta)
    doc.add_paragraph("")

    for sec in sections:
        heading = sec.get("heading", "")
        body = sec.get("body", "")
        bullets = sec.get("bullets", [])
        table = sec.get("table")
        images = sec.get("images", [])

        if heading:
            doc.add_heading(heading, level=2)
        if body:
            doc.add_paragraph(body)
        if bullets and isinstance(bullets, list):
            for b in bullets:
                para = doc.add_paragraph(style="List Bullet")
                para.add_run(str(b))
        if table and isinstance(table, dict):
            headers = table.get("headers", [])
            rows = table.get("rows", [])
            if headers or rows:
                cols = len(headers) if headers else len(rows[0])
                t = doc.add_table(rows=1, cols=cols)
                hdr_cells = t.rows[0].cells
                for i, h in enumerate(headers):
                    hdr_cells[i].text = str(h)
                for row in rows:
                    cells = t.add_row().cells
                    for i, val in enumerate(row):
                        cells[i].text = str(val)
        if images and isinstance(images, list):
            for img in images[:5]:
                src = img.get("data_url") or img.get("url") or ""
                caption = img.get("caption", "")
                img_bytes = None
                if src.startswith("data:"):
                    try:
                        b64data = src.split(",", 1)[1]
                        img_bytes = base64.b64decode(b64data)
                    except Exception:
                        img_bytes = None
                elif os.path.exists(src):
                    with open(src, "rb") as f:
                        img_bytes = f.read()
                if img_bytes:
                    tmp = io.BytesIO(img_bytes)
                    try:
                        doc.add_picture(tmp, width=None)
                        if caption:
                            doc.add_paragraph(caption).italic = True
                    except Exception:
                        pass
        doc.add_paragraph("")

    if footer:
        doc.add_paragraph(footer)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def summarize_csv_tsv(text: str, delimiter: str = ",", max_rows: int = 1000, max_cols: int = 50) -> dict:
    rows = []
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        if len(row) > max_cols:
            row = row[:max_cols]
        rows.append(row)
    if not rows:
        return {"rows": 0, "cols": 0, "headers": [], "sample": []}
    headers = rows[0]
    data_rows = rows[1:]
    sample = data_rows[:5]
    return {
        "rows": len(rows) - 1,
        "cols": len(headers),
        "headers": headers,
        "sample": sample,
    }


def summarize_xlsx(content: bytes, max_rows: int = 1000, max_cols: int = 50) -> dict:
    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    sheet = wb.active
    headers = []
    data = []
    for r_idx, row in enumerate(sheet.iter_rows(max_row=max_rows, max_col=max_cols, values_only=True)):
        vals = ["" if v is None else v for v in row]
        if r_idx == 0:
            headers = vals
        else:
            data.append(vals)
        if len(data) >= max_rows:
            break
    return {
        "rows": len(data),
        "cols": len(headers),
        "headers": headers,
        "sample": data[:5],
    }


def summarize_json(content: bytes, max_bytes: int = 1_000_000) -> dict:
    if len(content) > max_bytes:
        raise ValueError("JSON too large")
    obj = json.loads(content)
    def safe_repr(o, max_len=200):
        s = repr(o)
        return s if len(s) <= max_len else s[:max_len] + "..."
    summary = {
        "type": type(obj).__name__,
    }
    if isinstance(obj, dict):
        keys = list(obj.keys())
        summary["keys"] = keys[:50]
        summary["len"] = len(obj)
    elif isinstance(obj, list):
        summary["len"] = len(obj)
        if obj and isinstance(obj[0], dict):
            keys = set()
            for item in obj[:20]:
                if isinstance(item, dict):
                    keys.update(item.keys())
            summary["keys"] = list(keys)[:50]
        summary["sample"] = safe_repr(obj[:3])
    else:
        summary["value"] = safe_repr(obj)
    return summary


def analyze_file_payload(payload: dict) -> dict:
    """
    Analyze a file payload with base64 content.
    Expected keys: filename, content_base64, content_type?
    Supports CSV/TSV/XLSX/JSON (lightweight summary).
    """
    filename = payload.get("filename", "")
    b64 = payload.get("content_base64", "")
    ctype = payload.get("content_type", "")
    if not filename or not b64:
        raise HTTPException(status_code=400, detail="filename and content_base64 are required")
    try:
        raw = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")

    max_bytes = 5 * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    name_lower = filename.lower()
    if name_lower.endswith(".csv"):
        text = raw.decode("utf-8", errors="replace")
        summary = summarize_csv_tsv(text, delimiter=",")
        return {"kind": "csv", "summary": summary}
    if name_lower.endswith(".tsv"):
        text = raw.decode("utf-8", errors="replace")
        summary = summarize_csv_tsv(text, delimiter="\\t")
        return {"kind": "tsv", "summary": summary}
    if name_lower.endswith(".xlsx"):
        summary = summarize_xlsx(raw)
        return {"kind": "xlsx", "summary": summary}
    if name_lower.endswith(".json") or "json" in ctype:
        summary = summarize_json(raw)
        return {"kind": "json", "summary": summary}

    raise HTTPException(status_code=400, detail="Unsupported file type for analysis")


def _decode_data_url(data_url: str) -> bytes:
    if not data_url.startswith("data:"):
        raise ValueError("Not a data URL")
    try:
        b64data = data_url.split(",", 1)[1]
        return base64.b64decode(b64data)
    except Exception as e:
        raise ValueError(f"Invalid data URL: {e}")


def _prepare_audio_bytes(payload: dict, max_bytes: int = 5 * 1024 * 1024) -> bytes:
    """
    Accepts either content_base64 or data_url in payload["audio"].
    """
    audio = payload.get("audio") or {}
    b64 = audio.get("content_base64", "")
    data_url = audio.get("data_url", "")
    raw = b""
    if b64:
        try:
            raw = base64.b64decode(b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid audio base64")
    elif data_url:
        try:
            raw = _decode_data_url(data_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="audio.content_base64 or audio.data_url is required")

    if len(raw) > max_bytes:
        raise HTTPException(status_code=400, detail="Audio too large (max 5MB)")
    return raw


async def openai_transcribe_audio(raw: bytes, filename: str = "audio.wav", model: str = "whisper-1") -> str:
    files = {"file": (filename, raw, "audio/wav")}
    data = {"model": model}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OPENAI_BASE_URL}/audio/transcriptions", headers=headers, files=files, data=data)
            resp.raise_for_status()
            return resp.json().get("text", "")
    except Exception as e:
        log(f"Transcription failed: {e}")
        raise HTTPException(status_code=502, detail="Transcription failed")


async def openai_tts(text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    payload = {"model": model, "voice": voice, "input": text}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OPENAI_BASE_URL}/audio/speech", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        log(f"TTS failed: {e}")
        raise HTTPException(status_code=502, detail="TTS failed")



@app.post("/v1/report/pdf")
async def generate_report_pdf(report: dict):
    """Generate a PDF report from structured JSON."""
    try:
        pdf_bytes = render_report_pdf(report)
    except Exception as e:
        log(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")

    filename = _safe_slug(report.get("title", "report")) + ".pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/v1/report/docx")
async def generate_report_docx(report: dict):
    """Generate a DOCX report from structured JSON."""
    try:
        docx_bytes = render_report_docx(report)
    except Exception as e:
        log(f"DOCX generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"DOCX generation failed: {e}")

    filename = _safe_slug(report.get("title", "report")) + ".docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/v1/tools/analyze-file")
async def analyze_file_tool(payload: dict):
    if not _is_enabled("ENABLE_ANALYZE_TOOL", default=True):
        raise HTTPException(status_code=403, detail="Analyze tool disabled")
    report = analyze_file_payload(payload)
    return JSONResponse(content=report)


@app.post("/v1/tools/search")
async def search_tool(payload: dict):
    if not _is_enabled("ENABLE_SEARCH_TOOL", default=True):
        raise HTTPException(status_code=403, detail="Search tool disabled")
    query = (payload.get("query") or "").strip()
    if not query or len(query) > 200:
        raise HTTPException(status_code=400, detail="Invalid query")
    banned = ["password", "secret", "token", "apikey"]
    if any(word in query.lower() for word in banned):
        raise HTTPException(status_code=400, detail="Query not allowed")

    url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"User-Agent": "glchemtec-search"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        log(f"Search failed: {e}")
        raise HTTPException(status_code=502, detail="Search failed")

    results = []
    topics = data.get("RelatedTopics", []) or []
    results_raw = data.get("Results", []) or []
    for item in results_raw:
        t = item.get("Text")
        u = item.get("FirstURL")
        if t and u:
            results.append({"title": t, "url": u})
    for item in topics:
        if isinstance(item, dict):
            t = item.get("Text")
            u = item.get("FirstURL")
            if t and u:
                results.append({"title": t, "url": u})
        if len(results) >= 5:
            break

    return JSONResponse(content={"query": query, "results": results[:5]})


@app.post("/v1/tools/transcribe")
async def transcribe_tool(payload: dict):
    if not _is_enabled("ENABLE_AUDIO_TOOLS", default=True):
        raise HTTPException(status_code=403, detail="Audio tools disabled")
    text = await openai_transcribe_audio(_prepare_audio_bytes(payload))
    return JSONResponse(content={"text": text})


@app.post("/v1/tools/tts")
async def tts_tool(payload: dict):
    if not _is_enabled("ENABLE_AUDIO_TOOLS", default=True):
        raise HTTPException(status_code=403, detail="Audio tools disabled")
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    voice = (payload.get("voice") or "alloy").strip()
    audio_bytes = await openai_tts(text, voice=voice)
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")


@app.get("/v1/models")
async def list_models():
    """Forward models list request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{OPENAI_BASE_URL}/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}
        )
        return JSONResponse(content=resp.json())


@app.get("/metrics")
async def metrics():
    """Simple in-memory metrics snapshot."""
    return JSONResponse(content=METRICS)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "OpenAI Responses Proxy", "status": "running"}
