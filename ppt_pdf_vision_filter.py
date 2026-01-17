"""
title: PPT/PDF Vision Filter
author: GLChemTec
version: 3.0
description: Converts PPT/PPTX to PDF using LibreOffice, then embeds PDF as base64 marker for the Responses API proxy to pick up.
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
        max_pdf_size_mb: int = Field(default=20, description="Max PDF size in MB to embed")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT/PDF-FILTER] {msg}")

    def _has_cmd(self, name: str) -> bool:
        return shutil.which(name) is not None

    def _extract_all_files(self, body: dict, messages: list) -> List[Dict[str, Any]]:
        """Extract files from ALL possible locations in OpenWebUI."""
        all_files = []
        
        # body["files"]
        if isinstance(body.get("files"), list):
            self._log(f"Found {len(body['files'])} file(s) in body['files']")
            all_files.extend(body["files"])
        
        for idx, msg in enumerate(messages):
            # message["files"]
            if isinstance(msg.get("files"), list):
                self._log(f"Found {len(msg['files'])} file(s) in messages[{idx}]['files']")
                all_files.extend(msg["files"])
            
            # message["attachments"]
            if isinstance(msg.get("attachments"), list):
                self._log(f"Found {len(msg['attachments'])} file(s) in messages[{idx}]['attachments']")
                all_files.extend(msg["attachments"])
            
            # message["sources"] - This is where OpenWebUI stores file attachments
            if isinstance(msg.get("sources"), list):
                for src_idx, source_obj in enumerate(msg["sources"]):
                    if isinstance(source_obj, dict):
                        source = source_obj.get("source", {})
                        if source.get("type") == "file" and isinstance(source.get("file"), dict):
                            file_info = source["file"]
                            self._log(f"Found file in messages[{idx}]['sources'][{src_idx}]")
                            all_files.append({"file": file_info, "_from_sources": True})
        
        # Deduplicate by path
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
        path = file_obj.get("path", "")
        if path:
            return path.strip()
        return ""

    def _get_file_name(self, file_obj: Dict[str, Any]) -> str:
        if not isinstance(file_obj, dict):
            return ""
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            name = f.get("filename") or f.get("name") or ""
            if not name and isinstance(f.get("meta"), dict):
                name = f["meta"].get("name") or f["meta"].get("filename") or ""
            if name:
                return name.lower().strip()
        name = file_obj.get("name") or file_obj.get("filename") or ""
        return name.lower().strip()

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

            env = os.environ.copy()
            env["HOME"] = "/tmp"

            cmd = [
                lo, "--headless", "--nologo", "--nofirststartwizard",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                ppt_path,
            ]
            
            self._log(f"Running LibreOffice conversion...")
            subprocess.run(cmd, check=True, timeout=self.valves.libreoffice_timeout_sec, 
                          capture_output=True, env=env)

            base = os.path.splitext(os.path.basename(ppt_path))[0]
            expected = os.path.join(output_dir, base + ".pdf")

            if os.path.exists(expected):
                self._log(f"PDF created: {expected}")
                return expected

            for fn in os.listdir(output_dir):
                if fn.lower().endswith(".pdf"):
                    candidate = os.path.join(output_dir, fn)
                    self._log(f"Found PDF: {candidate}")
                    return candidate

            self._log("No PDF found after conversion")
            return None

        except subprocess.TimeoutExpired:
            self._log("LibreOffice timeout!")
            return None
        except Exception as e:
            self._log(f"PPT->PDF error: {e}")
            return None

    def file_to_base64(self, path: str) -> Optional[str]:
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > self.valves.max_pdf_size_mb:
                self._log(f"PDF too large: {size_mb:.1f}MB > {self.valves.max_pdf_size_mb}MB limit")
                return None
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            self._log(f"Base64 encode error: {e}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 50)
        self._log("INLET START")

        if not self.valves.enabled:
            self._log("Filter disabled")
            return body

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages")
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            self._log("No files found")
            return body

        pdf_payloads = []

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
                self._log(f"Skipping non-PPT/PDF: {file_name}")
                continue

            pdf_path = file_path

            if is_ppt:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    self._log("Converting PPT -> PDF...")
                    pdf_path = self.convert_ppt_to_pdf(file_path, tmp_dir)
                    if not pdf_path:
                        self._log("PPT->PDF failed")
                        continue
                    
                    pdf_b64 = self.file_to_base64(pdf_path)
                    if pdf_b64:
                        pdf_payloads.append({
                            "filename": os.path.basename(pdf_path),
                            "base64": pdf_b64
                        })
            else:
                # Already PDF
                pdf_b64 = self.file_to_base64(pdf_path)
                if pdf_b64:
                    pdf_payloads.append({
                        "filename": os.path.basename(pdf_path),
                        "base64": pdf_b64
                    })

        if not pdf_payloads:
            self._log("No PDFs to embed")
            return body

        self._log(f"Embedding {len(pdf_payloads)} PDF(s)")

        # Get original user text
        last_message = messages[-1]
        original_text = self._extract_text_content(last_message.get("content", ""))

        # Build content with PDF markers for the proxy to pick up
        # Format: [__PDF_FILE_B64__ filename=xxx.pdf]base64data[/__PDF_FILE_B64__]
        pdf_markers = []
        for pdf in pdf_payloads:
            marker = f"[__PDF_FILE_B64__ filename={pdf['filename']}]{pdf['base64']}[/__PDF_FILE_B64__]"
            pdf_markers.append(marker)

        # Combine original text with PDF markers
        combined_text = original_text
        if pdf_markers:
            combined_text = original_text + "\n\n" + "\n".join(pdf_markers)

        messages[-1]["content"] = combined_text
        body["messages"] = messages

        self._log(f"Injected {len(pdf_payloads)} PDF marker(s)")
        self._log("=" * 50)

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
