"""
Register export proxy routes with OpenWebUI after it starts.
This script runs continuously and tries to register routes when OpenWebUI is ready.
"""
import time
import sys
import os
sys.path.insert(0, '/app/backend')

try:
    from export_route_handler import register_export_routes
except ImportError:
    # Fallback to inline implementation
    import httpx
    from fastapi import Request  # type: ignore
    from starlette.responses import Response  # type: ignore
    
    def register_export_routes(app):
        """Register export proxy routes with OpenWebUI's FastAPI app."""
        try:
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
                        return Response(content=f"Proxy error: {str(e)}", status_code=502)
            
            print("[EXPORT-ROUTES] ✅ Successfully registered /v1/export/* routes")
            return True
        except Exception as e:
            print(f"[EXPORT-ROUTES] ❌ Failed to register routes: {e}")
            return False

def add_export_proxy_routes(webui_app):
    """Add proxy routes to OpenWebUI's FastAPI app."""
    try:
        # Check if routes already exist
        for route in webui_app.routes:
            if hasattr(route, 'path') and route.path == "/v1/export/{path:path}":
                print("[EXPORT-ROUTES] Routes already registered, skipping")
                return True
        
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
                    
                    # CRITICAL: Preserve ALL headers, especially Content-Disposition for downloads
                    response_headers = {}
                    for k, v in proxy_response.headers.items():
                        # Skip hop-by-hop headers that shouldn't be forwarded
                        if k.lower() not in ["connection", "transfer-encoding", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "upgrade"]:
                            response_headers[k] = v
                    
                    # Ensure Content-Disposition is preserved (critical for file downloads)
                    if "content-disposition" not in {h.lower() for h in response_headers.keys()}:
                        # If proxy didn't set it, try to get it from response
                        if "content-disposition" in proxy_response.headers:
                            response_headers["Content-Disposition"] = proxy_response.headers["content-disposition"]
                    
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
        
        print("[EXPORT-ROUTES] ✅ Successfully added proxy routes: /v1/export/* → localhost:8000")
        return True
        
    except Exception as e:
        print(f"[EXPORT-ROUTES] ❌ Failed to add proxy routes: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_and_register_routes():
    """Try to find OpenWebUI's app and register routes."""
    # Method 1: Try open_webui.api.app
    try:
        import open_webui.api.app as app_module  # type: ignore
        if hasattr(app_module, 'app'):
            if add_export_proxy_routes(app_module.app):
                return True
    except Exception as e:
        pass
    
    # Method 2: Try open_webui.main
    try:
        import open_webui.main as main_module  # type: ignore
        if hasattr(main_module, 'app'):
            if add_export_proxy_routes(main_module.app):
                return True
    except Exception as e:
        pass
    
    # Method 3: Search sys.modules
    try:
        import sys
        for module_name in list(sys.modules.keys()):
            if 'open_webui' in module_name.lower():
                module = sys.modules[module_name]
                if hasattr(module, 'app'):
                    if add_export_proxy_routes(module.app):
                        return True
    except Exception as e:
        pass
    
    return False

if __name__ == "__main__":
    print("[EXPORT-ROUTES] Starting route registration script...")
    max_attempts = 60  # Increased to 60 attempts (2 minutes total)
    for i in range(max_attempts):
        if find_and_register_routes():
            print("[EXPORT-ROUTES] ✅ Routes registered successfully!")
            # Keep running to retry if routes get lost (OpenWebUI might restart)
            print("[EXPORT-ROUTES] Monitoring for route registration...")
            while True:
                time.sleep(30)  # Check every 30 seconds
                # Verify routes still exist
                try:
                    import open_webui.api.app as app_module  # type: ignore
                    if hasattr(app_module, 'app'):
                        routes_exist = any('/v1/export' in str(route.path) for route in app_module.app.routes if hasattr(route, 'path'))
                        if not routes_exist:
                            print("[EXPORT-ROUTES] ⚠️ Routes lost, re-registering...")
                            find_and_register_routes()
                except:
                    pass
        print(f"[EXPORT-ROUTES] Attempt {i+1}/{max_attempts}: OpenWebUI not ready yet, waiting...")
        time.sleep(2)
    
    print("[EXPORT-ROUTES] ⚠️ Failed to register routes after 60 attempts - continuing anyway (filter will retry)")
    # Don't exit - let the filter try to register on first request
    while True:
        time.sleep(60)  # Keep trying periodically
        find_and_register_routes()
