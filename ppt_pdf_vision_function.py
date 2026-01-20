"""
title: PPT/PDF Vision Function
author: GLChemTec
version: 7.4
description: Function (Pipe) version - Converts PPT/PDF to images for Claude vision analysis.
required_open_webui_version: 0.4.0
"""

import os
import base64
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict, Any, Generator, Iterator, Union

from pydantic import BaseModel, Field


class Pipe:
    """OpenWebUI Function (Pipe) for PPT/PDF vision processing."""
    
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Function priority")
        debug: bool = Field(default=True, description="Enable debug logging")
        libreoffice_timeout_sec: int = Field(default=240, description="LibreOffice timeout (sec)")
        # Token management - VERY AGGRESSIVE to stay under 200K limit
        max_pages: int = Field(default=8, description="Max pages (8 pages = ~120K tokens max)")
        dpi: int = Field(default=72, description="DPI for rendering (72 = screen quality)")
        max_image_width: int = Field(default=800, description="Max width in pixels")
        max_image_height: int = Field(default=600, description="Max height in pixels")
        jpeg_quality: int = Field(default=40, description="JPEG quality (40 = good balance)")
        use_jpeg: bool = Field(default=True, description="Use JPEG (much smaller than PNG)")
        max_total_base64_mb: float = Field(default=2.0, description="Max total base64 size in MB")
        # Model to forward to
        target_model: str = Field(default="anthropic/claude-sonnet-4-20250514", description="Model to forward processed request to")

    def __init__(self):
        self.type = "pipe"
        self.id = "ppt_pdf_vision"
        self.name = "PPT/PDF Vision"
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT/PDF-VISION] {msg}")

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
                    self._log(f"WARNING: Stopping at page {idx+1} - total size {total_size/1024/1024:.1f}MB exceeds limit")
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

    def pipes(self) -> List[dict]:
        """Return list of available pipes/models."""
        return [{"id": "ppt_pdf_vision", "name": "PPT/PDF Vision Analyzer"}]

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        """Main pipe function - processes PPT/PDF files and forwards to target model."""
        self._log("=" * 50)
        self._log("PIPE - PPT/PDF Vision Processing (v7.4)")

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages in body")
            return body

        files = self._extract_all_files(body, messages)
        self._log(f"Found {len(files)} file(s) in request")
        
        if not files:
            self._log("No files found - passing through unchanged")
            # No files to process, forward as-is
            body["model"] = self.valves.target_model
            return body

        all_images = []

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)
            
            self._log(f"File: {file_name} at {file_path}")

            if not file_path or not os.path.exists(file_path):
                self._log(f"File not found: {file_path}")
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
                        continue

                # Stage 2: Convert pages to images
                self._log("Stage 2: Converting pages to images")
                image_paths = self.convert_pdf_to_images(pdf_path, tmp_dir)
                self._log(f"Got {len(image_paths)} image paths")
                
                total_b64_size = 0
                for img_path in image_paths:
                    b64 = self.image_to_base64(img_path)
                    if b64:
                        b64_size = len(b64)
                        total_b64_size += b64_size
                        est_tokens = int(b64_size / 1024 * 300)
                        
                        mime = "image/jpeg" if self.valves.use_jpeg else "image/png"
                        # Anthropic/Claude format for images
                        all_images.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64
                            }
                        })
                        self._log(f"Added page {len(all_images)}: {b64_size/1024:.1f}KB (~{est_tokens} tokens)")
                
                total_est_tokens = int(total_b64_size / 1024 * 300)
                self._log(f"Total for this file: {total_b64_size/1024/1024:.2f}MB (~{total_est_tokens} tokens)")

        if not all_images:
            self._log("No images extracted from any files")
            body["model"] = self.valves.target_model
            return body

        # Stage 3: Build the message with images
        self._log(f"Stage 3: Building message with {len(all_images)} images")

        last_message = messages[-1]
        original_prompt = self._extract_text_content(last_message.get("content", ""))

        combined_text = f"{original_prompt}\n\n"
        combined_text += (
            f"[{len(all_images)} PAGE IMAGES ATTACHED]\n"
            "Analyze the page images. "
            "For spectra (NMR, HPLC, MS), read peaks, chemical shifts, and labels from the images."
        )

        # Combine: text block + all image blocks
        content_blocks = [{"type": "text", "text": combined_text}] + all_images
        messages[-1]["content"] = content_blocks
        body["messages"] = messages
        body["model"] = self.valves.target_model

        self._log(f"SUCCESS - Added {len(all_images)} images, forwarding to {self.valves.target_model}")
        self._log("=" * 50)
        return body
