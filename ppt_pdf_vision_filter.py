"""
title: PPT/PDF Vision Filter (Claude-Style)
author: GLChemTec
version: 7.3
description: Claude-style PDF processing with token optimization - JPEG compression, resizing, optional text extraction.
"""

import os
import base64
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority")
        enabled: bool = Field(default=True, description="Enable PPT/PDF vision processing")
        libreoffice_timeout_sec: int = Field(default=240, description="LibreOffice timeout (sec)")
        debug: bool = Field(default=True, description="Enable debug logging")
        # Token management - VERY AGGRESSIVE for Claude's 200K limit
        max_pages: int = Field(default=15, description="Max pages to process")
        dpi: int = Field(default=50, description="DPI for page images (50 = minimum readable)")
        max_image_width: int = Field(default=600, description="Max image width in pixels")
        jpeg_quality: int = Field(default=40, description="JPEG quality (40 = compressed but readable)")
        use_jpeg: bool = Field(default=True, description="Use JPEG instead of PNG (much smaller)")
        skip_text_extraction: bool = Field(default=True, description="Skip text - images have it all")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[CLAUDE-STYLE] {msg}")

    def _extract_all_files(self, body: dict, messages: list) -> List[Dict[str, Any]]:
        all_files = []
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
        
        seen = set()
        unique = []
        for f in all_files:
            path = self._get_file_path(f)
            if path and path not in seen:
                seen.add(path)
                unique.append(f)
        return unique

    def _get_file_path(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            path = f.get("path", "")
            if path:
                return path.strip()
            if isinstance(f.get("meta"), dict):
                return f["meta"].get("path", "").strip()
        return file_obj.get("path", "").strip()

    def _get_file_name(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            name = f.get("filename") or f.get("name") or ""
            if not name and isinstance(f.get("meta"), dict):
                name = f["meta"].get("name") or ""
            return name.lower().strip()
        return (file_obj.get("name") or file_obj.get("filename") or "").lower().strip()

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            return "\n".join(p for p in parts if p).strip()
        return str(content) if content else ""

    def convert_ppt_to_pdf(self, ppt_path: str, output_dir: str) -> Optional[str]:
        """Convert PPT/PPTX to PDF via LibreOffice."""
        try:
            lo = shutil.which("libreoffice") or shutil.which("soffice")
            if not lo:
                self._log("LibreOffice not found")
                return None

            profile_dir = tempfile.mkdtemp(prefix="lo_")
            env = os.environ.copy()
            env["HOME"] = "/tmp"

            cmd = [lo, "--headless", "--nologo", "--nofirststartwizard",
                   f"-env:UserInstallation=file://{profile_dir}",
                   "--convert-to", "pdf", "--outdir", output_dir, ppt_path]
            
            subprocess.run(cmd, timeout=self.valves.libreoffice_timeout_sec, 
                          capture_output=True, env=env)
            shutil.rmtree(profile_dir, ignore_errors=True)

            base = os.path.splitext(os.path.basename(ppt_path))[0]
            pdf_path = os.path.join(output_dir, base + ".pdf")
            return pdf_path if os.path.exists(pdf_path) else None
        except Exception as e:
            self._log(f"PPT->PDF error: {e}")
            return None

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using pdfplumber or PyMuPDF."""
        text_parts = []
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc):
                if page_num >= self.valves.max_pages:
                    break
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")
            doc.close()
            self._log(f"Extracted text from {min(len(text_parts), self.valves.max_pages)} pages")
        except ImportError:
            self._log("PyMuPDF not available, trying pdfplumber")
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        if page_num >= self.valves.max_pages:
                            break
                        text = page.extract_text() or ""
                        if text.strip():
                            text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")
                self._log(f"Extracted text from {len(text_parts)} pages")
            except Exception as e:
                self._log(f"Text extraction failed: {e}")
        except Exception as e:
            self._log(f"Text extraction error: {e}")
        
        return "\n\n".join(text_parts)

    def convert_pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF pages to optimized images for token efficiency."""
        try:
            from pdf2image import convert_from_path
            from PIL import Image
            
            images = convert_from_path(pdf_path, dpi=self.valves.dpi, fmt="png",
                                       first_page=1, last_page=self.valves.max_pages)
            paths = []
            total_size = 0
            
            for idx, img in enumerate(images):
                # Resize if too wide (saves tokens significantly)
                if img.width > self.valves.max_image_width:
                    ratio = self.valves.max_image_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((self.valves.max_image_width, new_height), Image.LANCZOS)
                
                # Save as JPEG (much smaller) or PNG
                if self.valves.use_jpeg:
                    path = os.path.join(output_dir, f"page_{idx+1:03d}.jpg")
                    img = img.convert("RGB")  # JPEG doesn't support alpha
                    img.save(path, "JPEG", quality=self.valves.jpeg_quality, optimize=True)
                else:
                    path = os.path.join(output_dir, f"page_{idx+1:03d}.png")
                    img.save(path, "PNG", optimize=True)
                
                file_size = os.path.getsize(path)
                total_size += file_size
                paths.append(path)
            
            self._log(f"Created {len(paths)} images, total size: {total_size / 1024 / 1024:.1f} MB")
            return paths
        except Exception as e:
            self._log(f"PDF->images error: {e}")
            return []

    def image_to_base64(self, path: str) -> Optional[str]:
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except:
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 50)
        self._log("INLET - Claude-Style Processing (v7.0)")

        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            return body

        all_images = []
        all_text = []

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)

            if not file_path or not os.path.exists(file_path):
                continue

            is_ppt = file_name.endswith((".ppt", ".pptx"))
            is_pdf = file_name.endswith(".pdf")

            if not (is_ppt or is_pdf):
                continue

            self._log(f"Processing: {file_name}")

            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_path = file_path

                # Stage 1: Convert PPT to PDF if needed
                if is_ppt:
                    self._log("Stage 1: PPT -> PDF")
                    pdf_path = self.convert_ppt_to_pdf(file_path, tmp_dir)
                    if not pdf_path:
                        continue

                # Stage 2a: Extract text from PDF (optional - can skip to save tokens)
                if not self.valves.skip_text_extraction:
                    self._log("Stage 2a: Extracting text from PDF")
                    extracted_text = self.extract_text_from_pdf(pdf_path)
                    if extracted_text:
                        all_text.append(f"=== Document: {file_name} ===\n{extracted_text}")

                # Stage 2b: Convert pages to images
                self._log("Stage 2b: Converting pages to images")
                image_paths = self.convert_pdf_to_images(pdf_path, tmp_dir)
                
                for img_path in image_paths:
                    b64 = self.image_to_base64(img_path)
                    if b64:
                        # Use correct mime type
                        mime = "image/jpeg" if self.valves.use_jpeg else "image/png"
                        all_images.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}
                        })

        if not all_images and not all_text:
            self._log("No content extracted")
            return body

        # Stage 3: Combine text + images for the model
        self._log(f"Stage 3: Combining {len(all_images)} images + extracted text")

        last_message = messages[-1]
        original_prompt = self._extract_text_content(last_message.get("content", ""))

        # Build combined content like Claude does
        combined_text = f"{original_prompt}\n\n"
        
        if all_text:
            combined_text += "[EXTRACTED TEXT FROM DOCUMENT]\n"
            combined_text += "\n".join(all_text)
            combined_text += "\n\n"
        
        combined_text += (
            f"[{len(all_images)} PAGE IMAGES ATTACHED]\n"
            "Analyze both the extracted text AND the page images. "
            "For spectra (NMR, HPLC, MS), read peaks, chemical shifts, and labels from the images. "
            "Cross-reference with the extracted text for accuracy."
        )

        # Combine: text block + all image blocks
        content_blocks = [{"type": "text", "text": combined_text}] + all_images
        messages[-1]["content"] = content_blocks
        body["messages"] = messages

        self._log(f"Done - {len(all_images)} images + {len(all_text)} text sections")
        self._log("=" * 50)
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
