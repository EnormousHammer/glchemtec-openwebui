"""
Local test script that can work with PDFs directly (skips PPT conversion)
or tests the full pipeline if LibreOffice is available.
"""
import os
import json
import sys
from datetime import datetime
from ppt_pdf_vision_filter import Filter

# Test file - can be PPTX or PDF
test_file = r"C:\APPLICATIONS MADE BY ME\WINDOWS\glchemtec_openwebui\test_files\GLCRCI-11062025R1 - Progress Update 05 - 11 Dec 2025 - rev 1.pptx"

# Check if we have a PDF version for direct testing
pdf_file = test_file.replace(".pptx", ".pdf").replace(".ppt", ".pdf")
use_pdf_directly = os.path.exists(pdf_file)

def test_filter():
    """Run the filter and capture all output."""
    print(f"Testing PPT/PDF Vision Filter (Local)")
    print(f"Original file: {test_file}")
    print(f"File exists: {os.path.exists(test_file)}")
    
    if use_pdf_directly:
        print(f"\n[INFO] Found PDF version - testing PDF->images directly (skips LibreOffice)")
        test_path = pdf_file
    else:
        print(f"\n[INFO] Testing full pipeline: PPT->PDF->images (requires LibreOffice)")
        test_path = test_file
    
    print("=" * 80)
    
    # Create filter instance
    f = Filter()
    
    # Create test body
    body = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": "Analyze this document and extract all HPLC data, NMR spectra, and key findings."
            }
        ],
        "files": [
            {
                "path": test_path,
                "name": os.path.basename(test_path)
            }
        ],
    }
    
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
        import traceback
        filter_output = f"ERROR: {e}\n{traceback.format_exc()}"
        result = body
    
    print(filter_output)
    
    # Analyze result
    print("\n=== RESULT ANALYSIS ===")
    messages = result.get("messages", [])
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "input_file": test_path,
        "file_exists": os.path.exists(test_path),
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
        elif isinstance(content, str):
            analysis["content_is_string"] = True
            analysis["content_length"] = len(content)
    
    # Save detailed output
    output_file = "test_output_local.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("PPT/PDF VISION FILTER - LOCAL TEST OUTPUT\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Timestamp: {analysis['timestamp']}\n")
        f.write(f"Test File: {test_path}\n")
        f.write(f"File Exists: {analysis['file_exists']}\n")
        f.write(f"Mode: {'PDF Direct' if use_pdf_directly else 'Full Pipeline (PPT->PDF)'}\n\n")
        
        f.write("=== FILTER LOGS ===\n")
        f.write(filter_output)
        f.write("\n\n")
        
        f.write("=== ANALYSIS ===\n")
        f.write(json.dumps(analysis, indent=2, default=str))
        f.write("\n\n")
        
        if messages:
            content = messages[-1].get("content", "")
            if isinstance(content, list):
                f.write("=== CONTENT ITEMS ===\n")
                for idx, item in enumerate(content[:5]):  # First 5 items
                    f.write(f"\n--- Item {idx} ---\n")
                    if isinstance(item, dict):
                        f.write(f"Type: {item.get('type', 'unknown')}\n")
                        if item.get("type") == "text":
                            text = item.get("text", "")[:500]
                            f.write(f"Text: {text}...\n")
                        elif item.get("type") == "image_url":
                            url = item.get("image_url", {}).get("url", "")
                            f.write(f"URL length: {len(url)}\n")
                            f.write(f"URL preview: {url[:200]}...\n")
    
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
            prev = analysis['first_image_preview']
            print(f"First image: {prev.get('length', 0)} chars, data URL: {prev.get('is_data_url', False)}")
    else:
        print(f"\n[WARNING] No images were added.")
        if "LibreOffice not found" in filter_output:
            print("  -> LibreOffice is not installed or not working")
            print("  -> TIP: Test with a PDF file directly to skip PPT conversion")
        if "No content extracted" in filter_output:
            print("  -> Conversion or image generation failed")
    
    print(f"\n=== Full output saved to: {output_file} ===")
    return analysis

if __name__ == "__main__":
    try:
        analysis = test_filter()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
