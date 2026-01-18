"""
title: PPT/PDF Vision Filter
author: GLChemTec
version: 6.0
description: Converts PPT/PPTX to PDF, then PDF pages to high-quality PNG images for vision analysis. Optimized for chemistry documents (NMR, HPLC, spectra).
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
        max_pages: int = Field(default=25, description="Max pages to convert to images")
        dpi: int = Field(default=200, description="DPI for PDF to image conversion (higher = better quality but more tokens)")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT/PDF-FILTER] {msg}")

    def _extract_all_files(self, body: dict, messages: list) -> List[Dict[str, Any]]:
        """Extract files from ALL possible locations in OpenWebUI."""
        all_files = []
        
        if isinstance(body.get("files"), list):
            self._log(f"Found {len(body['files'])} file(s) in body['files']")
            all_files.extend(body["files"])
        
        for idx, msg in enumerate(messages):
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
        
        seen_paths = set()
        unique_files = []
        for f in all_files:
            path = self._get_file_path(f)
            if path and path not in seen_paths:
                seen_paths.add(path)
                unique_files.append(f)
        
        self._log(f"Total unique files: {len(unique_files)}")
        return unique_files

    def _get_file_path(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            path = f.get("path", "")
            if path:
                return path.strip()
            if isinstance(f.get("meta"), dict):
                path = f["meta"].get("path", "")
                if path:
                    return path.strip()
        return file_obj.get("path", "").strip()

    def _get_file_name(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            name = f.get("filename") or f.get("name") or ""
            if not name and isinstance(f.get("meta"), dict):
                name = f["meta"].get("name") or ""
            if name:
                return name.lower().strip()
        return (file_obj.get("name") or file_obj.get("filename") or "").lower().strip()

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join([p for p in parts if p]).strip()
        return str(content) if content is not None else ""

    def convert_ppt_to_pdf(self, ppt_path: str, output_dir: str) -> Optional[str]:
        """Convert PPT/PPTX to PDF via LibreOffice."""
        try:
            if not os.path.exists(ppt_path):
                self._log(f"PPT file not found: {ppt_path}")
                return None

            lo = shutil.which("libreoffice") or shutil.which("soffice")
            if not lo:
                self._log("LibreOffice not found!")
                return None

            profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
            
            env = os.environ.copy()
            env["HOME"] = "/tmp"
            env["TMPDIR"] = "/tmp"

            cmd = [
                lo, "--headless", "--nologo", "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                ppt_path,
            ]
            
            self._log("Running LibreOffice conversion...")
            result = subprocess.run(cmd, timeout=self.valves.libreoffice_timeout_sec, 
                          capture_output=True, text=True, env=env)
            
            shutil.rmtree(profile_dir, ignore_errors=True)

            if result.returncode != 0:
                self._log(f"LibreOffice error: {result.stderr}")

            base = os.path.splitext(os.path.basename(ppt_path))[0]
            expected = os.path.join(output_dir, base + ".pdf")

            if os.path.exists(expected):
                self._log(f"PDF created: {expected}")
                return expected

            for fn in os.listdir(output_dir):
                if fn.lower().endswith(".pdf"):
                    return os.path.join(output_dir, fn)

            self._log("No PDF found after conversion")
            return None

        except Exception as e:
            self._log(f"PPT->PDF error: {e}")
            return None

    def convert_pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF pages to PNG images using pdf2image."""
        try:
            from pdf2image import convert_from_path
            
            self._log(f"Converting PDF to images (dpi={self.valves.dpi}, max_pages={self.valves.max_pages})...")
            
            images = convert_from_path(
                pdf_path,
                dpi=self.valves.dpi,
                fmt="png",
                first_page=1,
                last_page=self.valves.max_pages,
            )
            
            image_paths = []
            for idx, img in enumerate(images):
                img_path = os.path.join(output_dir, f"page_{idx+1:03d}.png")
                img.save(img_path, "PNG", optimize=True)
                image_paths.append(img_path)
            
            self._log(f"Created {len(image_paths)} image(s)")
            return image_paths

        except ImportError:
            self._log("pdf2image not installed!")
            return []
        except Exception as e:
            self._log(f"PDF->images error: {e}")
            return []

    def image_to_base64(self, path: str) -> Optional[str]:
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            self._log(f"Base64 error: {e}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 50)
        self._log("INLET START (v6.0 - High-Quality Images)")

        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            self._log("No files found")
            return body

        processed_images = []

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)

            self._log(f"Processing: {file_name}")

            if not file_path or not os.path.exists(file_path):
                self._log(f"File not found: {file_path}")
                continue

            is_ppt = file_name.endswith((".ppt", ".pptx"))
            is_pdf = file_name.endswith(".pdf")

            if not (is_ppt or is_pdf):
                self._log(f"Skipping: {file_name}")
                continue

            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_path = file_path

                if is_ppt:
                    self._log("Converting PPT -> PDF...")
                    pdf_path = self.convert_ppt_to_pdf(file_path, tmp_dir)
                    if not pdf_path:
                        continue

                self._log("Converting PDF -> Images...")
                image_paths = self.convert_pdf_to_images(pdf_path, tmp_dir)
                
                for img_path in image_paths:
                    b64 = self.image_to_base64(img_path)
                    if b64:
                        processed_images.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        })

        if not processed_images:
            self._log("No images to inject")
            return body

        self._log(f"Injecting {len(processed_images)} image(s)")

        last_message = messages[-1]
        original_text = self._extract_text_content(last_message.get("content", ""))

        instruction = (
            f"{original_text}\n\n"
            f"[{len(processed_images)} page images from the document are attached at {self.valves.dpi} DPI. "
            f"Provide a comprehensive technical analysis of ALL content together - "
            f"text, tables, charts, chemical structures, reaction schemes, and analytical data. "
            f"For spectra (NMR, HPLC, MS, IR), read peak values, chemical shifts, retention times, and labels if legible. "
            f"Do NOT describe page-by-page. Give a unified scientific summary.]"
        )

        messages[-1]["content"] = [{"type": "text", "text": instruction}] + processed_images
        body["messages"] = messages

        self._log(f"Done - injected {len(processed_images)} images at {self.valves.dpi} DPI")
        self._log("=" * 50)

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
