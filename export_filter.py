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
            default="http://127.0.0.1:8000",
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
        # CRITICAL: Always ensure valves exists, even if init fails
        # This prevents OpenWebUI from crashing when introspecting filters
        try:
            # Get export service URL from env if set, otherwise use default
            # Use 127.0.0.1 instead of localhost for better compatibility
            export_url = os.environ.get("EXPORT_SERVICE_URL", "http://127.0.0.1:8000")
            # Get public URL for download links
            public_url = os.environ.get("WEBUI_URL", os.environ.get("PUBLIC_URL", ""))
            if not public_url:
                # Try to detect from common env vars
                public_url = os.environ.get("RENDER_EXTERNAL_URL", "")
            self.valves = self.Valves(export_service_url=export_url, public_base_url=public_url)
            # Force SharePoint export off regardless of env
            self.valves.enable_sharepoint = False
            
            # Try to register export routes with OpenWebUI
            try:
                import sys
                sys.path.insert(0, '/app/backend')
                try:
                    from export_route_handler import register_export_routes
                    # Try to find OpenWebUI's app
                    try:
                        import open_webui.api.app as app_module  # type: ignore
                        if hasattr(app_module, 'app'):
                            register_export_routes(app_module.app)
                            self._log("✅ Export routes registered via open_webui.api.app")
                    except:
                        try:
                            import open_webui.main as main_module  # type: ignore
                            if hasattr(main_module, 'app'):
                                register_export_routes(main_module.app)
                                self._log("✅ Export routes registered via open_webui.main")
                        except:
                            self._log("⚠️ Could not find OpenWebUI app to register routes (will retry on first request)")
                except ImportError:
                    self._log("⚠️ export_route_handler not found, routes may not be registered")
            except Exception as e:
                self._log(f"⚠️ Failed to register export routes: {e}")
            
            # Test proxy connectivity on init (non-blocking, just a warning)
            try:
                test_response = requests.get(f"{export_url}/health", timeout=2)
                if test_response.status_code == 200:
                    self._log(f"Export filter initialized - proxy reachable at {export_url}")
                else:
                    self._log(f"WARNING: Export proxy at {export_url} returned {test_response.status_code}")
            except requests.exceptions.ConnectionError:
                self._log(f"WARNING: Cannot connect to export proxy at {export_url} - exports may fail")
            except Exception:
                # Health endpoint might not exist, that's okay
                self._log(f"Export filter initialized (proxy: {export_url})")
            
            self._log(f"Export filter initialized (public_url: {public_url})")
        except Exception as e:
            # If initialization fails, disable the filter to prevent crashes
            print(f"[EXPORT-FILTER] ERROR in __init__: {e}")
            import traceback
            print(f"[EXPORT-FILTER] Traceback: {traceback.format_exc()}")
            # Create a minimal disabled filter - MUST succeed or OpenWebUI crashes
            try:
                self.valves = self.Valves(enabled=False)
            except Exception as e2:
                # Last resort - create with absolute minimum
                print(f"[EXPORT-FILTER] CRITICAL: Cannot create Valves - {e2}")
                # This should never happen, but if it does, we're in trouble
                raise
        # Patterns to detect export requests - more flexible patterns
        self.export_patterns = [
            # PDF patterns - more flexible
            r"export.*pdf",
            r"export.*to.*pdf",
            r"export.*as.*pdf",
            r"create.*pdf",
            r"make.*pdf",
            r"generate.*pdf",
            r"save.*pdf",
            r"download.*pdf",
            r"give.*pdf",
            r"pdf.*export",
            r"pdf.*file",
            r"pdf.*document",
            # Word/DOCX patterns - more flexible
            r"export.*word",
            r"export.*docx",
            r"export.*to.*word",
            r"export.*to.*docx",
            r"export.*as.*word",
            r"export.*as.*docx",
            r"create.*word",
            r"create.*docx",
            r"make.*word",
            r"make.*docx",
            r"generate.*word",
            r"generate.*docx",
            r"save.*word",
            r"save.*docx",
            r"download.*word",
            r"download.*docx",
            r"word.*export",
            r"docx.*export",
            r"word.*file",
            r"docx.*file",
        ]

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[EXPORT-FILTER] {msg}")

    def _detect_export_request(self, text: str) -> Optional[str]:
        """Detect if user is requesting an export and return format (word/pdf)."""
        text_lower = text.lower()
        self._log(f"Checking text for export request: {text_lower[:100]}")
        for pattern in self.export_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                matched = match.group(0)
                self._log(f"Matched pattern: {pattern} -> {matched}")
                if "word" in matched or "docx" in matched:
                    return "docx"
                elif "pdf" in matched:
                    return "pdf"
        self._log("No export pattern matched")
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

        self._log(f"Building report from {len(messages)} messages")
        current_section = None
        sections_added = 0
        total_content_chars = 0
        
        for msg in messages:
            role = msg.get("role", "")
            content = self._extract_text_content(msg.get("content", ""))
            
            if not content.strip():
                self._log(f"Skipping empty {role} message")
                continue

            content_len = len(content)
            total_content_chars += content_len
            self._log(f"Processing {role} message: {content_len} chars")

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
                sections_added += 1
                current_section = None
            elif role == "assistant" and not current_section:
                # Standalone assistant message
                report["sections"].append({
                    "heading": "Response",
                    "body": content,
                    "bullets": []
                })
                sections_added += 1

        self._log(f"Report built: {sections_added} sections, {total_content_chars} total characters")
        if sections_added == 0:
            self._log(f"WARNING: No sections added to report! Messages: {len(messages)}")
            # Add at least something so PDF isn't empty
            if messages:
                report["sections"].append({
                    "heading": "Conversation Export",
                    "body": "No content could be extracted from the conversation.",
                    "bullets": []
                })

        return report

    def _generate_export_file(self, report: Dict[str, Any], format_type: str) -> Optional[bytes]:
        """Generate export file (Word or PDF) via the proxy service."""
        try:
            url = f"{self.valves.export_service_url}/v1/report/{format_type}"
            self._log(f"Requesting export from: {url}")
            self._log(f"Report keys: {list(report.keys())}")
            
            # Make request with proper headers
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=report, headers=headers, timeout=60, stream=True)
            
            self._log(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                # Read content in chunks to avoid loading entire file into memory
                file_bytes = bytearray()
                for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                    if chunk:
                        file_bytes.extend(chunk)
                        # Safety check: limit to 50MB to prevent memory issues
                        if len(file_bytes) > 50 * 1024 * 1024:
                            self._log("ERROR: File too large (>50MB), stopping download")
                            return None
                
                self._log(f"Successfully received {len(file_bytes)} bytes")
                if len(file_bytes) == 0:
                    self._log("ERROR: Received empty file!")
                    return None
                return bytes(file_bytes)
            else:
                error_text = response.text[:500] if hasattr(response, 'text') else "No error details"
                self._log(f"Export failed: HTTP {response.status_code}")
                self._log(f"Error response: {error_text}")
                return None
        except requests.exceptions.ConnectionError as e:
            self._log(f"Connection error - proxy not reachable at {self.valves.export_service_url}: {e}")
            return None
        except requests.exceptions.Timeout as e:
            self._log(f"Request timeout after 60s: {e}")
            return None
        except Exception as e:
            self._log(f"Export error: {type(e).__name__}: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _create_export_with_link(self, report: Dict[str, Any], format_type: str, messages: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Create export file via proxy endpoint and return download link."""
        try:
            # Use the proxy's export/create endpoint which handles file storage and returns a download URL
            url = f"{self.valves.export_service_url}/v1/export/create"
            self._log(f"Requesting export creation from: {url}")
            
            payload = {
                "report": report,
                "format": format_type,
                "use_ai": False,  # Default to False - only enable if messages provided
                "model": "gpt-4o"  # Use gpt-4o for better quality
            }
            
            # Include conversation history for AI generation
            if messages and len(messages) > 0:
                payload["use_ai"] = True  # Enable AI only if we have messages
                # Convert messages to the format expected by OpenAI Responses API
                conversation_history = []
                for msg in messages:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    
                    # Convert content to Responses API format
                    if isinstance(content, str):
                        content_items = [{"type": "input_text", "text": content}]
                    elif isinstance(content, list):
                        content_items = []
                        for item in content:
                            if isinstance(item, dict):
                                # Already in Responses API format
                                content_items.append(item)
                            elif isinstance(item, str):
                                content_items.append({"type": "input_text", "text": item})
                    else:
                        content_items = [{"type": "input_text", "text": str(content)}]
                    
                    conversation_history.append({
                        "role": role,
                        "content": content_items
                    })
                
                payload["conversation"] = conversation_history
                self._log(f"Including {len(conversation_history)} messages for AI generation")
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers, timeout=120)  # Increased timeout for AI generation
            
            self._log(f"Export creation response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    # Get the download URL - must be publicly accessible from browser
                    file_id = result.get("file_id")
                    
                    # Proxy runs on localhost:8000 but Render only exposes port 8080
                    # So we MUST use public_base_url (OpenWebUI's public URL) for browser access
                    # The proxy endpoints are routed through OpenWebUI via backend_startup_hook.py
                    public_url = self.valves.public_base_url or os.environ.get("WEBUI_URL", "") or os.environ.get("PUBLIC_URL", "") or os.environ.get("RENDER_EXTERNAL_URL", "")
                    
                    if public_url:
                        # Use public URL - proxy routes are accessible via OpenWebUI's domain
                        # Routes should be registered via register_export_routes.py or export_route_handler.py
                        download_url = f"{public_url}/v1/export/download/{file_id}"
                        self._log(f"✅ Using public URL for download: {download_url}")
                        self._log(f"   File ID: {file_id}, Size: {result.get('size_bytes', 0)} bytes")
                    else:
                        # Fallback: try to construct from request (last resort)
                        # This won't work but at least we tried
                        download_url = f"http://127.0.0.1:8000/v1/export/download/{file_id}"
                        self._log(f"⚠️ WARNING: No public URL found - download will fail: {download_url}")
                        self._log(f"   Please set WEBUI_URL or PUBLIC_URL environment variable")
                        self._log(f"   File created but download link will not work without public URL")
                    
                    self._log(f"Export created: {result.get('filename')} (ID: {file_id}, URL: {download_url})")
                    
                    return {
                        "success": True,
                        "filename": result.get("filename", f"export.{format_type}"),
                        "size_bytes": result.get("size_bytes", 0),
                        "download_url": download_url,
                        "is_data_url": False
                    }
                else:
                    self._log(f"Export creation failed: {result}")
                    return None
            else:
                error_text = response.text[:500] if hasattr(response, 'text') else "No error details"
                self._log(f"Export creation failed: HTTP {response.status_code}")
                self._log(f"Error response: {error_text}")
                return None
            
        except requests.exceptions.ConnectionError as e:
            self._log(f"Connection error - proxy not reachable at {self.valves.export_service_url}: {e}")
            return None
        except requests.exceptions.Timeout as e:
            self._log(f"Request timeout after 60s: {e}")
            return None
        except Exception as e:
            self._log(f"Export creation error: {type(e).__name__}: {e}")
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
            self._log(f"Processing {len(messages)} messages for export")
            
            # Generate the file and get a download link
            # Build basic report structure (will be enhanced by AI if use_ai=True)
            report = self._build_report_from_conversation(messages, export_format)
            self._log(f"Report structure: title='{report.get('title')}', sections={len(report.get('sections', []))}")
            # Pass messages for AI generation
            export_result = self._create_export_with_link(report, export_format, messages)
            
            if export_result and export_result.get("success"):
                filename = export_result.get("filename", f"export.{export_format}")
                download_url = export_result.get("download_url", "")
                file_size = export_result.get("size_bytes", 0)
                file_size_kb = file_size // 1024
                
                self._log(f"Export file created: {filename} ({file_size_kb}KB)")
                
                # download_url is now a data URL (base64) - works directly in browser
                full_download_url = download_url
                
                # Store export info in metadata for outlet
                # DO NOT modify user message - let the AI respond naturally, then outlet adds download link
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
        
        # If we have file info (from inlet), ensure download link is in the ASSISTANT response
        if export_file_info and messages:
            # Find the last assistant message (like SharePoint filter does)
            last_assistant_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg
                    break
            
            if not last_assistant_msg:
                self._log("No assistant message found in outlet - cannot add download link")
                return body
            
            filename = export_file_info.get("filename", "export_file")
            download_url = export_file_info.get("download_url", "")
            export_format = export_file_info.get("format", "pdf")
            file_size = export_file_info.get("size", 0)
            file_size_kb = file_size // 1024 if file_size else 0
            
            if download_url:
                content = self._extract_text_content(last_assistant_msg.get("content", ""))
                branding = self._get_branding_config()
                icon = self._get_document_icon(export_format)
                
                # Check if the download link is already in the response
                if download_url not in content:
                    # Add the download link - provide both HTML button and direct link
                    # Use both formats for maximum compatibility
                    # Escape filename for HTML
                    safe_filename = filename.replace('"', '&quot;').replace("'", "&#39;")
                    export_note = (
                        f"\n\n---\n"
                        f"{icon} **Your {export_format.upper()} Export is Ready!**\n\n"
                        f"**Download:** [{filename}]({download_url})\n\n"
                        f"<a href=\"{download_url}\" download=\"{safe_filename}\" style=\"display: inline-block; padding: 8px 16px; background-color: {branding['primary_color']}; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; margin-top: 8px;\">📥 Download {safe_filename}</a>\n\n"
                        f"*File size: {file_size_kb}KB | Generated by {branding['company_name']}*\n"
                        f"*If the download doesn't start automatically, right-click the link above and select 'Save Link As'*"
                    )
                    
                    # Modify assistant message content (like SharePoint filter does)
                    if isinstance(last_assistant_msg.get("content"), str):
                        last_assistant_msg["content"] = [
                            {"type": "text", "text": content},
                            {"type": "text", "text": export_note}
                        ]
                    elif isinstance(last_assistant_msg.get("content"), list):
                        last_assistant_msg["content"].append({
                            "type": "text",
                            "text": export_note
                        })
                    else:
                        # Initialize as list if empty
                        last_assistant_msg["content"] = [
                            {"type": "text", "text": export_note}
                        ]
                    
                    self._log(f"✅ Added download link to assistant response: {download_url}")
                else:
                    self._log(f"Download link already in response: {filename}")
            else:
                self._log(f"WARNING: No download URL in export_file_info")

        return body
