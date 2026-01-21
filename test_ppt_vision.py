"""
Test script for ppt_pdf_vision_filter.py
Tests the filter with a real PPTX file and saves detailed output.
"""
import os
import json
import sys
from datetime import datetime
from ppt_pdf_vision_filter import Filter

# Test file path
file_path = r"C:\APPLICATIONS MADE BY ME\WINDOWS\glchemtec_openwebui\test_files\GLCRCI-11062025R1 - Progress Update 05 - 11 Dec 2025 - rev 1.pptx"

# Output file
output_file = "test_output.txt"

def test_filter():
    """Run the filter and capture all output."""
    print(f"Testing PPT/PDF Vision Filter")
    print(f"File: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    print("=" * 80)
    
    # Create filter instance
    f = Filter()
    
    # Create test body (simulating OpenWebUI request)
    body = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "Analyze this presentation and extract all HPLC data, NMR spectra, and key findings."
            }
        ],
        "files": [
            {
                "path": file_path,
                "name": os.path.basename(file_path)
            }
        ],
    }
    
    print("\n=== INPUT BODY ===")
    print(json.dumps(body, indent=2, default=str))
    print("\n=== RUNNING FILTER ===")
    
    # Capture stdout
    import io
    from contextlib import redirect_stdout
    
    stdout_capture = io.StringIO()
    
    try:
        with redirect_stdout(stdout_capture):
            result = f.inlet(body)
        filter_output = stdout_capture.getvalue()
    except Exception as e:
        filter_output = f"ERROR: {e}\n{traceback.format_exc()}"
        result = body
    
    print(filter_output)
    
    # Analyze result
    print("\n=== RESULT ANALYSIS ===")
    messages = result.get("messages", [])
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "input_file": file_path,
        "file_exists": os.path.exists(file_path),
        "messages_count": len(messages),
        "last_message_role": messages[-1].get("role") if messages else None,
        "content_type": type(messages[-1].get("content")).__name__ if messages else None,
        "image_url_blocks": 0,
        "image_blocks": 0,
        "text_blocks": 0,
        "total_content_items": 0,
        "first_image_preview": None,
        "filter_logs": filter_output,
    }
    
    if messages:
        content = messages[-1].get("content", "")
        
        if isinstance(content, list):
            analysis["total_content_items"] = len(content)
            for idx, item in enumerate(content):
                if isinstance(item, dict):
                    item_type = item.get("type", "unknown")
                    if item_type == "text":
                        analysis["text_blocks"] += 1
                    elif item_type == "image_url":
                        analysis["image_url_blocks"] += 1
                        if not analysis["first_image_preview"]:
                            url = item.get("image_url", {}).get("url", "")
                            analysis["first_image_preview"] = {
                                "length": len(url),
                                "preview": url[:150] + ("..." if len(url) > 150 else ""),
                                "is_data_url": url.startswith("data:image")
                            }
                    elif item_type == "image":
                        analysis["image_blocks"] += 1
                        if not analysis["first_image_preview"]:
                            source = item.get("source", {})
                            data = source.get("data", "")
                            analysis["first_image_preview"] = {
                                "length": len(data),
                                "preview": data[:150] + ("..." if len(data) > 150 else ""),
                                "media_type": source.get("media_type", "unknown")
                            }
        elif isinstance(content, str):
            analysis["content_is_string"] = True
            analysis["content_length"] = len(content)
    
    # Save detailed output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("PPT/PDF VISION FILTER TEST OUTPUT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {analysis['timestamp']}\n")
        f.write(f"Test File: {file_path}\n")
        f.write(f"File Exists: {analysis['file_exists']}\n\n")
        
        f.write("=== FILTER LOGS ===\n")
        f.write(filter_output)
        f.write("\n\n")
        
        f.write("=== ANALYSIS ===\n")
        f.write(json.dumps(analysis, indent=2, default=str))
        f.write("\n\n")
        
        f.write("=== RESULT MESSAGE CONTENT (first 2000 chars) ===\n")
        if messages:
            content = messages[-1].get("content", "")
            if isinstance(content, list):
                for idx, item in enumerate(content[:3]):  # First 3 items
                    f.write(f"\n--- Content Item {idx} ---\n")
                    if isinstance(item, dict):
                        item_type = item.get("type", "unknown")
                        f.write(f"Type: {item_type}\n")
                        if item_type == "text":
                            text = item.get("text", "")[:500]
                            f.write(f"Text preview: {text}...\n")
                        elif item_type == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            f.write(f"URL length: {len(url)}\n")
                            f.write(f"URL preview: {url[:200]}...\n")
                        elif item_type == "image":
                            source = item.get("source", {})
                            data = source.get("data", "")
                            f.write(f"Data length: {len(data)}\n")
                            f.write(f"Media type: {source.get('media_type', 'unknown')}\n")
            else:
                f.write(str(content)[:2000])
        
        f.write("\n\n=== FULL RESULT BODY (truncated) ===\n")
        result_str = json.dumps(result, indent=2, default=str)
        # Truncate very long base64 strings
        if len(result_str) > 10000:
            result_str = result_str[:10000] + "\n... (truncated - see individual items above)"
        f.write(result_str)
    
    print("\n=== SUMMARY ===")
    print(f"Messages: {analysis['messages_count']}")
    print(f"Content type: {analysis['content_type']}")
    print(f"Total content items: {analysis['total_content_items']}")
    print(f"Text blocks: {analysis['text_blocks']}")
    print(f"Image URL blocks (OpenAI): {analysis['image_url_blocks']}")
    print(f"Image blocks (Claude): {analysis['image_blocks']}")
    
    if analysis['image_url_blocks'] > 0 or analysis['image_blocks'] > 0:
        print(f"\n[SUCCESS] Images were added to the message!")
        if analysis['first_image_preview']:
            print(f"First image preview: {analysis['first_image_preview']}")
    else:
        print(f"\n[WARNING] No images were added. Check filter logs above.")
        if "LibreOffice not found" in filter_output:
            print("  -> LibreOffice is not installed or not in PATH")
        if "No content extracted" in filter_output:
            print("  -> Conversion failed - check LibreOffice installation")
    
    print(f"\n=== Full output saved to: {output_file} ===")
    return analysis

if __name__ == "__main__":
    try:
        import traceback
        analysis = test_filter()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
