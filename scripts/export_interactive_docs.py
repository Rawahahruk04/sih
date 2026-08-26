"""Generate standalone, portable interactive Swagger UI and Redoc HTML files with embedded openapi.json.
These files can be emailed, shared, or opened directly in any browser with zero backend needed.
"""
import json
from pathlib import Path

openapi_data = json.loads(Path("openapi.json").read_text(encoding="utf-8"))
openapi_json_str = json.dumps(openapi_data)

# Standalone Swagger UI HTML file with embedded OpenAPI specification
swagger_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIPI API Documentation — Interactive Swagger UI</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css" />
  <style>
    body {{ margin: 0; padding: 0; background: #fafafa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .top-banner {{ background: #1b1f23; color: white; padding: 14px 28px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .top-banner h2 {{ margin: 0; font-size: 16px; font-weight: 600; }}
    .top-banner span {{ font-size: 13px; color: #a0aec0; }}
    #swagger-ui {{ max-width: 1200px; margin: 20px auto; padding: 0 16px; }}
    .swagger-ui .info {{ margin: 20px 0; }}
  </style>
</head>
<body>
  <div class="top-banner">
    <h2>AIPI API — Airfare Price Index for India (Interactive Documentation)</h2>
    <span>Standalone Portable Document · SIH 2026 PS 26056</span>
  </div>
  <div id="swagger-ui"></div>

  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
  <script>
    const spec = {openapi_json_str};
    window.onload = () => {{
      window.ui = SwaggerUIBundle({{
        spec: spec,
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        defaultModelsExpandDepth: 3,
        defaultModelExpandDepth: 3,
        docExpansion: 'list',
        showExtensions: true,
        showCommonExtensions: true
      }});
    }};
  </script>
</body>
</html>"""

# Standalone Redoc HTML file with 3-column developer layout
redoc_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIPI API — Developer API Reference</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
  </style>
</head>
<body>
  <div id="redoc-container"></div>
  <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
  <script>
    const spec = {openapi_json_str};
    Redoc.init(spec, {{
      scrollYOffset: 50,
      expandResponses: 'all',
      requiredPropsFirst: true,
      sortPropsAlphabetically: false,
      showObjectSchemaExamples: true
    }}, document.getElementById('redoc-container'));
  </script>
</body>
</html>"""

Path("api_docs_swagger.html").write_text(swagger_html, encoding="utf-8")
Path("docs/api_docs_swagger.html").write_text(swagger_html, encoding="utf-8")
Path("api_docs_redoc.html").write_text(redoc_html, encoding="utf-8")
Path("docs/api_docs_redoc.html").write_text(redoc_html, encoding="utf-8")
print("Standalone Interactive API docs created: api_docs_swagger.html & api_docs_redoc.html")
