"""
title: Document Export Filter
author: GLChemTec
version: 1.5
description: Detects export requests and generates Word/PDF files. Uses server download URLs.
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

# Register export proxy routes with OpenWebUI when this filter loads
# This ensures /v1/export/* routes are available for file downloads
try:
    import backend_startup_hook
    print("[EXPORT-FILTER] ✅ Export proxy routes registered")
except ImportError:
    try:
        # Try alternative path
        import sys
        sys.path.insert(0, '/app/backend')
        import backend_startup_hook
        print("[EXPORT-FILTER] ✅ Export proxy routes registered (alt path)")
    except Exception as e:
        print(f"[EXPORT-FILTER] ⚠️ Could not register export routes: {e}")


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
        # Patterns to detect export requests - more flexible patterns with typo tolerance
        self.export_patterns = [
            # PDF patterns - with typo tolerance for "export" (wxport, expotr, exprot, etc.)
            r"[ewx]xport.*pdf",
            r"exp[oar]rt.*pdf",
            r"export.*pdf",
            r"export.*to.*pdf",
            r"export.*as.*pdf",
            r"[ewx]xport.*to.*pdf",
            r"[ewx]xport.*as.*pdf",
            r"create.*pdf",
            r"make.*pdf",
            r"generate.*pdf",
            r"save.*pdf",
            r"download.*pdf",
            r"give.*pdf",
            r"pdf.*export",
            r"pdf.*file",
            r"pdf.*document",
            r"convert.*pdf",
            r"to\s+pdf",
            r"as\s+pdf",
            # Word/DOCX patterns - with typo tolerance
            r"[ewx]xport.*word",
            r"[ewx]xport.*docx",
            r"exp[oar]rt.*word",
            r"exp[oar]rt.*docx",
            r"export.*word",
            r"export.*docx",
            r"export.*to.*word",
            r"export.*to.*docx",
            r"export.*as.*word",
            r"export.*as.*docx",
            r"[ewx]xport.*to.*word",
            r"[ewx]xport.*to.*docx",
            r"[ewx]xport.*as.*word",
            r"[ewx]xport.*as.*docx",
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
            r"convert.*word",
            r"convert.*docx",
            r"to\s+word",
            r"to\s+docx",
            r"as\s+word",
            r"as\s+docx",
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
        
        # Log section details for debugging
        for i, sec in enumerate(report.get("sections", [])):
            heading = sec.get("heading", "")[:50]
            body_len = len(sec.get("body", ""))
            self._log(f"  Section {i+1}: '{heading}...' ({body_len} chars)")
        
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
    
    def _create_export_with_link(self, report: Dict[str, Any], format_type: str, messages: Optional[List[Dict[str, Any]]] = None, __user__: Optional[dict] = None) -> Optional[Dict[str, Any]]:
        """Create export file via proxy endpoint and return download link."""
        try:
            # Use the proxy's export/create endpoint which handles file storage and returns a download URL
            url = f"{self.valves.export_service_url}/v1/export/create"
            self._log(f"Requesting export creation from: {url}")
            
            # Just render the conversation directly - no separate AI call needed
            # The conversation is already formatted by whatever model the user is chatting with
            payload = {
                "report": report,
                "format": format_type,
                "use_ai": False  # Never use separate AI - just render the conversation as-is
            }
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers, timeout=120)  # Increased timeout for AI generation
            
            self._log(f"Export creation response: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self._log(f"Export response keys: {list(result.keys())}")
                if result.get("success"):
                    file_id = result.get("file_id")
                    filename = result.get("filename", f"export.{format_type}")
                    size_bytes = result.get("size_bytes", 0)
                    mime_type = result.get("mime_type", "application/octet-stream")
                    
                    # Check if file bytes are included directly (preferred - no second request needed)
                    file_bytes_b64 = result.get("file_bytes_b64")
                    self._log(f"file_bytes_b64 present: {bool(file_bytes_b64)}, length: {len(file_bytes_b64) if file_bytes_b64 else 0}")
                    
                    if file_bytes_b64:
                        # Decode file bytes (for size calculation)
                        file_bytes = base64.b64decode(file_bytes_b64)
                        
                        # NOTE: We skip uploading to OpenWebUI's file system because it causes
                        # a self-referential HTTP request that deadlocks the server on Render.
                        # The service tries to POST to itself, which times out and can crash.
                        # Instead, we use data URLs which work reliably for most file sizes.
                        
                        # Create data URL (works reliably, no self-referential request)
                        data_url = f"data:{mime_type};base64,{file_bytes_b64}"
                        self._log(f"✅ Created data URL for download ({size_bytes} bytes)")
                        
                        return {
                            "success": True,
                            "file_id": file_id,
                            "filename": filename,
                            "size_bytes": size_bytes,
                            "download_url": data_url,
                            "is_data_url": True
                        }
                    else:
                        # Fallback: construct download URL (may not work if routes aren't registered)
                        public_url = self.valves.public_base_url or os.environ.get("WEBUI_URL", "") or os.environ.get("PUBLIC_URL", "") or os.environ.get("RENDER_EXTERNAL_URL", "")
                        
                        if public_url:
                            download_url = f"{public_url}/v1/export/download/{file_id}"
                            self._log(f"Using public URL for download: {download_url}")
                        else:
                            download_url = f"http://127.0.0.1:8000/v1/export/download/{file_id}"
                            self._log(f"⚠️ WARNING: No public URL found - download may fail")
                        
                        return {
                            "success": True,
                            "file_id": file_id,
                            "filename": filename,
                            "size_bytes": size_bytes,
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

    def _upload_to_openwebui(self, file_bytes: bytes, filename: str, mime_type: str, __user__: Optional[dict] = None) -> Optional[str]:
        """
        Upload file to OpenWebUI's native file system and return download URL.
        This is the most reliable way to serve files to users.
        """
        try:
            # Get the public URL for OpenWebUI
            public_url = self.valves.public_base_url or os.environ.get("WEBUI_URL", "") or os.environ.get("RENDER_EXTERNAL_URL", "")
            if not public_url:
                self._log("No public URL configured, cannot upload to OpenWebUI")
                return None
            
            # OpenWebUI's file upload endpoint
            upload_url = f"{public_url}/api/v1/files/"
            
            # Get user token if available (needed for authenticated upload)
            user_token = None
            if __user__ and isinstance(__user__, dict):
                user_token = __user__.get("token") or __user__.get("api_key")
            
            # Prepare multipart form data
            files = {
                'file': (filename, io.BytesIO(file_bytes), mime_type)
            }
            
            headers = {}
            if user_token:
                headers["Authorization"] = f"Bearer {user_token}"
            
            self._log(f"Uploading {filename} ({len(file_bytes)} bytes) to OpenWebUI: {upload_url}")
            
            response = requests.post(upload_url, files=files, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                file_id = result.get("id")
                if file_id:
                    # Construct download URL using OpenWebUI's file endpoint
                    download_url = f"{public_url}/api/v1/files/{file_id}/content"
                    self._log(f"✅ Uploaded to OpenWebUI: {download_url}")
                    return download_url
                else:
                    self._log(f"Upload succeeded but no file ID returned: {result}")
                    return None
            else:
                self._log(f"OpenWebUI upload failed: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            self._log(f"OpenWebUI upload error: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Input filter - detects export requests and generates files BEFORE assistant responds.
        Returns immediate assistant response with download link, preventing LLM call.
        """
        self._log("Inlet called")
        if not self.valves.enabled:
            self._log("Filter disabled, skipping")
            return body

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages in body")
            return body

        # 1) Detect export request from the last user message
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            return body

        user_content = self._extract_text_content(last_user_msg.get("content", ""))
        export_format = self._detect_export_request(user_content)

        if not export_format:
            return body  # normal flow

        self._log(f"Export request detected in inlet: {export_format.upper()}")
        self._log(f"Processing {len(messages)} messages for export")
        
        # 2) Build report from messages (existing logic)
        report = self._build_report_from_conversation(messages, export_format)
        self._log(f"Report structure: title='{report.get('title')}', sections={len(report.get('sections', []))}")
        
        # 3) Create export via proxy (existing logic)
        export_result = self._create_export_with_link(report, export_format, messages, __user__)
        
        if export_result and export_result.get("success"):
            download_url = export_result.get("download_url", "")
            filename = export_result.get("filename", f"export.{export_format}")
            file_size = export_result.get("size_bytes", 0)
            file_size_kb = file_size // 1024 if file_size else 0
            is_data_url = export_result.get("is_data_url", False)
            
            self._log(f"✅ Export file created: {filename} ({file_size_kb}KB, data_url={is_data_url})")
            
            # Store export info in metadata for outlet to use
            if "metadata" not in body:
                body["metadata"] = {}
            body["metadata"]["export_file"] = {
                "filename": filename,
                "download_url": download_url,
                "format": export_format,
                "size": file_size,
                "is_data_url": is_data_url,
                "handled_by_inlet": True  # Flag to prevent outlet from creating duplicate
            }
            
            safe_filename = filename.replace('"', '&quot;').replace("'", "&#39;")
            
            # Since OpenWebUI doesn't render HTML in responses, we need to use markdown
            # For data URLs, we'll provide instructions and the raw link
            # The user can copy-paste the link or we can try the server URL
            
            if is_data_url:
                # Data URLs contain the entire file - they work without server routes
                # But they're very long, so we need to handle them carefully
                self._log(f"Using data URL directly for download (length: {len(download_url)} chars)")
                
                # Store the data URL in metadata so outlet can use it
                body["metadata"]["export_file"]["data_url"] = download_url
                
                # For the AI response, we'll use a simpler message
                # The outlet will add the actual download link with proper HTML
                last_user_msg["content"] = (
                    f"{user_content}\n\n"
                    f"[SYSTEM: Export file has been created successfully ({file_size_kb}KB {export_format.upper()}). "
                    f"Respond with ONLY: '✅ Your {export_format.upper()} export is ready! Click the download button below.']"
                )
            else:
                # For server URLs, use simple markdown link
                last_user_msg["content"] = (
                    f"{user_content}\n\n"
                    f"[SYSTEM: Export has been created successfully. "
                    f"Respond with ONLY this exact message, nothing else:\n\n"
                    f"✅ **Export Ready!**\n\n"
                    f"📥 **[Click here to download {safe_filename}]({download_url})**\n\n"
                    f"*File size: {file_size_kb}KB | Format: {export_format.upper()}*]"
                )
            
            self._log(f"✅ Modified user message with server download link")
        else:
            # Modify user message to tell AI export failed
            last_user_msg["content"] = (
                f"{user_content}\n\n"
                f"[SYSTEM: Export failed. Respond with: "
                f"❌ Export failed. Please try again or contact support.]"
            )
            self._log("❌ Export creation failed, added error instruction")

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

        # Check if we have export file info from inlet (metadata may not persist between inlet/outlet)
        export_file_info = None
        if isinstance(body.get("metadata"), dict):
            export_file_info = body["metadata"].get("export_file")
            if export_file_info:
                self._log(f"Found export_file_info from inlet metadata: {export_file_info.get('filename')}")
        
        # Check if the assistant response already contains a download indicator
        # This prevents duplicate processing
        last_assistant_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                last_assistant_msg = msg
                break
        
        if last_assistant_msg:
            assistant_content = self._extract_text_content(last_assistant_msg.get("content", ""))
            # Check if export was already handled (look for our export markers)
            if "Export is Ready" in assistant_content or "export is ready" in assistant_content or "Click to Download" in assistant_content:
                self._log("Export already in assistant response, skipping outlet processing")
                return body
        
        # If no metadata from inlet, check if this is an export request (fallback)
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
                    export_result = self._create_export_with_link(report, export_format, None, __user__)
                    
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
                # For data URLs, check for filename instead (data URLs are too long to search)
                is_data_url = download_url.startswith("data:")
                already_has_link = (filename in content) or ("Click to Download" in content) or (not is_data_url and download_url in content)
                
                if not already_has_link:
                    # Escape filename for HTML/markdown
                    safe_filename = filename.replace('"', '&quot;').replace("'", "&#39;")
                    
                    if is_data_url:
                        # For data URLs, use HTML with download attribute
                        # This creates a clickable button that triggers file download
                        export_note = (
                            f"\n\n---\n"
                            f"{icon} **Your {export_format.upper()} Export is Ready!**\n\n"
                            f"<a href=\"{download_url}\" download=\"{safe_filename}\" "
                            f"style=\"display:inline-block;padding:12px 24px;background-color:{branding['primary_color']};"
                            f"color:white;text-decoration:none;border-radius:6px;font-weight:bold;cursor:pointer;\">"
                            f"📥 Click to Download {safe_filename}</a>\n\n"
                            f"*File size: {file_size_kb}KB | Format: {export_format.upper()} | Generated by {branding['company_name']}*\n\n"
                            f"*If the button doesn't work, right-click and select 'Save link as...'*"
                        )
                    else:
                        # For server URLs, use simple markdown link (more compatible)
                        export_note = (
                            f"\n\n---\n"
                            f"{icon} **Your {export_format.upper()} Export is Ready!**\n\n"
                            f"📥 **[Click here to download {safe_filename}]({download_url})**\n\n"
                            f"*File size: {file_size_kb}KB | Format: {export_format.upper()} | Generated by {branding['company_name']}*"
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
                    
                    # Log without the full data URL (too long)
                    url_preview = download_url[:100] + "..." if len(download_url) > 100 else download_url
                    self._log(f"✅ Added download link to assistant response: {url_preview}")
                else:
                    self._log(f"Download link already in response: {filename}")
            else:
                self._log(f"WARNING: No download URL in export_file_info")

        return body
