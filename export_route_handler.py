"""
Export route handler - registers /v1/export/* routes with OpenWebUI.
This file should be imported by OpenWebUI to add the proxy routes.
"""
import os
import aiohttp
from fastapi import Request  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore

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
        
        @app.get("/v1/export/download/{file_id}")
        async def webui_export_download(file_id: str, request: Request):
            """Forward download requests to proxy service."""
            # Use environment variable if set, otherwise default to 127.0.0.1
            proxy_url = os.environ.get("EXPORT_SERVICE_URL", "http://127.0.0.1:8000")
            url = f"{proxy_url}/v1/export/download/{file_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        return StreamingResponse(
                            iter([body.encode("utf-8")]),
                            status_code=resp.status,
                            media_type="text/plain",
                        )
                    
                    # Forward content-disposition + content-type so browser downloads properly
                    headers = {}
                    cd = resp.headers.get("Content-Disposition")
                    ct = resp.headers.get("Content-Type")
                    if cd:
                        headers["Content-Disposition"] = cd
                    if ct:
                        headers["Content-Type"] = ct
                    headers["Cache-Control"] = "no-store"
                    
                    async def streamer():
                        async for chunk in resp.content.iter_chunked(1024 * 256):  # 256KB chunks
                            yield chunk
                    
                    print(f"[EXPORT-ROUTES] ✅ Forwarding download: {file_id} ({resp.headers.get('Content-Type', 'unknown')})")
                    return StreamingResponse(streamer(), headers=headers)
        
        @app.post("/v1/export/create")
        async def webui_export_create(request: Request):
            """Forward create requests to proxy service."""
            # Use environment variable if set, otherwise default to 127.0.0.1
            proxy_url = os.environ.get("EXPORT_SERVICE_URL", "http://127.0.0.1:8000")
            url = f"{proxy_url}/v1/export/create"
            payload = await request.json()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.read()
                    print(f"[EXPORT-ROUTES] ✅ Forwarded create request: {resp.status}")
                    return StreamingResponse(
                        iter([data]),
                        status_code=resp.status,
                        media_type="application/json"
                    )
        
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
