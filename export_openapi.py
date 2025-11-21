#!/usr/bin/env python3
"""Export OpenAPI schema to JSON file for frontend team."""

import json
import sys
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    output_path = Path(__file__).parent / "openapi.json"
    
    # Get OpenAPI schema from FastAPI app
    openapi_schema = app.openapi()
    
    # Pretty print JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    
    print(f"✅ OpenAPI schema exported to: {output_path}")
    print(f"📄 Share this file with frontend team")
    print(f"🔗 They can import it to Postman, Insomnia, or use it with code generators")

