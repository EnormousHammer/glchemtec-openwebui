"""
title: Document Export Filter
author: GLChemTec
version: 1.0
description: Detects export requests and generates Word/PDF files from conversation content.
"""

import os
import re
import json
import base64
import io
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=10, description="Filter priority (higher = runs later)")
        enabled: bool = Field(default=True, description="Enable document export")
        debug: bool = Field(default=True, description="Enable debug logging")
        export_service_url: str = Field(
            default="http://localhost:8000",
            description="URL of the export service (proxy)"
        )

    def __init__(self):
        try:
            # Get export service URL from env if set, otherwise use default
            export_url = os.environ.get("EXPORT_SERVICE_URL", "http://localhost:8000")
            self.valves = self.Valves(export_service_url=export_url)
            self._log("Export filter initialized")
        except Exception as e:
            # If initialization fails, disable the filter to prevent crashes
            print(f"[EXPORT-FILTER] ERROR in __init__: {e}")
            import traceback
            print(f"[EXPORT-FILTER] Traceback: {traceback.format_exc()}")
            # Create a minimal disabled filter
            self.valves = self.Valves(enabled=False)
        # Patterns to detect export requests
        self.export_patterns = [
            r"export\s+(?:this|the|that)\s+(?:to|as|in)\s+(?:word|docx|\.docx)",
            r"create\s+(?:a|an)\s+(?:word|docx|\.docx)\s+(?:file|document)",
            r"make\s+(?:a|an)\s+(?:word|docx|\.docx)\s+(?:file|document)",
            r"generate\s+(?:a|an)\s+(?:word|docx|\.docx)\s+(?:file|document)",
            r"save\s+(?:this|it|that)\s+(?:as|to)\s+(?:word|docx|\.docx)",
            r"export\s+(?:this|the|that)\s+(?:to|as|in)\s+(?:pdf|\.pdf)",
            r"create\s+(?:a|an)\s+(?:pdf|\.pdf)\s+(?:file|document)",
            r"make\s+(?:a|an)\s+(?:pdf|\.pdf)\s+(?:file|document)",
            r"generate\s+(?:a|an)\s+(?:pdf|\.pdf)\s+(?:file|document)",
            r"save\s+(?:this|it|that)\s+(?:as|to)\s+(?:pdf|\.pdf)",
            r"convert\s+(?:this|it|that)\s+(?:to|into)\s+(?:word|docx|pdf)",
        ]

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[EXPORT-FILTER] {msg}")

    def _detect_export_request(self, text: str) -> Optional[str]:
        """Detect if user is requesting an export and return format (word/pdf)."""
        text_lower = text.lower()
        for pattern in self.export_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                matched = match.group(0)
                if "word" in matched or "docx" in matched:
                    return "docx"
                elif "pdf" in matched:
                    return "pdf"
        return None

    def _extract_text_content(self, content: Any) -> str:
        """Extract text from message content."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
            return "\n".join(p for p in parts if p).strip()
        return str(content) if content else ""

    def _build_report_from_conversation(self, messages: List[Dict[str, Any]], format_type: str) -> Dict[str, Any]:
        """Build a structured report from conversation messages."""
        report = {
            "title": "Conversation Export",
            "subtitle": f"Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sections": []
        }

        current_section = None
        for msg in messages:
            role = msg.get("role", "")
            content = self._extract_text_content(msg.get("content", ""))
            
            if not content.strip():
                continue

            if role == "user":
                # User message becomes a section heading
                heading = content[:100] + ("..." if len(content) > 100 else "")
                current_section = {
                    "heading": heading,
                    "body": "",
                    "bullets": []
                }
            elif role == "assistant" and current_section:
                # Assistant response becomes the body
                current_section["body"] = content
                report["sections"].append(current_section)
                current_section = None
            elif role == "assistant" and not current_section:
                # Standalone assistant message
                report["sections"].append({
                    "heading": "Response",
                    "body": content,
                    "bullets": []
                })

        return report

    def _generate_export_file(self, report: Dict[str, Any], format_type: str) -> Optional[bytes]:
        """Generate export file (Word or PDF) via the proxy service."""
        try:
            url = f"{self.valves.export_service_url}/v1/report/{format_type}"
            self._log(f"Requesting export from: {url}")
            
            response = requests.post(url, json=report, timeout=60)
            
            if response.status_code == 200:
                return response.content
            else:
                self._log(f"Export failed: {response.status_code} - {response.text[:200]}")
                return None
        except Exception as e:
            self._log(f"Export error: {e}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Input filter - detects export requests and generates files BEFORE assistant responds.
        This is the better approach: generate file early, then assistant can reference it.
        """
        self._log("Inlet called")
        if not self.valves.enabled:
            self._log("Filter disabled, skipping")
            return body

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages in body")
            return body

        # Check the last user message for export requests
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            return body

        user_content = self._extract_text_content(last_user_msg.get("content", ""))
        export_format = self._detect_export_request(user_content)

        if export_format:
            self._log(f"Export request detected in inlet: {export_format.upper()}")
            
            # Generate the file NOW (before assistant responds)
            # This way we can provide a download link that the assistant can reference
            report = self._build_report_from_conversation(messages, export_format)
            file_bytes = self._generate_export_file(report, export_format)
            
            if file_bytes:
                filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
                
                # Save file to uploads directory
                upload_dir = os.environ.get("UPLOAD_DIR", "/app/backend/data/uploads")
                if not os.path.exists(upload_dir):
                    for alt_dir in ["/app/uploads", "/app/data/uploads", "/tmp"]:
                        if os.path.exists(alt_dir):
                            upload_dir = alt_dir
                            break
                
                file_path = os.path.join(upload_dir, filename)
                try:
                    with open(file_path, "wb") as f:
                        f.write(file_bytes)
                    self._log(f"Export file generated and saved in inlet: {file_path} ({len(file_bytes)} bytes)")
                    
                    # Create download link - use data URL for small files
                    mime_type = "application/pdf" if export_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    file_size_kb = len(file_bytes) // 1024
                    
                    if len(file_bytes) < 5 * 1024 * 1024:  # Less than 5MB
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")
                        download_url = f"data:{mime_type};base64,{b64_data}"
                    else:
                        # For large files, provide file path
                        download_url = f"file://{file_path}"
                    
                    # Modify user message to include file info and instruction
                    # This tells the assistant to provide a download link
                    instruction = (
                        f"\n\n[SYSTEM NOTE: The user requested to export this conversation to {export_format.upper()}. "
                        f"The file has been generated: {filename} ({file_size_kb}KB). "
                        f"Please inform the user that the file is ready and provide this download link: {download_url} "
                        f"or mention that the file is saved at {file_path}. "
                        f"Use markdown format for the link: [Download {filename}]({download_url})]"
                    )
                    
                    if isinstance(last_user_msg.get("content"), str):
                        last_user_msg["content"] = user_content + instruction
                    elif isinstance(last_user_msg.get("content"), list):
                        last_msg_content = last_user_msg.get("content", [])
                        if not isinstance(last_msg_content, list):
                            last_msg_content = [{"type": "text", "text": user_content}]
                        last_msg_content.append({
                            "type": "text",
                            "text": instruction
                        })
                        last_user_msg["content"] = last_msg_content
                    
                    # Store file info in body metadata for outlet to use
                    if "metadata" not in body:
                        body["metadata"] = {}
                    if "export_file" not in body["metadata"]:
                        body["metadata"]["export_file"] = {}
                    body["metadata"]["export_file"] = {
                        "path": file_path,
                        "filename": filename,
                        "format": export_format,
                        "size": len(file_bytes),
                        "download_url": download_url
                    }
                    
                except Exception as e:
                    self._log(f"Failed to save export file in inlet: {e}")
                    import traceback
                    self._log(f"Traceback: {traceback.format_exc()}")
            else:
                self._log("Failed to generate export file in inlet")

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Output filter - enhances assistant response with file download link.
        File was already generated in inlet, so we just enhance the message here.
        """
        try:
            self._log("Outlet called")
            if not self.valves.enabled:
                self._log("Filter disabled, skipping")
                return body
        except Exception as e:
            print(f"[EXPORT-FILTER] ERROR in outlet: {e}")
            return body

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages in body")
            return body

        # Check if we have export file info from inlet
        export_file_info = None
        if isinstance(body.get("metadata"), dict):
            export_file_info = body["metadata"].get("export_file")
        
        # If no metadata, check user message for export request (fallback)
        if not export_file_info:
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg
                    break

            if last_user_msg:
                user_content = self._extract_text_content(last_user_msg.get("content", ""))
                export_format = self._detect_export_request(user_content)
                
                if export_format:
                    self._log(f"Export request detected in outlet (fallback): {export_format.upper()}")
                    # Generate file now (fallback if inlet didn't run)
                    report = self._build_report_from_conversation(messages, export_format)
                    file_bytes = self._generate_export_file(report, export_format)
                    
                    if file_bytes:
                        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
                        upload_dir = os.environ.get("UPLOAD_DIR", "/app/backend/data/uploads")
                        if not os.path.exists(upload_dir):
                            for alt_dir in ["/app/uploads", "/app/data/uploads", "/tmp"]:
                                if os.path.exists(alt_dir):
                                    upload_dir = alt_dir
                                    break
                        
                        file_path = os.path.join(upload_dir, filename)
                        try:
                            with open(file_path, "wb") as f:
                                f.write(file_bytes)
                            self._log(f"Export file saved (fallback): {file_path}")
                            export_file_info = {
                                "path": file_path,
                                "filename": filename,
                                "format": export_format,
                                "size": len(file_bytes)
                            }
                        except Exception as e:
                            self._log(f"Failed to save file in outlet fallback: {e}")
        
        # If we have file info (from inlet or fallback), enhance the assistant message
        if export_file_info and messages:
            last_msg = messages[-1]
            filename = export_file_info.get("filename", "export_file")
            file_path = export_file_info.get("path", "")
            export_format = export_file_info.get("format", "pdf")
            file_size = export_file_info.get("size", 0)
            download_url = export_file_info.get("download_url", "")
            
            # If no download_url, create one
            if not download_url and file_path and os.path.exists(file_path):
                mime_type = "application/pdf" if export_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if file_size < 5 * 1024 * 1024:  # Less than 5MB
                    try:
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")
                        download_url = f"data:{mime_type};base64,{b64_data}"
                    except Exception as e:
                        self._log(f"Failed to create data URL: {e}")
                        download_url = f"file://{file_path}"
                else:
                    download_url = f"file://{file_path}"
            
            # Enhance assistant message with download link
            content = self._extract_text_content(last_msg.get("content", ""))
            file_size_kb = file_size // 1024 if file_size else 0
            
            # Check if assistant already mentioned the file (from our inlet instruction)
            if download_url and download_url not in content:
                # Add download link if not already present
                download_link = f"[📥 Download {filename}]({download_url})"
                export_note = (
                    f"\n\n---\n"
                    f"📄 **Export File Ready**: {filename} ({file_size_kb}KB)\n"
                    f"{download_link}\n"
                )
                
                if isinstance(last_msg.get("content"), str):
                    last_msg["content"] = content + export_note
                elif isinstance(last_msg.get("content"), list):
                    last_msg["content"].append({
                        "type": "text",
                        "text": export_note
                    })
                
                self._log(f"Enhanced assistant message with download link for {filename}")

        return body
