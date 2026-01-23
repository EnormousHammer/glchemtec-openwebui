"""
title: SharePoint Import Filter
author: GLChemTec
version: 1.0
description: Import files from SharePoint for analysis in chat.
"""

import os
import re
import base64
import requests
import tempfile
from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=5, description="Filter priority (runs before file processing)")
        enabled: bool = Field(default=True, description="Enable SharePoint import")
        debug: bool = Field(default=True, description="Enable debug logging")
        
        # SharePoint Configuration
        sharepoint_site_url: str = Field(
            default="",
            description="SharePoint site URL (e.g., https://yourcompany.sharepoint.com/sites/YourSite)"
        )
        sharepoint_folder: str = Field(
            default="Documents",
            description="Default SharePoint folder to browse"
        )
        enable_sharepoint: bool = Field(
            default=False,
            description="Enable SharePoint integration"
        )

    def __init__(self):
        try:
            # Get SharePoint config from environment
            sharepoint_url = os.environ.get("SHAREPOINT_SITE_URL", "")
            sharepoint_folder = os.environ.get("SHAREPOINT_FOLDER", "Documents")
            enable_sp = os.environ.get("ENABLE_SHAREPOINT", "false").lower() == "true"
            
            self.valves = self.Valves(
                sharepoint_site_url=sharepoint_url or "",
                sharepoint_folder=sharepoint_folder,
                enable_sharepoint=enable_sp
            )
            self._log("SharePoint import filter initialized")
        except Exception as e:
            print(f"[SHAREPOINT-IMPORT] ERROR in __init__: {e}")
            import traceback
            print(f"[SHAREPOINT-IMPORT] Traceback: {traceback.format_exc()}")
            self.valves = self.Valves(enabled=False)
        
        # Patterns to detect SharePoint import requests
        self.import_patterns = [
            r"import\s+(?:from\s+)?sharepoint",
            r"load\s+(?:file|document)\s+(?:from\s+)?sharepoint",
            r"get\s+(?:file|document)\s+(?:from\s+)?sharepoint",
            r"download\s+(?:from\s+)?sharepoint",
            r"sharepoint\s+(?:file|document|import)",
            r"list\s+sharepoint\s+files",
            r"browse\s+sharepoint",
        ]

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[SHAREPOINT-IMPORT] {msg}")

    def _detect_import_request(self, text: str) -> bool:
        """Detect if user is requesting SharePoint file import."""
        text_lower = text.lower()
        for pattern in self.import_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _extract_filename_from_request(self, text: str) -> Optional[str]:
        """Extract filename from user request if specified."""
        # Look for patterns like "file.pdf", "document.docx", etc.
        patterns = [
            r'["\']([^"\']+\.(pdf|docx|pptx|xlsx|png|jpg|jpeg))["\']',
            r'(\w+\.(pdf|docx|pptx|xlsx|png|jpg|jpeg))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _get_graph_token(self) -> Optional[str]:
        """Get Microsoft Graph API access token using Azure AD credentials."""
        try:
            client_id = os.environ.get("SHAREPOINT_CLIENT_ID", "")
            client_secret = os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
            tenant_id = os.environ.get("SHAREPOINT_TENANT_ID", "")
            
            if not all([client_id, client_secret, tenant_id]):
                self._log("SharePoint credentials not configured")
                return None
            
            # Use Microsoft Graph API (v1.0) - same as glc_assistant
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            
            token_data = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default"
            }
            
            response = requests.post(token_url, data=token_data, timeout=10)
            if response.status_code != 200:
                self._log(f"Token request failed: {response.status_code} - {response.text[:200]}")
                return None
            
            token_data = response.json()
            return token_data.get("access_token")
            
        except Exception as e:
            self._log(f"Error getting Graph API token: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None

    def _list_sharepoint_files(self, folder_path: str = None) -> List[Dict[str, Any]]:
        """List files in SharePoint using Microsoft Graph API (matching glc_assistant implementation)."""
        try:
            token = self._get_graph_token()
            if not token:
                return []
            
            # Use Microsoft Graph API - same approach as glc_assistant
            # First, get the site ID from the site URL
            site_url = self.valves.sharepoint_site_url
            if not site_url:
                self._log("SharePoint site URL not configured")
                return []
            
            # Extract site hostname and path
            # Format: https://tenant.sharepoint.com/sites/SiteName
            site_host = site_url.split("//")[1].split("/")[0] if "//" in site_url else ""
            site_path = "/" + "/".join(site_url.split("//")[1].split("/")[1:]) if "//" in site_url else ""
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
            
            # Get site by hostname and path (Graph API)
            site_api_url = f"https://graph.microsoft.com/v1.0/sites/{site_host}:{site_path}"
            site_response = requests.get(site_api_url, headers=headers, timeout=15)
            
            if site_response.status_code != 200:
                self._log(f"Failed to get site: {site_response.status_code}")
                return []
            
            site_data = site_response.json()
            site_id = site_data.get("id")
            
            if not site_id:
                self._log("Failed to get site ID")
                return []
            
            # Get default document library (drive)
            drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            drives_response = requests.get(drives_url, headers=headers, timeout=15)
            
            if drives_response.status_code != 200:
                self._log(f"Failed to get drives: {drives_response.status_code}")
                return []
            
            drives_data = drives_response.json()
            drives = drives_data.get("value", [])
            
            if not drives:
                self._log("No document libraries found")
                return []
            
            # Use first drive (default document library)
            drive_id = drives[0].get("id")
            
            # Build folder path
            folder = folder_path or self.valves.sharepoint_folder
            folder = folder.strip("/")
            
            # Get items from drive root or specific folder
            if folder:
                # Search for folder first
                search_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
                items_response = requests.get(search_url, headers=headers, timeout=15)
                
                if items_response.status_code == 200:
                    items_data = items_response.json()
                    items = items_data.get("value", [])
                    
                    # Find the folder
                    folder_item = None
                    for item in items:
                        if item.get("name") == folder and item.get("folder"):
                            folder_item = item
                            break
                    
                    if folder_item:
                        folder_id = folder_item.get("id")
                        items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
                    else:
                        items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
                else:
                    items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
            else:
                items_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
            
            # Get files
            files_response = requests.get(items_url, headers=headers, timeout=15)
            if files_response.status_code != 200:
                self._log(f"Failed to list files: {files_response.status_code}")
                return []
            
            files_data = files_response.json()
            items = files_data.get("value", [])
            
            files = []
            for item in items:
                if not item.get("folder"):  # Only files, not folders
                    files.append({
                        "id": item.get("id"),
                        "name": item.get("name", ""),
                        "size": item.get("size", 0),
                        "download_url": item.get("@microsoft.graph.downloadUrl", ""),
                        "web_url": item.get("webUrl", ""),
                        "modified": item.get("lastModifiedDateTime", ""),
                        "mime_type": item.get("file", {}).get("mimeType", "") if item.get("file") else ""
                    })
            
            self._log(f"Found {len(files)} files in SharePoint (Graph API)")
            return files
            
        except Exception as e:
            self._log(f"Error listing SharePoint files: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return []

    def _download_sharepoint_file(self, file_id: str, drive_id: str, filename: str, download_url: str = None) -> Optional[str]:
        """Download file from SharePoint using Microsoft Graph API (matching glc_assistant implementation)."""
        try:
            token = self._get_graph_token()
            if not token:
                return None
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "*/*"
            }
            
            # Use Graph API to download file content (same as glc_assistant)
            if file_id and drive_id:
                # Preferred: Use Graph API endpoint
                graph_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/content"
                response = requests.get(graph_url, headers=headers, timeout=60, stream=True)
            elif download_url:
                # Fallback: Use direct download URL
                response = requests.get(download_url, headers=headers, timeout=60, stream=True)
            else:
                self._log("No file ID or download URL provided")
                return None
            
            if response.status_code != 200:
                self._log(f"Failed to download file: {response.status_code}")
                return None
            
            # Save to uploads directory
            upload_dir = os.environ.get("UPLOAD_DIR", "/app/backend/data/uploads")
            if not os.path.exists(upload_dir):
                for alt_dir in ["/app/uploads", "/app/data/uploads", "/tmp"]:
                    if os.path.exists(alt_dir):
                        upload_dir = alt_dir
                        break
                else:
                    upload_dir = tempfile.gettempdir()
            
            # Create unique filename to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(filename)[0]
            ext = os.path.splitext(filename)[1]
            local_filename = f"sharepoint_{base_name}_{timestamp}{ext}"
            local_path = os.path.join(upload_dir, local_filename)
            
            # Download and save
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(local_path)
            self._log(f"Downloaded file from SharePoint: {local_filename} ({file_size} bytes)")
            
            return local_path
            
        except Exception as e:
            self._log(f"Error downloading SharePoint file: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Input filter - detects SharePoint import requests and downloads files.
        """
        self._log("Inlet called")
        if not self.valves.enabled or not self.valves.enable_sharepoint:
            self._log("Filter disabled or SharePoint not enabled, skipping")
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        # Check the last user message for SharePoint import requests
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            return body

        user_content = ""
        if isinstance(last_user_msg.get("content"), str):
            user_content = last_user_msg.get("content", "")
        elif isinstance(last_user_msg.get("content"), list):
            for item in last_user_msg.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    user_content += item.get("text", "") + " "

        if not self._detect_import_request(user_content):
            return body

        self._log(f"SharePoint import request detected: {user_content[:100]}")

        # Extract filename if specified
        filename = self._extract_filename_from_request(user_content)
        
        if filename:
            # Download specific file
            self._log(f"Downloading specific file: {filename}")
            
            # List files to find the one matching
            files = self._list_sharepoint_files()
            target_file = None
            
            # Also need to get drive ID for downloads
            site_url = self.valves.sharepoint_site_url
            if site_url:
                try:
                    token = self._get_graph_token()
                    if token:
                        site_host = site_url.split("//")[1].split("/")[0] if "//" in site_url else ""
                        site_path = "/" + "/".join(site_url.split("//")[1].split("/")[1:]) if "//" in site_url else ""
                        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                        site_api_url = f"https://graph.microsoft.com/v1.0/sites/{site_host}:{site_path}"
                        site_response = requests.get(site_api_url, headers=headers, timeout=15)
                        if site_response.status_code == 200:
                            site_data = site_response.json()
                            site_id = site_data.get("id")
                            if site_id:
                                drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
                                drives_response = requests.get(drives_url, headers=headers, timeout=15)
                                if drives_response.status_code == 200:
                                    drives_data = drives_response.json()
                                    drives = drives_data.get("value", [])
                                    if drives:
                                        drive_id = drives[0].get("id")
                                        for f in files:
                                            f["drive_id"] = drive_id
                except Exception as e:
                    self._log(f"Error getting drive ID: {e}")
            
            for f in files:
                if f["name"].lower() == filename.lower():
                    target_file = f
                    break
            
            if target_file:
                # Get drive ID from site (needed for Graph API download)
                drive_id = target_file.get("drive_id", "")
                file_id = target_file.get("id", "")
                download_url = target_file.get("download_url", "")
                
                local_path = self._download_sharepoint_file(file_id, drive_id, target_file["name"], download_url)
                if local_path:
                    # Add file to message for processing
                    if "files" not in last_user_msg:
                        last_user_msg["files"] = []
                    
                    file_obj = {
                        "file": {
                            "path": local_path,
                            "name": target_file["name"],
                            "size": target_file["size"],
                            "meta": {
                                "path": local_path,
                                "filename": target_file["name"],
                                "source": "sharepoint"
                            }
                        }
                    }
                    last_user_msg["files"].append(file_obj)
                    self._log(f"Added SharePoint file to message: {target_file['name']}")
                    
                    # Add instruction to assistant
                    instruction = (
                        f"\n\n[SYSTEM NOTE: User requested to import file '{target_file['name']}' from SharePoint. "
                        f"The file has been downloaded and is attached for analysis.]"
                    )
                    
                    if isinstance(last_user_msg.get("content"), str):
                        last_user_msg["content"] = user_content + instruction
                    elif isinstance(last_user_msg.get("content"), list):
                        last_user_msg["content"].append({
                            "type": "text",
                            "text": instruction
                        })
            else:
                # File not found - list available files
                self._log(f"File '{filename}' not found in SharePoint")
                files = self._list_sharepoint_files()
                if files:
                    file_list = "\n".join([f"- {f['name']} ({f['size']//1024}KB)" for f in files[:10]])
                    instruction = (
                        f"\n\n[SYSTEM NOTE: File '{filename}' not found in SharePoint. "
                        f"Available files:\n{file_list}\n"
                        f"Please ask the user which file they want to import.]"
                    )
                    if isinstance(last_user_msg.get("content"), str):
                        last_user_msg["content"] = user_content + instruction
                    elif isinstance(last_user_msg.get("content"), list):
                        last_user_msg["content"].append({
                            "type": "text",
                            "text": instruction
                        })
        else:
            # List files for user to choose
            self._log("Listing SharePoint files for user selection")
            files = self._list_sharepoint_files()
            
            if files:
                file_list = "\n".join([f"- {f['name']} ({f['size']//1024}KB)" for f in files[:20]])
                instruction = (
                    f"\n\n[SYSTEM NOTE: User requested to browse SharePoint files. "
                    f"Available files:\n{file_list}\n"
                    f"Please ask the user which file(s) they want to import for analysis.]"
                )
                if isinstance(last_user_msg.get("content"), str):
                    last_user_msg["content"] = user_content + instruction
                elif isinstance(last_user_msg.get("content"), list):
                    last_user_msg["content"].append({
                        "type": "text",
                        "text": instruction
                    })
            else:
                instruction = (
                    f"\n\n[SYSTEM NOTE: No files found in SharePoint folder '{self.valves.sharepoint_folder}'. "
                    f"Please inform the user.]"
                )
                if isinstance(last_user_msg.get("content"), str):
                    last_user_msg["content"] = user_content + instruction
                elif isinstance(last_user_msg.get("content"), list):
                    last_user_msg["content"].append({
                        "type": "text",
                        "text": instruction
                    })

        return body

    def stream(self, event: dict, __user__: Optional[dict] = None) -> dict:
        """
        Stream filter - passes through streaming output unchanged.
        This method is required by OpenWebUI but we don't modify streaming output.
        """
        return event

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """Output filter - injects SharePoint browser iframe when user requests to browse."""
        if not self.valves.enabled or not self.valves.enable_sharepoint:
            return body
        
        messages = body.get("messages", [])
        if not messages:
            return body
        
        # Check if user requested to browse SharePoint
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break
        
        if not last_user_msg:
            return body
        
        user_text = ""
        if isinstance(last_user_msg.get("content"), str):
            user_text = last_user_msg.get("content", "")
        elif isinstance(last_user_msg.get("content"), list):
            for item in last_user_msg.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    user_text += item.get("text", "") + " "
        
        # Check if user wants to browse (not download specific file)
        browse_keywords = ["browse sharepoint", "show sharepoint files", "list sharepoint", "sharepoint browser", "open sharepoint", "import from sharepoint"]
        wants_browse = any(keyword in user_text.lower() for keyword in browse_keywords)
        
        # Only show browser if no specific file was requested
        has_specific_file = self._extract_filename_from_request(user_text) is not None
        
        if wants_browse and not has_specific_file:
            # Get the proxy URL (where SharePoint browser is served)
            # Use relative path - proxy should be on same domain
            proxy_url = "/sharepoint-browser"
            
            # Create HTML iframe to embed SharePoint browser in chat
            browser_html = f"""
<div style="width: 100%; max-width: 100%; margin: 20px 0; border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; overflow: hidden; background: #0f1419;">
    <div style="padding: 15px; background: #1a1f2e; border-bottom: 1px solid rgba(255,255,255,0.1);">
        <h3 style="margin: 0; color: #fff; font-size: 16px;">📂 SharePoint File Browser</h3>
        <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 12px;">Browse and select files from SharePoint</p>
    </div>
    <iframe 
        src="{proxy_url}" 
        style="width: 100%; height: 600px; border: none; display: block;"
        title="SharePoint File Browser"
        allow="clipboard-read; clipboard-write"
    ></iframe>
</div>
<p style="color: #94a3b8; font-size: 12px; margin-top: 10px;">
    💡 <strong>Tip:</strong> Click on a file to select it, then click "Import Selected" to add it to your chat.
</p>
"""
            
            # Find the last assistant message and inject the browser
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    
                    # If content is a string, convert to list format
                    if isinstance(content, str):
                        msg["content"] = [
                            {"type": "text", "text": content},
                            {"type": "text", "text": browser_html}
                        ]
                    elif isinstance(content, list):
                        # Add browser HTML as text block
                        msg["content"].append({"type": "text", "text": browser_html})
                    else:
                        # Initialize as list
                        msg["content"] = [
                            {"type": "text", "text": browser_html}
                        ]
                    
                    self._log("✅ Injected SharePoint browser iframe into chat response")
                    break
        
        return body
