"""
title: PPT/PDF Vision Filter
author: GLChemTec
version: 10.0
description: PPT/PPTX -> PDF (LibreOffice) -> high-DPI PNG pages for vision + PDF vision. Optimized for spectra (NMR/HPLC) clarity.
"""

import os
import base64
import tempfile
import shutil
import subprocess
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

# Optional: local PPTX text/table extraction
try:
    from pptx import Presentation  # type: ignore
    PPTX_AVAILABLE = True
except Exception:
    PPTX_AVAILABLE = False


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority (0 = highest)")
        enabled: bool = Field(default=True, description="Enable PPT/PDF vision processing")
        debug: bool = Field(default=True, description="Enable debug logging")

        # ===== Rendering quality (CRITICAL) =====
        # Use higher DPI to keep fine spectra labels legible.
        dpi: int = Field(default=600, description="DPI for PDF rendering (600 for spectra/NMR clarity)")
        # Allow more slides by default to avoid truncating longer decks.
        max_pages: int = Field(default=30, description="Max pages/slides to render as images")

        # Output format: PNG is best for small text/spectra (lossless)
        output_format: str = Field(default="png", description="png (recommended) or jpeg")
        jpeg_quality: int = Field(default=92, description="JPEG quality if output_format=jpeg")

        # Size & safety limits (prevents huge payloads) — bumped to avoid cutting pages at higher DPI
        max_total_image_mb: float = Field(default=64.0, description="Max total base64 image payload (MB)")
        # If you truly need unlimited, raise max_total_image_mb, but keep an eye on API payload limits.
s
        # PPTX pipeline
        render_pptx_via_pdf: bool = Field(default=True, description="Convert PPTX -> PDF then render pages (best fidelity)")
        libreoffice_timeout_sec: int = Field(default=60, description="LibreOffice timeout (sec) - allow larger decks to finish")

        # Include PPTX extracted text/tables (helpful for copyable content)
        include_pptx_text: bool = Field(default=True, description="Extract slide text/tables via python-pptx (if available)")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT-PDF-VISION] {msg}")

    # -------------------------
    # OpenWebUI file discovery
    # -------------------------
    def _get_file_path(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            path = (f.get("path") or "").strip()
            if path:
                return path
            if isinstance(f.get("meta"), dict):
                return (f["meta"].get("path") or "").strip()
        return (file_obj.get("path") or "").strip()

    def _get_file_name(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            name = f.get("filename") or f.get("name") or ""
            if not name and isinstance(f.get("meta"), dict):
                name = f["meta"].get("name") or ""
            return (name or "").lower().strip()
        return ((file_obj.get("name") or file_obj.get("filename") or "")).lower().strip()

    def _extract_all_files(self, body: dict, messages: list) -> List[Dict[str, Any]]:
        all_files: List[Dict[str, Any]] = []

        if isinstance(body.get("files"), list):
            all_files.extend(body["files"])

        for msg in messages:
            if isinstance(msg.get("files"), list):
                all_files.extend(msg["files"])
            if isinstance(msg.get("attachments"), list):
                all_files.extend(msg["attachments"])
            if isinstance(msg.get("sources"), list):
                for source_obj in msg["sources"]:
                    if isinstance(source_obj, dict):
                        source = source_obj.get("source", {})
                        if source.get("type") == "file" and isinstance(source.get("file"), dict):
                            all_files.append({"file": source["file"]})

        # Dedup by path
        seen = set()
        unique = []
        for f in all_files:
            p = self._get_file_path(f)
            if p and p not in seen:
                seen.add(p)
                unique.append(f)
        return unique

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join([p for p in parts if p]).strip()
        return str(content) if content else ""

    # -------------------------
    # PPTX -> PDF (LibreOffice)
    # -------------------------
    def _find_libreoffice(self) -> Optional[str]:
        return shutil.which("libreoffice") or shutil.which("soffice")

    def convert_pptx_to_pdf(self, ppt_path: str, out_dir: str) -> Optional[str]:
        lo = self._find_libreoffice()
        if not lo:
            self._log("❌ LibreOffice not found (libreoffice/soffice). PPTX->PDF disabled.")
            return None

        profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
        try:
            env = os.environ.copy()
            env["HOME"] = "/tmp"
            env["TMPDIR"] = "/tmp"

            cmd = [
                lo,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "pdf",
                "--outdir", out_dir,
                ppt_path,
            ]
            self._log(f"Running LibreOffice PPTX->PDF: {os.path.basename(ppt_path)} (timeout: {self.valves.libreoffice_timeout_sec}s)")
            r = subprocess.run(
                cmd,
                timeout=self.valves.libreoffice_timeout_sec,
                capture_output=True,
                text=True,
                env=env,
            )
            self._log(f"LibreOffice conversion completed (returncode: {r.returncode})")
            if r.returncode != 0:
                self._log(f"LibreOffice returned {r.returncode}")
                if r.stderr:
                    self._log(f"LibreOffice stderr: {r.stderr[:800]}")
                if r.stdout:
                    self._log(f"LibreOffice stdout: {r.stdout[:800]}")

            base = os.path.splitext(os.path.basename(ppt_path))[0]
            expected = os.path.join(out_dir, base + ".pdf")
            if os.path.exists(expected):
                return expected

            # Fallback: first PDF found
            for fn in os.listdir(out_dir):
                if fn.lower().endswith(".pdf"):
                    return os.path.join(out_dir, fn)

            self._log("❌ PPTX->PDF produced no PDF file.")
            return None
        except subprocess.TimeoutExpired:
            self._log(f"❌ LibreOffice conversion timed out after {self.valves.libreoffice_timeout_sec}s. Killing immediately...")
            # Kill processes immediately - no waiting
            try:
                # Force kill immediately
                subprocess.run(["pkill", "-9", "-f", "soffice"], timeout=1, capture_output=True)
                subprocess.run(["pkill", "-9", "-f", "libreoffice"], timeout=1, capture_output=True)
                # Also try killing by PID if we can find it
                subprocess.run(["killall", "-9", "soffice"], timeout=1, capture_output=True)
                subprocess.run(["killall", "-9", "libreoffice"], timeout=1, capture_output=True)
            except:
                pass
            return None
        except Exception as e:
            self._log(f"❌ PPTX->PDF error: {type(e).__name__}: {e}")
            return None
        finally:
            shutil.rmtree(profile_dir, ignore_errors=True)

    # -------------------------
    # PDF -> high-DPI images
    # -------------------------
    def convert_pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """
        Render PDF pages to images using pdf2image.
        Default output is PNG (lossless) at high DPI for spectra clarity.
        """
        paths: List[str] = []
        try:
            from pdf2image import convert_from_path  # type: ignore

            fmt = (self.valves.output_format or "png").lower().strip()
            if fmt not in ("png", "jpeg", "jpg"):
                fmt = "png"

            max_pages = max(1, int(self.valves.max_pages))
            dpi = max(72, int(self.valves.dpi))

            self._log(f"PDF->Images: dpi={dpi}, max_pages={max_pages}, fmt={fmt}")

            # Convert pages (PIL Images in memory)
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                fmt="png" if fmt == "png" else "ppm",  # convert_from_path expects fmt; we'll save ourselves
                first_page=1,
                last_page=max_pages,
            )

            max_total_bytes = int(float(self.valves.max_total_image_mb) * 1024 * 1024)
            running_bytes = 0

            for i, img in enumerate(images, start=1):
                if fmt == "png":
                    out_path = os.path.join(output_dir, f"page_{i:03d}.png")
                    img.save(out_path, format="PNG", optimize=False)
                else:
                    out_path = os.path.join(output_dir, f"page_{i:03d}.jpg")
                    img = img.convert("RGB")
                    img.save(out_path, format="JPEG", quality=int(self.valves.jpeg_quality), optimize=True)

                sz = os.path.getsize(out_path)
                running_bytes += sz
                paths.append(out_path)

                # Stop when total bytes limit reached (prevents giant payload)
                if running_bytes > max_total_bytes:
                    self._log(f"⚠️ Image payload limit reached at page {i} (>{self.valves.max_total_image_mb}MB). Stopping.")
                    break

            self._log(f"✅ Rendered {len(paths)} pages to images (total ~{running_bytes/1024/1024:.2f}MB)")
            return paths
        except Exception as e:
            self._log(f"❌ PDF->images error: {type(e).__name__}: {e}")
            return paths

    def image_file_to_data_url(self, img_path: str) -> Optional[str]:
        try:
            with open(img_path, "rb") as f:
                raw = f.read()
            ext = os.path.splitext(img_path)[1].lower()
            if ext == ".png":
                mime = "image/png"
            elif ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            else:
                mime = "image/png"
            b64 = base64.b64encode(raw).decode("utf-8")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    # -------------------------
    # PPTX text/table extraction
    # -------------------------
    def extract_pptx_text_tables(self, ppt_path: str) -> Dict[str, Any]:
        """
        Extract text + tables for copyable context. (Does not render visuals.)
        Rendering is done via PDF pipeline.
        """
        out: Dict[str, Any] = {"slides": [], "total_slides": 0}
        if not (self.valves.include_pptx_text and PPTX_AVAILABLE):
            return out

        try:
            prs = Presentation(ppt_path)
            slides = []
            for idx, slide in enumerate(prs.slides, start=1):
                texts: List[str] = []
                tables: List[List[List[str]]] = []

                for shape in slide.shapes:
                    # text
                    if hasattr(shape, "text") and shape.text:
                        t = str(shape.text).strip()
                        if t:
                            texts.append(t)

                    # tables
                    if getattr(shape, "has_table", False):
                        try:
                            table = shape.table
                            rows = []
                            for row in table.rows:
                                row_vals = []
                                for cell in row.cells:
                                    row_vals.append((cell.text or "").strip())
                                rows.append(row_vals)
                            if rows:
                                tables.append(rows)
                        except Exception:
                            pass

                notes = ""
                try:
                    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                        notes = (slide.notes_slide.notes_text_frame.text or "").strip()
                except Exception:
                    pass

                slides.append({
                    "slide_number": idx,
                    "text": "\n".join(texts).strip(),
                    "tables": tables,
                    "notes": notes
                })

            out["slides"] = slides
            out["total_slides"] = len(slides)
            return out
        except Exception as e:
            self._log(f"⚠️ PPTX text extraction failed: {type(e).__name__}: {e}")
            return out

    def format_pptx_text_tables(self, extracted: Dict[str, Any], file_name: str) -> str:
        slides = extracted.get("slides") or []
        if not slides:
            return f"=== PPTX: {file_name} ===\n(No text/tables extracted.)"

        parts = [f"=== PPTX: {file_name} (Text/Tables/Notes) ==="]
        for s in slides:
            sn = s.get("slide_number")
            text = (s.get("text") or "").strip()
            notes = (s.get("notes") or "").strip()
            tables = s.get("tables") or []

            parts.append(f"\n--- Slide {sn} ---")
            if text:
                parts.append(text)
            if notes:
                parts.append("\n[Notes]\n" + notes)

            # tables pretty-print
            for ti, trows in enumerate(tables, start=1):
                parts.append(f"\n[Table {ti}]")
                for row in trows:
                    parts.append(" | ".join(row))

        return "\n".join(parts).strip()

    # -------------------------
    # Main filter: inject text + images into last user message
    # -------------------------
    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 60)
        self._log("INLET - PPT/PDF Vision Filter v10.0 (PPT->PDF->PNG)")
        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            self._log("No files found in request.")
            return body

        all_text_sections: List[str] = []
        all_images: List[Dict[str, Any]] = []

        for fobj in files:
            file_path = self._get_file_path(fobj)
            file_name = self._get_file_name(fobj)

            if not file_path or not os.path.exists(file_path):
                continue
            if not file_name:
                file_name = os.path.basename(file_path).lower()

            is_pptx = file_name.endswith((".ppt", ".pptx"))
            is_pdf = file_name.endswith(".pdf")
            if not (is_pptx or is_pdf):
                continue

            self._log(f"Processing: {file_name}")

            with tempfile.TemporaryDirectory() as tmp:
                pdf_path = None

                # PPTX -> PDF (with fast failure)
                if is_pptx and self.valves.render_pptx_via_pdf:
                    pdf_path = self.convert_pptx_to_pdf(file_path, tmp)
                    if pdf_path:
                        self._log(f"✅ PPTX converted to PDF: {os.path.basename(pdf_path)}")
                    else:
                        self._log("⚠️ PPTX->PDF failed or timed out. Using text extraction only (faster).")

                # Always extract text/tables for PPTX (works even if PDF conversion fails)
                if is_pptx:
                    extracted = self.extract_pptx_text_tables(file_path)
                    if extracted.get("slides"):
                        all_text_sections.append(self.format_pptx_text_tables(extracted, file_name))
                        self._log(f"✅ Extracted text from {len(extracted.get('slides', []))} slides")

                # PDF direct
                if is_pdf:
                    pdf_path = file_path

                # Render PDF pages -> images
                if pdf_path and os.path.exists(pdf_path):
                    img_paths = self.convert_pdf_to_images(pdf_path, tmp)
                    for p in img_paths:
                        url = self.image_file_to_data_url(p)
                        if url:
                            all_images.append({
                                "type": "image_url",
                                "image_url": {"url": url}
                            })
                    self._log(f"✅ Added {len(img_paths)} rendered page images for {file_name}")

        if not all_text_sections and not all_images:
            self._log("No extractable content produced.")
            return body

        # Build combined text prompt in the last user message
        last_message = messages[-1]
        original_prompt = self._extract_text_content(last_message.get("content", ""))

        combined_text = original_prompt.strip() + "\n\n"

        if all_text_sections:
            combined_text += "Document text/tables/notes (extracted):\n"
            combined_text += "\n\n".join(all_text_sections).strip()
            combined_text += "\n\n"

        if all_images:
            combined_text += (
                f"Attached are {len(all_images)} high-resolution page images for visual analysis "
                f"(rendered at {self.valves.dpi} DPI, format={self.valves.output_format}).\n"
                "If you see spectra (NMR/HPLC/LCMS), read axes/labels carefully and extract peak tables if legible.\n\n"
            )

        # Replace last message content with a text block + image blocks
        content_blocks: List[Dict[str, Any]] = [{"type": "text", "text": combined_text}]

        # Ensure images are clean and only contain expected keys
        for img in all_images:
            if isinstance(img, dict) and img.get("type") == "image_url":
                iu = img.get("image_url", {})
                if isinstance(iu, dict) and iu.get("url"):
                    content_blocks.append({"type": "image_url", "image_url": {"url": iu["url"]}})

        messages[-1]["content"] = content_blocks
        body["messages"] = messages

        self._log(f"✅ Final payload to OpenWebUI:")
        self._log(f"   - Text sections: {len(all_text_sections)}")
        self._log(f"   - Image blocks: {len(all_images)} (lossless PNG recommended)")
        self._log("=" * 60)
        return body

    def stream(self, event: dict, __user__: Optional[dict] = None) -> dict:
        return event

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
