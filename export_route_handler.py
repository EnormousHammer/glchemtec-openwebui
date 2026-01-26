"""
Export route handler - registers /v1/export/* routes with OpenWebUI.
This file should be imported by OpenWebUI to add the proxy routes.
"""
import os
import httpx
from fastapi import Request  # type: ignore
from starlette.responses import Response  # type: ignore

_ROUTES_REGISTERED = False

def register_export_routes(app):
    """Register export proxy routes with OpenWebUI's FastAPI app."""
    global _ROUTES_REGISTERED
    
    if _ROUTES_REGISTERED:
        return True
    
    try:
        # Check if routes already exist
        for route in app.routes:
            if hasattr(route, 'path') and '/v1/export' in str(route.path):
                print("[EXPORT-ROUTES] Routes already exist, skipping")
                _ROUTES_REGISTERED = True
                return True
        
        @app.get("/v1/export/{path:path}")
        @app.post("/v1/export/{path:path}")
        async def proxy_export(request: Request, path: str):
            """Proxy requests to export service on 127.0.0.1:8000."""
            # Use environment variable if set, otherwise default to 127.0.0.1
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
                        print(f"[EXPORT-ROUTES] ✅ Preserved Content-Disposition: {content_disp[:100]}...")
                    else:
                        print(f"[EXPORT-ROUTES] ⚠️ WARNING: Content-Disposition header not found in proxy response!")
                        print(f"[EXPORT-ROUTES] Available headers: {list(proxy_response.headers.keys())}")
                    
                    # Get content type
                    content_type = proxy_response.headers.get("content-type") or proxy_response.headers.get("Content-Type")
                    
                    return Response(
                        content=proxy_response.content,
                        status_code=proxy_response.status_code,
                        headers=response_headers,
                        media_type=content_type
                    )
                except Exception as e:
                    print(f"[EXPORT-ROUTES] Proxy error: {e}")
                    return Response(content=f"Proxy error: {str(e)}", status_code=502)
        
        print("[EXPORT-ROUTES] ✅ Successfully registered /v1/export/* routes")
        _ROUTES_REGISTERED = True
        return True
        
    except Exception as e:
        print(f"[EXPORT-ROUTES] ❌ Failed to register routes: {e}")
        import traceback
        traceback.print_exc()
        return False

# Try to auto-register if OpenWebUI app is available
try:
    import open_webui.api.app as app_module
    if hasattr(app_module, 'app'):
        register_export_routes(app_module.app)
except:
    pass
