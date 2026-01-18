"""
title: PPT to PDF Converter
author: GLChemTec
version: 1.0
description: Converts PPT/PPTX to PDF for Claude analysis. Claude handles PDF vision natively.
"""

import os
import subprocess
import tempfile
import shutil
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority")
        enabled: bool = Field(default=True, description="Enable PPT to PDF conversion")
        libreoffice_timeout_sec: int = Field(default=240, description="LibreOffice timeout (sec)")
        debug: bool = Field(default=True, description="Enable debug logging")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT-TO-PDF] {msg}")

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

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        self._log("=" * 50)
        self._log("INLET START (PPT to PDF for Claude)")

        if not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        files = self._extract_all_files(body, messages)
        if not files:
            self._log("No files found")
            return body

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)

            self._log(f"Checking: {file_name}")

            if not file_path or not os.path.exists(file_path):
                continue

            is_ppt = file_name.endswith((".ppt", ".pptx"))

            if not is_ppt:
                self._log(f"Skipping (not PPT): {file_name}")
                continue

            self._log(f"Converting PPT to PDF: {file_name}")
            
            # Convert to PDF in the same directory as the original
            output_dir = os.path.dirname(file_path)
            pdf_path = self.convert_ppt_to_pdf(file_path, output_dir)
            
            if pdf_path:
                # Update the file reference to point to the PDF
                if isinstance(file_obj.get("file"), dict):
                    file_obj["file"]["path"] = pdf_path
                    base_name = os.path.splitext(file_name)[0]
                    file_obj["file"]["filename"] = f"{base_name}.pdf"
                    file_obj["file"]["name"] = f"{base_name}.pdf"
                    if isinstance(file_obj["file"].get("meta"), dict):
                        file_obj["file"]["meta"]["path"] = pdf_path
                        file_obj["file"]["meta"]["name"] = f"{base_name}.pdf"
                self._log(f"Updated file reference to PDF: {pdf_path}")

        self._log("=" * 50)
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
