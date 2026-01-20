"""
title: PPT/PDF Vision Filter (Claude-Style)
author: GLChemTec
version: 7.4
description: Claude-style PDF processing with AGGRESSIVE token optimization for 200K limit.
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
        # Token management - VERY AGGRESSIVE to stay under 200K limit
        # Rule of thumb: 1KB of base64 ≈ 250-400 tokens for images
        # Target: ~50KB per image = ~15K tokens per image
        # 8 images × 15K = 120K tokens (safe under 200K)
        max_pages: int = Field(default=8, description="Max pages (8 pages = ~120K tokens max)")
        dpi: int = Field(default=72, description="DPI for rendering (72 = screen quality)")
        max_image_width: int = Field(default=800, description="Max width in pixels")
        max_image_height: int = Field(default=600, description="Max height in pixels")
        jpeg_quality: int = Field(default=40, description="JPEG quality (40 = good balance)")
        use_jpeg: bool = Field(default=True, description="Use JPEG (much smaller than PNG)")
        skip_text_extraction: bool = Field(default=True, description="Skip text extraction")
        max_total_base64_mb: float = Field(default=2.0, description="Max total base64 size in MB")

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

    def _is_openai_model(self, model: str) -> bool:
        """
        Default to OpenAI format unless we explicitly detect Anthropic.
        This prevents sending Anthropic-style "image" blocks to OpenAI.
        """
        m = (model or "").lower()
        if not m:
            return True
        if "claude" in m or "anthropic" in m:
            return False
        return any(token in m for token in ("gpt", "openai", "o1-", "o3-", "4o"))

    def _is_anthropic_model(self, model: str) -> bool:
        m = (model or "").lower()
        return "claude" in m or "anthropic" in m

    def convert_ppt_to_pdf(self, ppt_path: str, output_dir: str) -> Optional[str]:
        """Convert PPT/PPTX to PDF via LibreOffice."""
        try:
            lo = shutil.which("libreoffice") or shutil.which("soffice")
            # Check common Windows installation paths if not in PATH
            if not lo and os.name == 'nt':
                win_paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                ]
                for path in win_paths:
                    if os.path.exists(path):
                        lo = path
                        break
            if not lo:
                self._log("LibreOffice not found")
                return None

            profile_dir = tempfile.mkdtemp(prefix="lo_")
            env = os.environ.copy()
            env["HOME"] = os.path.expanduser("~") if os.name != 'nt' else os.environ.get("TEMP", "C:\\Temp")

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
            
            self._log(f"Converting PDF with max_pages={self.valves.max_pages}, dpi={self.valves.dpi}")
            images = convert_from_path(pdf_path, dpi=self.valves.dpi, fmt="png",
                                    first_page=1, last_page=self.valves.max_pages)
            paths = []
            total_size = 0
            max_bytes = int(self.valves.max_total_base64_mb * 1024 * 1024)
            
            for idx, img in enumerate(images):
                # Resize to fit within max dimensions (both width AND height)
                w, h = img.width, img.height
                max_w = self.valves.max_image_width
                max_h = self.valves.max_image_height
                
                # Calculate scale factor to fit within bounds
                scale = min(max_w / w, max_h / h, 1.0)  # Don't upscale
                if scale < 1.0:
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    self._log(f"Page {idx+1}: Resized {w}x{h} -> {new_w}x{new_h}")
                
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
                
                # Check if we're exceeding the total size limit
                if total_size > max_bytes:
                    self._log(f"WARNING: Stopping at page {idx+1} - total size {total_size/1024/1024:.1f}MB exceeds limit {self.valves.max_total_base64_mb}MB")
                    paths.append(path)
                    break
                    
                paths.append(path)
            
            self._log(f"Created {len(paths)} images, total size: {total_size / 1024 / 1024:.2f} MB")
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
        self._log("INLET - Claude-Style Processing (v7.4)")

        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        self._log(f"Found {len(files)} file(s) in request")
        
        if not files:
            self._log("No files found - checking body structure")
            self._log(f"Body keys: {list(body.keys())}")
            return body

        all_images = []
        all_text = []

        model_name = body.get("model", "")
        use_openai_format = self._is_openai_model(model_name)
        use_claude_format = self._is_anthropic_model(model_name)
        if use_openai_format and not use_claude_format:
            self._log("Target looks like OpenAI/unknown - using image_url data URLs")
        else:
            self._log("Target looks like Claude/Anthropic - using base64 image blocks")

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)
            
            self._log(f"File object: {file_obj}")
            self._log(f"Extracted path: {file_path}")
            self._log(f"Extracted name: {file_name}")

            if not file_path:
                self._log(f"No path found for file")
                continue
                
            if not os.path.exists(file_path):
                self._log(f"File does not exist: {file_path}")
                continue

            is_ppt = file_name.endswith((".ppt", ".pptx"))
            is_pdf = file_name.endswith(".pdf")

            if not (is_ppt or is_pdf):
                self._log(f"Skipping non-PPT/PDF file: {file_name}")
                continue

            self._log(f"Processing: {file_name}")

            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_path = file_path

                # Stage 1: Convert PPT to PDF if needed
                if is_ppt:
                    self._log("Stage 1: PPT -> PDF")
                    pdf_path = self.convert_ppt_to_pdf(file_path, tmp_dir)
                    if not pdf_path:
                        self._log(f"ERROR: PPT->PDF conversion failed for {file_name}. Skipping file.")
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
                self._log(f"Got {len(image_paths)} image paths")
                
                total_b64_size = 0
                for img_path in image_paths:
                    b64 = self.image_to_base64(img_path)
                    if b64:
                        b64_size = len(b64)
                        total_b64_size += b64_size
                        # Estimate tokens: ~250-400 tokens per KB of base64 for images
                        est_tokens = int(b64_size / 1024 * 300)
                        mime = "image/jpeg" if self.valves.use_jpeg else "image/png"

                        if use_openai_format and not use_claude_format:
                            all_images.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64}"
                                }
                            })
                        else:
                            all_images.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64
                                }
                            })

                        self._log(
                            f"Added page {len(all_images)}: {b64_size/1024:.1f}KB "
                            f"(~{est_tokens} tokens) [{ 'openai' if use_openai_format else 'claude'}]"
                        )
                
                total_est_tokens = int(total_b64_size / 1024 * 300)
                self._log(f"Total for this file: {total_b64_size/1024/1024:.2f}MB (~{total_est_tokens} tokens)")

        if not all_images and not all_text:
            self._log("No content extracted from any files")
            return body

        # Stage 3: Combine text + images for the model
        self._log(f"Stage 3: Combining {len(all_images)} images + {len(all_text)} text sections")

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
            "For NMR, give the spectrum title and a concise peak table (shift, multiplicity, J, integration). "
            "Skip dumping raw ppm lists or placeholder labels. Provide an ACS-style summary; keep other findings concise."
        )

        # Combine: text block + all image blocks
        content_blocks = [{"type": "text", "text": combined_text}] + all_images
        messages[-1]["content"] = content_blocks
        body["messages"] = messages

        self._log(f"SUCCESS - Added {len(all_images)} images to message content")
        self._log("=" * 50)
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
