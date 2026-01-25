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
    from fastapi import Request
    from starlette.responses import Response
    
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
        import open_webui.api.app as app_module
        if hasattr(app_module, 'app'):
            if add_export_proxy_routes(app_module.app):
                return True
    except Exception as e:
        pass
    
    # Method 2: Try open_webui.main
    try:
        import open_webui.main as main_module
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
    max_attempts = 30
    for i in range(max_attempts):
        if find_and_register_routes():
            print("[EXPORT-ROUTES] Routes registered successfully!")
            sys.exit(0)
        print(f"[EXPORT-ROUTES] Attempt {i+1}/{max_attempts}: OpenWebUI not ready yet, waiting...")
        time.sleep(2)
    
    print("[EXPORT-ROUTES] ⚠️ Failed to register routes after 30 attempts")
    sys.exit(1)
