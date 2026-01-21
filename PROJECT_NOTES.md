# Project Notes and Configuration

## Render API Configuration

**API Key**: `rnd_v09UaSigC2P2SF4yRIeZ7fC4RmMB`  
**Service Name**: `glchemtec-openwebui`  
**Service ID**: `srv-d5li9q7gi27c738ts6ug`

## Log Retrieval Script

The project includes `get_render_logs.py` which can automatically:
- Connect to Render API
- Retrieve service logs
- Analyze for errors and issues
- Categorize problems (import errors, filter issues, etc.)

**Usage:**
```bash
python get_render_logs.py
```

The script automatically uses the configured API key and service ID.

## Export Filter

The export filter (`export_filter.py`) is currently:
- ✅ Tested and working locally
- ⚠️ Temporarily disabled in Dockerfile (commented out)
- Ready to be re-enabled once 500 error is resolved

## Current Issues

1. **500 Internal Server Error** - OpenWebUI not starting
   - Export filter temporarily disabled
   - Need to check actual error in Render logs
   - Use `get_render_logs.py` to retrieve and analyze logs

2. **Filter Loading** - Filters may not be loading correctly
   - Check OpenWebUI logs for filter initialization messages
   - Verify filter files are in correct locations

## Files Added

- `get_render_logs.py` - Automated log retrieval and analysis
- `test_export_filter.py` - Local testing script for export filter
- `EXPORT_FILTER_SETUP.md` - Complete setup guide
- `GET_LOGS_INSTRUCTIONS.md` - How to use log retrieval
- `RENDER_API_KEY.md` - API key storage (in .gitignore)
- `DEBUG_500_ERROR.md` - Debugging guide for 500 errors

## Next Steps

1. Run `python get_render_logs.py` to get actual error
2. Fix the root cause of 500 error
3. Re-enable export filter in Dockerfile
4. Test export functionality
