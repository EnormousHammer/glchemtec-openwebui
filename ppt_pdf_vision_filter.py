"""
title: PPT/PDF Vision Filter
author: GLChemTec
version: 8.0
description: Uses external glc-pptx-converter service for PPTX extraction + vision processing for PDFs.
"""

import os
import base64
import json
import tempfile
import shutil
import requests
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority (0 = highest)")
        enabled: bool = Field(default=True, description="Enable PPT/PDF vision processing")
        debug: bool = Field(default=True, description="Enable debug logging")
        
        # External PPTX Converter Service
        pptx_converter_url: str = Field(
            default="https://glc-pptx-converter.onrender.com",
            description="URL of the glc-pptx-converter service"
        )
        pptx_converter_timeout: int = Field(default=120, description="Timeout for PPTX converter (seconds)")
        
        # PDF Processing (fallback for PDFs)
        max_pages: int = Field(default=8, description="Max pages for PDF processing")
        dpi: int = Field(default=150, description="DPI for PDF rendering (higher = clearer text)")
        max_image_width: int = Field(default=1600, description="Max width in pixels (larger = more detail)")
        max_image_height: int = Field(default=1200, description="Max height in pixels (larger = more content)")
        jpeg_quality: int = Field(default=85, description="JPEG quality (0-100, higher = less compression)")
        max_total_base64_mb: float = Field(default=5.0, description="Max total base64 size in MB")

    def __init__(self):
        self.valves = self.Valves()

    def _log(self, msg: str) -> None:
        if self.valves.debug:
            print(f"[PPT-PDF-VISION] {msg}")

    def _extract_all_files(self, body: dict, messages: list) -> List[Dict[str, Any]]:
        """Extract files from all possible locations in the request."""
        all_files = []
        
        # Check body.files
        if isinstance(body.get("files"), list):
            self._log(f"Found {len(body['files'])} files in body['files']")
            all_files.extend(body["files"])
        
        # Check each message
        for msg in messages:
            if isinstance(msg.get("files"), list):
                self._log(f"Found {len(msg['files'])} files in message['files']")
                all_files.extend(msg["files"])
            if isinstance(msg.get("attachments"), list):
                self._log(f"Found {len(msg['attachments'])} files in message['attachments']")
                all_files.extend(msg["attachments"])
            if isinstance(msg.get("sources"), list):
                for source_obj in msg["sources"]:
                    if isinstance(source_obj, dict):
                        source = source_obj.get("source", {})
                        if source.get("type") == "file" and isinstance(source.get("file"), dict):
                            all_files.append({"file": source["file"]})
        
        # Deduplicate by path
        seen = set()
        unique = []
        for f in all_files:
            path = self._get_file_path(f)
            if path and path not in seen:
                seen.add(path)
                unique.append(f)
        
        self._log(f"Total unique files found: {len(unique)}")
        return unique

    def _get_file_path(self, file_obj: Dict[str, Any]) -> str:
        """Extract file path from various file object structures."""
        if not isinstance(file_obj, dict):
            return ""
        
        # Try file.path
        if isinstance(file_obj.get("file"), dict):
            f = file_obj["file"]
            path = f.get("path", "")
            if path:
                return path.strip()
            # Try file.meta.path
            if isinstance(f.get("meta"), dict):
                return f["meta"].get("path", "").strip()
        
        # Try direct path
        return file_obj.get("path", "").strip()

    def _get_file_name(self, file_obj: Dict[str, Any]) -> str:
        """Extract filename from various file object structures."""
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
        """Extract text from message content (handles string or list format)."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
            return "\n".join(p for p in parts if p).strip()
        return str(content) if content else ""

    def _is_openai_model(self, model: str) -> bool:
        """Check if model uses OpenAI format."""
        m = (model or "").lower()
        if not m:
            return True
        if "claude" in m or "anthropic" in m:
            return False
        return True  # Default to OpenAI format

    def _is_anthropic_model(self, model: str) -> bool:
        """Check if model is Anthropic/Claude."""
        m = (model or "").lower()
        return "claude" in m or "anthropic" in m

    def extract_pptx_via_service(self, file_path: str, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Send PPTX to glc-pptx-converter service and get extracted data.
        Returns dict with slides, text, images, etc.
        """
        try:
            url = f"{self.valves.pptx_converter_url}/api/extract/pptx"
            self._log(f"Sending PPTX to converter: {url}")
            self._log(f"File: {file_name}, Size: {os.path.getsize(file_path)} bytes")
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': (
                        file_name, 
                        f, 
                        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    )
                }
                response = requests.post(
                    url, 
                    files=files, 
                    timeout=self.valves.pptx_converter_timeout
                )
            
            if response.status_code == 200:
                data = response.json()
                self._log(f"PPTX extraction successful: {len(data.get('slides', []))} slides")
                return data
            else:
                # Log full error response (not truncated)
                error_text = response.text
                self._log(f"PPTX extraction failed: HTTP {response.status_code}")
                self._log(f"Full error response ({len(error_text)} chars): {error_text}")
                
                # Try to parse JSON error and extract diagnostics
                try:
                    error_json = response.json()
                    error_msg = error_json.get("error", "Unknown error")
                    diagnostics = error_json.get("diagnostics", {})
                    
                    self._log(f"Error message: {error_msg}")
                    if diagnostics:
                        self._log(f"Diagnostics: {json.dumps(diagnostics, indent=2)}")
                        
                        # Log LibreOffice-specific errors if present
                        if "libreoffice" in error_msg.lower() or "convert" in error_msg.lower():
                            self._log("=== LIBREOFFICE CONVERSION ERROR DETECTED ===")
                            self._log(f"Full error: {error_msg}")
                            if isinstance(diagnostics, dict):
                                for key, value in diagnostics.items():
                                    self._log(f"  {key}: {value}")
                except (json.JSONDecodeError, AttributeError):
                    # Not JSON, log as plain text
                    self._log(f"Non-JSON error response: {error_text}")
                
                return None
                
        except requests.exceptions.Timeout:
            self._log(f"PPTX extraction timeout after {self.valves.pptx_converter_timeout}s")
            return None
        except requests.exceptions.RequestException as e:
            self._log(f"PPTX extraction request error: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            self._log(f"PPTX extraction unexpected error: {type(e).__name__}: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None

    def _extract_image_from_shape(self, shape, slide_num: int) -> Optional[Dict[str, Any]]:
        """Extract image from a shape, handling various shape types."""
        try:
            # Direct image shape
            if hasattr(shape, "image"):
                image = shape.image
                image_bytes = image.blob
                
                # Convert to base64
                b64_data = base64.b64encode(image_bytes).decode("utf-8")
                
                # Determine mime type from image extension
                ext = image.ext
                if ext.lower() in ("png", ".png"):
                    mime_type = "image/png"
                elif ext.lower() in ("jpg", "jpeg", ".jpg", ".jpeg"):
                    mime_type = "image/jpeg"
                elif ext.lower() in ("gif", ".gif"):
                    mime_type = "image/gif"
                else:
                    mime_type = "image/png"  # Default
                
                return {
                    "data": b64_data,
                    "base64": b64_data,
                    "content_type": mime_type,
                    "slide_number": slide_num
                }
            
            # Picture shape (alternative attribute)
            if hasattr(shape, "image") or (hasattr(shape, "shape_type") and "picture" in str(shape.shape_type).lower()):
                try:
                    if hasattr(shape, "image"):
                        image = shape.image
                        image_bytes = image.blob
                        b64_data = base64.b64encode(image_bytes).decode("utf-8")
                        ext = getattr(image, "ext", "png")
                        if ext.lower() in ("png", ".png"):
                            mime_type = "image/png"
                        elif ext.lower() in ("jpg", "jpeg", ".jpg", ".jpeg"):
                            mime_type = "image/jpeg"
                        elif ext.lower() in ("gif", ".gif"):
                            mime_type = "image/gif"
                        else:
                            mime_type = "image/png"
                        return {
                            "data": b64_data,
                            "base64": b64_data,
                            "content_type": mime_type,
                            "slide_number": slide_num
                        }
                except Exception as e:
                    self._log(f"Slide {slide_num}: Error extracting from picture shape: {e}")
            
            return None
        except Exception as e:
            self._log(f"Slide {slide_num}: Error in _extract_image_from_shape: {e}")
            return None

    def _extract_images_recursive(self, shapes, slide_num: int) -> List[Dict[str, Any]]:
        """Recursively extract images from shapes, including grouped shapes."""
        images = []
        
        for shape in shapes:
            # Try to extract image from this shape
            img = self._extract_image_from_shape(shape, slide_num)
            if img:
                images.append(img)
                self._log(f"Slide {slide_num}: Extracted image ({len(img['base64']) * 3 // 4} bytes, {img['content_type']})")
            
            # If shape is a group, recursively extract from its shapes
            if hasattr(shape, "shapes"):
                try:
                    nested_images = self._extract_images_recursive(shape.shapes, slide_num)
                    images.extend(nested_images)
                except Exception as e:
                    self._log(f"Slide {slide_num}: Error extracting from grouped shape: {e}")
        
        return images

    def extract_pptx_fallback(self, file_path: str, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Fallback extraction using python-pptx when LibreOffice conversion fails.
        Extracts both text and images, returning data in the same format as the converter service.
        Enhanced to extract images from grouped shapes, backgrounds, and all shape types.
        """
        try:
            from pptx import Presentation
            
            self._log(f"Attempting fallback extraction using python-pptx for {file_name}")
            prs = Presentation(file_path)
            
            slides_data = []
            total_images = 0
            
            for idx, slide in enumerate(prs.slides, 1):
                slide_data = {
                    "slide_number": idx,
                    "title": "",
                    "text": [],
                    "notes": "",
                    "images": []
                }
                
                # Extract title
                if slide.shapes.title:
                    title = slide.shapes.title.text.strip()
                    if title:
                        slide_data["title"] = title
                
                # Extract text from all shapes
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text = shape.text.strip()
                        if text:
                            slide_data["text"].append(text)
                
                # Extract images recursively (handles grouped shapes)
                slide_images = self._extract_images_recursive(slide.shapes, idx)
                slide_data["images"].extend(slide_images)
                total_images += len(slide_images)
                
                # Try to extract background image if present
                try:
                    if hasattr(slide, "background") and slide.background:
                        bg = slide.background
                        if hasattr(bg, "fill") and hasattr(bg.fill, "picture"):
                            pic = bg.fill.picture
                            if hasattr(pic, "image"):
                                bg_image = pic.image
                                bg_bytes = bg_image.blob
                                bg_b64 = base64.b64encode(bg_bytes).decode("utf-8")
                                ext = bg_image.ext
                                if ext.lower() in ("png", ".png"):
                                    bg_mime = "image/png"
                                elif ext.lower() in ("jpg", "jpeg", ".jpg", ".jpeg"):
                                    bg_mime = "image/jpeg"
                                elif ext.lower() in ("gif", ".gif"):
                                    bg_mime = "image/gif"
                                else:
                                    bg_mime = "image/png"
                                
                                slide_data["images"].append({
                                    "data": bg_b64,
                                    "base64": bg_b64,
                                    "content_type": bg_mime,
                                    "slide_number": idx
                                })
                                total_images += 1
                                self._log(f"Slide {idx}: Extracted background image ({len(bg_bytes)} bytes, {bg_mime})")
                except Exception as bg_e:
                    # Background extraction is optional, don't fail if it doesn't work
                    pass
                
                # Extract notes
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_data["notes"] = notes
                
                slides_data.append(slide_data)
            
            result = {
                "slides": slides_data,
                "fallback_mode": True,
                "total_slides": len(slides_data),
                "total_images": total_images
            }
            
            self._log(f"Fallback extraction successful: {len(slides_data)} slides, {total_images} images")
            return result
            
        except ImportError:
            self._log("python-pptx not available for fallback extraction")
            return None
        except Exception as e:
            self._log(f"Fallback extraction failed: {type(e).__name__}: {e}")
            import traceback
            self._log(f"Traceback: {traceback.format_exc()}")
            return None

    def format_pptx_extraction(self, data: Dict[str, Any], file_name: str, include_image_refs: bool = True) -> str:
        """Format extracted PPTX data into natural, flowing text for the model."""
        slides = data.get("slides", [])
        if not slides:
            return f"Document: {file_name}\n\nNo content found in this presentation."
        
        # Build natural flowing text
        content_parts = []
        
        # Add document header
        content_parts.append(f"Document: {file_name}")
        content_parts.append(f"Total slides: {len(slides)}\n")
        
        # Combine all text content naturally
        all_text = []
        for slide in slides:
            slide_text = []
            slide_num = slide.get("slide_number", "?")
            
            # Add title if present
            title = slide.get("title", "").strip()
            if title:
                slide_text.append(title)
            
            # Add text content
            text_content = slide.get("text", [])
            if isinstance(text_content, list):
                for text in text_content:
                    if text and text.strip():
                        slide_text.append(text.strip())
            elif text_content and str(text_content).strip():
                slide_text.append(str(text_content).strip())
            
            # Add notes if present
            notes = slide.get("notes", "").strip()
            if notes:
                slide_text.append(f"(Note: {notes})")
            
            # Add tables as formatted text
            tables = slide.get("tables", [])
            for table in tables:
                if isinstance(table, list):
                    table_text = []
                    for row in table:
                        if isinstance(row, list):
                            table_text.append(" | ".join(str(cell) for cell in row))
                    if table_text:
                        slide_text.append("\n".join(table_text))
            
            # Add image references for source view
            if include_image_refs:
                images = slide.get("images", [])
                if images:
                    img_refs = [f"[Image {i+1} from slide {slide_num}]" for i in range(len(images))]
                    slide_text.append(" ".join(img_refs))
            
            # Combine slide content
            if slide_text:
                all_text.append("\n".join(slide_text))
        
        # Join all content with natural spacing
        if all_text:
            content_parts.append("\n\n".join(all_text))
        
        return "\n".join(content_parts)

    def download_image_to_base64(self, url: str) -> Optional[Dict[str, str]]:
        """Download image from URL and convert to base64."""
        try:
            self._log(f"Downloading image: {url[:80]}...")
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                self._log(f"Failed to download image: {response.status_code}")
                return None
            
            # Determine mime type
            content_type = response.headers.get("Content-Type", "image/png")
            if "jpeg" in content_type or "jpg" in content_type:
                mime_type = "image/jpeg"
            elif "png" in content_type:
                mime_type = "image/png"
            elif "gif" in content_type:
                mime_type = "image/gif"
            elif "webp" in content_type:
                mime_type = "image/webp"
            else:
                mime_type = "image/png"  # Default
            
            # Convert to base64
            b64_data = base64.b64encode(response.content).decode("utf-8")
            
            self._log(f"Downloaded image: {len(b64_data)//1024}KB as {mime_type}")
            return {"base64": b64_data, "mime_type": mime_type}
            
        except Exception as e:
            self._log(f"Error downloading image: {e}")
            return None

    def get_pptx_images_as_base64(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract images from PPTX extraction data - handles URLs and base64."""
        images = []
        total_size = 0
        max_bytes = int(self.valves.max_total_base64_mb * 1024 * 1024)
        
        for slide in data.get("slides", []):
            slide_num = slide.get("slide_number", "?")
            
            for img in slide.get("images", []):
                # Check total size limit
                if total_size > max_bytes:
                    self._log(f"Reached image size limit ({self.valves.max_total_base64_mb}MB), stopping")
                    break
                
                b64_data = None
                mime_type = "image/png"
                
                # Option 1: Image already has base64 data
                if img.get("data") or img.get("base64"):
                    b64_data = img.get("data") or img.get("base64")
                    mime_type = img.get("content_type", "image/png")
                    self._log(f"Slide {slide_num}: Using embedded base64 image")
                
                # Option 2: Image has URL - download it
                elif img.get("url"):
                    url = img.get("url")
                    downloaded = self.download_image_to_base64(url)
                    if downloaded:
                        b64_data = downloaded["base64"]
                        mime_type = downloaded["mime_type"]
                        self._log(f"Slide {slide_num}: Downloaded image from URL")
                
                # Option 3: Check for 'src' or 'path' as URL
                elif img.get("src") or img.get("path"):
                    url = img.get("src") or img.get("path")
                    if url.startswith("http"):
                        downloaded = self.download_image_to_base64(url)
                        if downloaded:
                            b64_data = downloaded["base64"]
                            mime_type = downloaded["mime_type"]
                            self._log(f"Slide {slide_num}: Downloaded image from src/path")
                
                if b64_data:
                    total_size += len(b64_data)
                    images.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_data}"
                        }
                    })
        
        self._log(f"Total images prepared: {len(images)}, size: {total_size//1024}KB")
        return images

    def convert_pdf_to_images(self, pdf_path: str, output_dir: str) -> List[str]:
        """Convert PDF pages to images (fallback for PDF files)."""
        try:
            from pdf2image import convert_from_path
            from PIL import Image
            
            self._log(f"Converting PDF with max_pages={self.valves.max_pages}")
            images = convert_from_path(
                pdf_path, 
                dpi=self.valves.dpi, 
                fmt="png",
                first_page=1, 
                last_page=self.valves.max_pages
            )
            
            paths = []
            total_size = 0
            max_bytes = int(self.valves.max_total_base64_mb * 1024 * 1024)
            
            for idx, img in enumerate(images):
                w, h = img.width, img.height
                max_w = self.valves.max_image_width
                max_h = self.valves.max_image_height
                
                scale = min(max_w / w, max_h / h, 1.0)
                if scale < 1.0:
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                
                path = os.path.join(output_dir, f"page_{idx+1:03d}.jpg")
                img = img.convert("RGB")
                img.save(path, "JPEG", quality=self.valves.jpeg_quality, optimize=True)
                
                file_size = os.path.getsize(path)
                total_size += file_size
                
                if total_size > max_bytes:
                    self._log(f"Stopping at page {idx+1} - size limit reached")
                    paths.append(path)
                    break
                
                paths.append(path)
            
            self._log(f"Created {len(paths)} PDF images")
            return paths
            
        except Exception as e:
            self._log(f"PDF->images error: {e}")
            return []

    def image_to_base64(self, path: str) -> Optional[str]:
        """Convert image file to base64 string."""
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except:
            return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """Main filter entry point - processes incoming requests."""
        self._log("=" * 60)
        self._log("INLET - PPT/PDF Vision Filter v8.0")
        self._log(f"Converter URL: {self.valves.pptx_converter_url}")

        if not self.valves.enabled:
            self._log("Filter is disabled")
            return body

        messages = body.get("messages", [])
        if not messages:
            self._log("No messages in request")
            return body

        # Log body structure for debugging
        self._log(f"Body keys: {list(body.keys())}")
        
        files = self._extract_all_files(body, messages)
        
        if not files:
            self._log("No files found in request")
            return body

        all_content = []  # Text content from extractions
        all_images = []   # Image blocks for vision

        model_name = body.get("model", "")
        use_openai_format = self._is_openai_model(model_name)
        self._log(f"Model: {model_name}, Format: {'OpenAI' if use_openai_format else 'Anthropic'}")

        for file_obj in files:
            file_path = self._get_file_path(file_obj)
            file_name = self._get_file_name(file_obj)
            
            self._log(f"Processing file: {file_name}")
            self._log(f"File path: {file_path}")

            if not file_path:
                self._log("No path found for file, skipping")
                continue
                
            if not os.path.exists(file_path):
                self._log(f"File does not exist: {file_path}")
                continue

            is_pptx = file_name.endswith((".ppt", ".pptx"))
            is_pdf = file_name.endswith(".pdf")

            if not (is_pptx or is_pdf):
                self._log(f"Skipping non-PPT/PDF file: {file_name}")
                continue

            # ========== PPTX PROCESSING ==========
            if is_pptx:
                self._log("Processing PPTX via external converter service")
                
                extracted = self.extract_pptx_via_service(file_path, file_name)
                
                if extracted:
                    # Add formatted text content
                    formatted_text = self.format_pptx_extraction(extracted, file_name)
                    all_content.append(formatted_text)
                    self._log(f"Added extracted text ({len(formatted_text)} chars)")
                    
                    # Add images if available
                    images = self.get_pptx_images_as_base64(extracted)
                    if images:
                        all_images.extend(images)
                        self._log(f"Added {len(images)} images from PPTX")
                    else:
                        self._log("WARNING: PPTX extraction succeeded but no images found")
                else:
                    self._log("PPTX extraction failed - attempting fallback extraction")
                    
                    # Try fallback extraction using python-pptx (text + images)
                    fallback_data = self.extract_pptx_fallback(file_path, file_name)
                    if fallback_data:
                        # Format and add text content
                        formatted_text = self.format_pptx_extraction(fallback_data, file_name)
                        all_content.append(formatted_text)
                        self._log(f"Added fallback text ({len(formatted_text)} chars)")
                        
                        # Add images if available
                        images = self.get_pptx_images_as_base64(fallback_data)
                        if images:
                            all_images.extend(images)
                            self._log(f"Added {len(images)} images from fallback extraction")
                        else:
                            self._log("Fallback extraction succeeded but no images found")
                    else:
                        # Both methods failed
                        self._log("Both primary and fallback extraction failed - no content available")
                        error_msg = (
                            f"[ERROR: PPTX conversion failed for {file_name}]\n"
                            f"The external converter service (glc-pptx-converter) was unable to extract content.\n"
                            f"Fallback extraction also failed.\n"
                            f"This is typically due to:\n"
                            f"- LibreOffice conversion failure (check converter logs for details)\n"
                            f"- Corrupted or unsupported PPTX file\n"
                            f"- File too large or contains unsupported elements\n"
                            f"Check the filter logs above for the full error message and diagnostics."
                        )
                        all_content.append(error_msg)

            # ========== PDF PROCESSING ==========
            elif is_pdf:
                self._log("Processing PDF via local image conversion")
                
                with tempfile.TemporaryDirectory() as tmp_dir:
                    image_paths = self.convert_pdf_to_images(file_path, tmp_dir)
                    
                    for img_path in image_paths:
                        b64 = self.image_to_base64(img_path)
                        if b64:
                            # Always use OpenAI format - OpenWebUI requires this format
                            all_images.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64}"
                                }
                            })
                    
                    self._log(f"Added {len(image_paths)} PDF page images")

        # ========== BUILD FINAL MESSAGE ==========
        if not all_content and not all_images:
            self._log("No content extracted from any files")
            return body

        self._log(f"Building message with {len(all_content)} text sections, {len(all_images)} images")

        last_message = messages[-1]
        original_prompt = self._extract_text_content(last_message.get("content", ""))

        # Build the combined message
        combined_text = f"{original_prompt}\n\n"
        
        if all_content:
            combined_text += "Document content:\n"
            combined_text += "\n\n".join(all_content)
            combined_text += "\n\n"
        
        if all_images:
            # Add image references in text so they appear in source view
            combined_text += f"Note: {len(all_images)} images from the document are attached below for visual analysis.\n\n"
            # Add image placeholders that will be matched with actual images
            for idx in range(len(all_images)):
                combined_text += f"[Image {idx+1} from document]\n"
            combined_text += "\n"
        
        # Natural, conversational prompt
        combined_text += (
            "Please analyze this document and provide a comprehensive, natural analysis. "
            "Write in a flowing, conversational style like you're explaining it to someone. "
            "For chemistry content (NMR, spectra, etc.), provide detailed analysis with peak tables. "
            "For presentations, provide a cohesive summary that flows naturally rather than listing slides. "
            "Focus on the key insights, findings, and important information."
        )

        # Build content blocks - interleave text and images so they appear together in source view
        content_blocks = [{"type": "text", "text": combined_text}]
        # Add images (no extra metadata - OpenWebUI doesn't allow unexpected keys)
        content_blocks.extend(all_images)
        
        messages[-1]["content"] = content_blocks
        body["messages"] = messages

        self._log(f"SUCCESS - Message updated with extracted content")
        self._log("=" * 60)
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """Output filter - passes through unchanged."""
        return body
