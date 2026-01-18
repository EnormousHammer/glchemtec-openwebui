"""
title: PPT/PDF Vision Filter
author: GLChemTec
version: 5.0
description: Converts PPT/PPTX to PDF, then sends PDF directly to OpenAI Responses API for native vision analysis (no quality loss).
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

    def file_to_base64(self, path: str) -> Optional[str]:
        """Read file and encode as base64."""
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            self._log(f"Base64 error: {e}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 50)
        self._log("INLET START (v5.0 - Direct PDF)")

        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            self._log("No files found")
            return body

        pdf_markers = []

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

            pdf_path = file_path
            tmp_dir = None

            try:
                if is_ppt:
                    self._log("Converting PPT -> PDF...")
                    tmp_dir = tempfile.mkdtemp(prefix="ppt_convert_")
                    pdf_path = self.convert_ppt_to_pdf(file_path, tmp_dir)
                    if not pdf_path:
                        continue

                # Read PDF and encode as base64
                self._log(f"Encoding PDF: {pdf_path}")
                pdf_b64 = self.file_to_base64(pdf_path)
                
                if pdf_b64:
                    # Get a clean filename for the PDF
                    pdf_filename = os.path.basename(pdf_path)
                    if is_ppt:
                        # Use original PPT name but with .pdf extension
                        base_name = os.path.splitext(os.path.basename(file_path))[0]
                        pdf_filename = f"{base_name}.pdf"
                    
                    # Create marker that proxy will recognize
                    marker = f"[__PDF_FILE_B64__ filename={pdf_filename}]{pdf_b64}[/__PDF_FILE_B64__]"
                    pdf_markers.append(marker)
                    self._log(f"Created PDF marker for: {pdf_filename} ({len(pdf_b64)} chars)")

            finally:
                if tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        if not pdf_markers:
            self._log("No PDFs to inject")
            return body

        self._log(f"Injecting {len(pdf_markers)} PDF(s)")

        last_message = messages[-1]
        original_text = self._extract_text_content(last_message.get("content", ""))

        # Build instruction with PDF markers
        instruction = (
            f"{original_text}\n\n"
            f"[{len(pdf_markers)} PDF document(s) attached for analysis. "
            f"Provide a comprehensive summary analyzing ALL content together - "
            f"text, tables, charts, chemical structures, spectra (HPLC, NMR, MS), reaction schemes, and data. "
            f"For spectra, read peak values and labels if legible. "
            f"Do NOT describe page-by-page. Give a unified technical analysis.]\n\n"
        )
        
        # Append all PDF markers
        instruction += "\n".join(pdf_markers)

        messages[-1]["content"] = instruction
        body["messages"] = messages

        self._log(f"Done - injected {len(pdf_markers)} PDF marker(s)")
        self._log("=" * 50)

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
