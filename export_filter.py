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
from pathlib import Path

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=10, description="Filter priority (higher = runs later)")
        enabled: bool = Field(default=True, description="Enable document export")
        debug: bool = Field(default=True, description="Enable debug logging")
        export_service_url: str = Field(
            default="http://localhost:8000",
            description="URL of the export service (proxy) - internal"
        )
        public_base_url: str = Field(
            default="",
            description="Public URL for download links (e.g., https://glchemtec-openwebui.onrender.com)"
        )
        # Branding and customization
        company_name: str = Field(default="GLChemTec", description="Company name for branding")
        company_logo_path: str = Field(default="/app/backend/open_webui/static/branding/GLC_Logo.png", description="Path to company logo image")
        primary_color: str = Field(default="#1d2b3a", description="Primary brand color (hex)")
        secondary_color: str = Field(default="#e6eef5", description="Secondary brand color (hex)")
        enable_sharepoint: bool = Field(default=False, description="Enable SharePoint integration (forced off)")
        sharepoint_site_url: str = Field(default="", description="SharePoint site URL")
        sharepoint_folder: str = Field(default="Documents", description="SharePoint folder path")

    def __init__(self):
        try:
            # Get export service URL from env if set, otherwise use default
            export_url = os.environ.get("EXPORT_SERVICE_URL", "http://localhost:8000")
            # Get public URL for download links
            public_url = os.environ.get("WEBUI_URL", os.environ.get("PUBLIC_URL", ""))
            if not public_url:
                # Try to detect from common env vars
                public_url = os.environ.get("RENDER_EXTERNAL_URL", "")
            self.valves = self.Valves(export_service_url=export_url, public_base_url=public_url)
            # Force SharePoint export off regardless of env
            self.valves.enable_sharepoint = False
            self._log(f"Export filter initialized (public_url: {public_url})")
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

    def _get_document_icon(self, format_type: str) -> str:
        """Get emoji/icon for document type."""
        icons = {
            "pdf": "📄",
            "docx": "📝",
            "word": "📝"
        }
        return icons.get(format_type.lower(), "📄")
    
    def _get_branding_config(self) -> Dict[str, Any]:
        """Get branding configuration from environment or valves."""
        # Find logo - check multiple possible locations
        logo_path = self.valves.company_logo_path or os.environ.get("COMPANY_LOGO_PATH", "")
        
        # If not set or doesn't exist, try common locations
        if not logo_path or not os.path.exists(logo_path):
            possible_paths = [
                "/app/backend/open_webui/static/branding/GLC_Logo.png",
                "/app/backend/static/branding/GLC_Logo.png",
                "/app/public/GLC_Logo.png",
                "public/GLC_Logo.png",
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    logo_path = p
                    self._log(f"Found logo at: {p}")
                    break
        
        return {
            "company_name": self.valves.company_name or os.environ.get("COMPANY_NAME", "GLChemTec"),
            "logo_path": logo_path if logo_path and os.path.exists(logo_path) else "",
            "primary_color": self.valves.primary_color or os.environ.get("PRIMARY_COLOR", "#1d2b3a"),
            "secondary_color": self.valves.secondary_color or os.environ.get("SECONDARY_COLOR", "#e6eef5"),
        }
    
    def _build_report_from_conversation(self, messages: List[Dict[str, Any]], format_type: str) -> Dict[str, Any]:
        """Build a structured report from conversation messages with branding."""
        branding = self._get_branding_config()
        icon = self._get_document_icon(format_type)
        
        # Extract conversation metadata
        first_user_msg = None
        for msg in messages:
            if msg.get("role") == "user":
                first_user_msg = msg
                break
        
        # Create a more descriptive title
        title_prefix = f"{icon} {format_type.upper()} Export"
        if first_user_msg:
            user_content = self._extract_text_content(first_user_msg.get("content", ""))
            if user_content:
                # Use first few words of first user message as part of title
                title_words = user_content[:50].strip().split()[:5]
                if title_words:
                    title_prefix = f"{icon} {' '.join(title_words)}"
        
        report = {
            "title": title_prefix,
            "subtitle": f"Generated by {branding['company_name']} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "author": branding["company_name"],
            "company_name": branding["company_name"],
            "logo_path": branding["logo_path"],
            "primary_color": branding["primary_color"],
            "secondary_color": branding["secondary_color"],
            "document_type": format_type,
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
    
    def _create_export_with_link(self, report: Dict[str, Any], format_type: str) -> Optional[Dict[str, Any]]:
        """Create export file and return base64 data URL for direct download."""
        try:
            # Generate the file bytes directly
            file_bytes = self._generate_export_file(report, format_type)
            
            if not file_bytes:
                self._log("Failed to generate export file bytes")
                return None
            
            # Create base64 data URL (works directly in browser, no server needed)
            b64_data = base64.b64encode(file_bytes).decode("utf-8")
            
            if format_type == "pdf":
                mime_type = "application/pdf"
                ext = "pdf"
            else:
                mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ext = "docx"
            
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            # Data URL format: data:mime_type;base64,data
            data_url = f"data:{mime_type};base64,{b64_data}"
            
            self._log(f"Export created with data URL: {filename} ({len(file_bytes)} bytes)")
            
            return {
                "success": True,
                "filename": filename,
                "size_bytes": len(file_bytes),
                "download_url": data_url,
                "is_data_url": True
            }
            
        except Exception as e:
            self._log(f"Export creation error: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _upload_to_sharepoint(self, file_path: str, filename: str) -> Optional[str]:
        """Upload file to SharePoint and return the sharepoint URL."""
        # SharePoint uploads are disabled
        return None
        
        try:
            # SharePoint REST API upload
            # This requires authentication - using environment variables for credentials
            sharepoint_client_id = os.environ.get("SHAREPOINT_CLIENT_ID", "")
            sharepoint_client_secret = os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
            sharepoint_tenant_id = os.environ.get("SHAREPOINT_TENANT_ID", "")
            
            if not all([sharepoint_client_id, sharepoint_client_secret, sharepoint_tenant_id]):
                self._log("SharePoint credentials not configured, skipping upload")
                return None
            
            # Get access token
            token_url = f"https://accounts.accesscontrol.windows.net/{sharepoint_tenant_id}/tokens/OAuth/2"
            token_data = {
                "grant_type": "client_credentials",
                "client_id": f"{sharepoint_client_id}@{sharepoint_tenant_id}",
                "client_secret": sharepoint_client_secret,
                "resource": f"00000003-0000-0ff1-ce00-000000000000/{self.valves.sharepoint_site_url.split('//')[1].split('/')[0]}@{sharepoint_tenant_id}"
            }
            
            token_response = requests.post(token_url, data=token_data, timeout=10)
            if token_response.status_code != 200:
                self._log(f"SharePoint token request failed: {token_response.status_code}")
                return None
            
            access_token = token_response.json().get("access_token")
            if not access_token:
                self._log("Failed to get SharePoint access token")
                return None
            
            # Upload file
            folder_path = self.valves.sharepoint_folder.strip("/")
            upload_url = f"{self.valves.sharepoint_site_url}/_api/web/GetFolderByServerRelativeUrl('{folder_path}')/Files/Add(url='{filename}',overwrite=true)"
            
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json;odata=verbose",
                "Content-Type": "application/octet-stream"
            }
            
            upload_response = requests.post(upload_url, headers=headers, data=file_content, timeout=30)
            
            if upload_response.status_code in [200, 201]:
                file_url = f"{self.valves.sharepoint_site_url}/{folder_path}/{filename}"
                self._log(f"Successfully uploaded to SharePoint: {file_url}")
                return file_url
            else:
                self._log(f"SharePoint upload failed: {upload_response.status_code} - {upload_response.text[:200]}")
                return None
                
        except Exception as e:
            self._log(f"SharePoint upload error: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
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
            
            # Generate the file and get a download link
            report = self._build_report_from_conversation(messages, export_format)
            export_result = self._create_export_with_link(report, export_format)
            
            if export_result and export_result.get("success"):
                filename = export_result.get("filename", f"export.{export_format}")
                download_url = export_result.get("download_url", "")
                file_size = export_result.get("size_bytes", 0)
                file_size_kb = file_size // 1024
                
                self._log(f"Export file created: {filename} ({file_size_kb}KB)")
                
                # download_url is now a data URL (base64) - works directly in browser
                full_download_url = download_url
                
                # Modify user message to tell assistant about the download link
                instruction = (
                    f"\n\n[SYSTEM NOTE: The user requested to export this conversation to {export_format.upper()}. "
                    f"The file '{filename}' ({file_size_kb}KB) has been generated. "
                    f"IMPORTANT: Include this EXACT clickable download link in your response:\n"
                    f"**[📥 Download {filename}]({full_download_url})**\n"
                    f"Tell the user to click the link to download their file.]"
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
                
                # Store export info in metadata for outlet
                if "metadata" not in body:
                    body["metadata"] = {}
                body["metadata"]["export_file"] = {
                    "filename": filename,
                    "download_url": full_download_url,
                    "format": export_format,
                    "size": file_size
                }
            else:
                self._log("Failed to create export file in inlet")

        return body

    def stream(self, event: dict, __user__: Optional[dict] = None) -> dict:
        """
        Stream filter - passes through streaming output unchanged.
        This method is required by OpenWebUI but we don't modify streaming output.
        """
        return event

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
                    export_result = self._create_export_with_link(report, export_format)
                    
                    if export_result and export_result.get("success"):
                        export_file_info = {
                            "filename": export_result.get("filename", f"export.{export_format}"),
                            "download_url": export_result.get("download_url", ""),
                            "format": export_format,
                            "size": export_result.get("size_bytes", 0)
                        }
                        self._log(f"Export file created (fallback): {export_file_info['filename']}")
        
        # If we have file info (from inlet), ensure download link is in the response
        if export_file_info and messages:
            last_msg = messages[-1]
            filename = export_file_info.get("filename", "export_file")
            download_url = export_file_info.get("download_url", "")
            export_format = export_file_info.get("format", "pdf")
            file_size = export_file_info.get("size", 0)
            file_size_kb = file_size // 1024 if file_size else 0
            
            if download_url:
                content = self._extract_text_content(last_msg.get("content", ""))
                branding = self._get_branding_config()
                icon = self._get_document_icon(export_format)
                
                # Check if the download link is already in the response
                if download_url not in content:
                    # Add the download link
                    export_note = (
                        f"\n\n---\n"
                        f"{icon} **Your {export_format.upper()} Export is Ready!**\n\n"
                        f"**[📥 Click here to download {filename}]({download_url})**\n\n"
                        f"*File size: {file_size_kb}KB | Generated by {branding['company_name']}*"
                    )
                    
                    if isinstance(last_msg.get("content"), str):
                        last_msg["content"] = content + export_note
                    elif isinstance(last_msg.get("content"), list):
                        last_msg["content"].append({
                            "type": "text",
                            "text": export_note
                        })
                    
                    self._log(f"Added download link to response: {download_url}")
                else:
                    self._log(f"Download link already in response: {filename}")

        return body
