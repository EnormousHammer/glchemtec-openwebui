"""
Add proxy routes to OpenWebUI to forward /v1/export/* to proxy service.
"""
import httpx
from fastapi import Request
from starlette.responses import Response

def add_export_proxy_routes(webui_app):
    """Add proxy routes to OpenWebUI's FastAPI app."""
    try:
        @webui_app.get("/v1/export/{path:path}")
        @webui_app.post("/v1/export/{path:path}")
        async def proxy_export(request: Request, path: str):
            """Proxy requests to export service on localhost:8000."""
            proxy_url = "http://localhost:8000"
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
                    
                    response_headers = {k: v for k, v in proxy_response.headers.items() 
                                      if k.lower() not in ["connection", "transfer-encoding"]}
                    
                    return Response(
                        content=proxy_response.content,
                        status_code=proxy_response.status_code,
                        headers=response_headers,
                        media_type=proxy_response.headers.get("content-type")
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
