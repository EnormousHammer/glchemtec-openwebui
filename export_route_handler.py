"""
Export route handler - registers /v1/export/* routes with OpenWebUI.
This file should be imported by OpenWebUI to add the proxy routes.
"""
import httpx
from fastapi import Request
from starlette.responses import Response

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
