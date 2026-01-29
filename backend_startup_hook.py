"""
Add proxy routes to OpenWebUI to forward /v1/export/* to proxy service.
"""
import os
import httpx
from fastapi import Request
from starlette.responses import Response

def add_export_proxy_routes(webui_app):
    """Add proxy routes to OpenWebUI's FastAPI app."""
    try:
        # Register specific download route first (more specific = higher priority)
        @webui_app.get("/v1/export/download/{file_id}")
        async def proxy_export_download(request: Request, file_id: str):
            """Proxy download requests to export service on 127.0.0.1:8000."""
            proxy_url = os.environ.get("EXPORT_SERVICE_URL", "http://127.0.0.1:8000")
            target_url = f"{proxy_url}/v1/export/download/{file_id}"
            
            print(f"[EXPORT-PROXY] Proxying download: {file_id} -> {target_url}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    proxy_response = await client.get(target_url, follow_redirects=True)
                    
                    response_headers = {}
                    for k, v in proxy_response.headers.items():
                        if k.lower() not in ["connection", "transfer-encoding", "keep-alive"]:
                            response_headers[k] = v
                    
                    print(f"[EXPORT-PROXY] ✅ Download: {proxy_response.status_code}")
                    
                    return Response(
                        content=proxy_response.content,
                        status_code=proxy_response.status_code,
                        headers=response_headers,
                        media_type=proxy_response.headers.get("content-type")
                    )
                except Exception as e:
                    print(f"[EXPORT-PROXY] ❌ Download error: {e}")
                    return Response(content=f"Proxy error: {str(e)}", status_code=502)
        
        # Register generic export route for create and other endpoints
        @webui_app.get("/v1/export/{path:path}")
        @webui_app.post("/v1/export/{path:path}")
        async def proxy_export(request: Request, path: str):
            """Proxy requests to export service on 127.0.0.1:8000."""
            proxy_url = os.environ.get("EXPORT_SERVICE_URL", "http://127.0.0.1:8000")
            target_url = f"{proxy_url}/v1/export/{path}"
            if request.url.query_string:
                target_url += f"?{request.url.query_string}"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                body = await request.body() if request.method == "POST" else None
                headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "connection"]}
                
                try:
                    if request.method == "GET":
                        proxy_response = await client.get(target_url, headers=headers, follow_redirects=True)
                    else:
                        proxy_response = await client.post(target_url, content=body, headers=headers, follow_redirects=True)
                    
                    # CRITICAL: Preserve ALL headers, especially Content-Disposition for downloads
                    response_headers = {}
                    for k, v in proxy_response.headers.items():
                        # Skip hop-by-hop headers that shouldn't be forwarded
                        if k.lower() not in ["connection", "transfer-encoding", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "upgrade"]:
                            response_headers[k] = v
                    
                    # Ensure Content-Disposition is preserved (critical for file downloads)
                    content_disp = None
                    for header_name in ["content-disposition", "Content-Disposition"]:
                        if header_name in proxy_response.headers:
                            content_disp = proxy_response.headers[header_name]
                            response_headers["Content-Disposition"] = content_disp
                            break
                    
                    # Log for debugging
                    if content_disp:
                        print(f"[EXPORT-PROXY] ✅ Preserved Content-Disposition: {content_disp[:100]}...")
                    else:
                        print(f"[EXPORT-PROXY] ⚠️ WARNING: Content-Disposition header not found in proxy response!")
                        print(f"[EXPORT-PROXY] Available headers: {list(proxy_response.headers.keys())}")
                    
                    # Get content type
                    content_type = proxy_response.headers.get("content-type") or proxy_response.headers.get("Content-Type")
                    
                    return Response(
                        content=proxy_response.content,
                        status_code=proxy_response.status_code,
                        headers=response_headers,
                        media_type=content_type
                    )
                except Exception as e:
                    return Response(content=f"Proxy error: {str(e)}", status_code=502)
        
        print("[EXPORT-PROXY] ✅ Added proxy routes: /v1/export/* → localhost:8000")
        return True
        
    except Exception as e:
        print(f"[EXPORT-PROXY] ❌ Failed to add proxy routes: {e}")
        import traceback
        traceback.print_exc()
        return False

# Auto-run on import - try to find OpenWebUI's app and add routes
# This runs when OpenWebUI imports modules from /app/backend/
def register_routes():
    """Try multiple ways to register the routes."""
    routes_added = False
    
    # Method 1: Try open_webui.api.app
    try:
        import open_webui.api.app as app_module
        if hasattr(app_module, 'app'):
            if add_export_proxy_routes(app_module.app):
                print("[EXPORT-PROXY] ✅ Routes added via open_webui.api.app")
                routes_added = True
    except Exception as e:
        print(f"[EXPORT-PROXY] Method 1 failed: {e}")
    
    # Method 2: Try open_webui.main
    if not routes_added:
        try:
            import open_webui.main as main_module
            if hasattr(main_module, 'app'):
                if add_export_proxy_routes(main_module.app):
                    print("[EXPORT-PROXY] ✅ Routes added via open_webui.main")
                    routes_added = True
        except Exception as e:
            print(f"[EXPORT-PROXY] Method 2 failed: {e}")
    
    # Method 3: Try finding app in sys.modules
    if not routes_added:
        try:
            import sys
            for module_name in list(sys.modules.keys()):
                if 'open_webui' in module_name and 'app' in module_name:
                    module = sys.modules[module_name]
                    if hasattr(module, 'app'):
                        if add_export_proxy_routes(module.app):
                            print(f"[EXPORT-PROXY] ✅ Routes added via {module_name}")
                            routes_added = True
                            break
        except Exception as e:
            print(f"[EXPORT-PROXY] Method 3 failed: {e}")
    
    if not routes_added:
        print("[EXPORT-PROXY] ⚠️ Could not add routes - will retry on next import")

# Try immediately
register_routes()

# Also try on import (in case OpenWebUI loads later)
try:
    import open_webui.api.app as app_module
    if hasattr(app_module, 'app'):
        add_export_proxy_routes(app_module.app)
        print("[EXPORT-PROXY] ✅ Routes added via auto-import")
except ImportError:
    # OpenWebUI not loaded yet - will try again later
    pass
except Exception as e:
    print(f"[EXPORT-PROXY] ⚠️ Could not auto-add routes: {e}")
