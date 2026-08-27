"""Generate high-quality, professional PDF documents for the AIPI project:
1. PS_COMPLIANCE_AUDIT.pdf
2. FRONTEND_API_GUIDE.pdf
3. API_DOCUMENTATION_SWAGGER.pdf
4. API_DOCUMENTATION_REDOC.pdf
"""
import html
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent

def markdown_to_styled_html(md_text: str, title: str) -> str:
    lines = md_text.splitlines()
    html_lines = []
    in_table = False
    in_code = False
    
    for line in lines:
        if line.startswith("```"):
            if in_code:
                html_lines.append("</code></pre>")
                in_code = False
            else:
                lang = line[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code = True
            continue
            
        if in_code:
            html_lines.append(html.escape(line))
            continue
            
        if line.startswith("|") and line.endswith("|"):
            parts = [p.strip() for p in line[1:-1].split("|")]
            if all(set(p).issubset({"-", ":", " "}) for p in parts if p):
                continue
            if not in_table:
                html_lines.append('<table><thead><tr>' + ''.join(f'<th>{p}</th>' for p in parts) + '</tr></thead><tbody>')
                in_table = True
            else:
                cells = []
                for p in parts:
                    if "✅" in p:
                        cells.append(f'<td><span class="badge-pass">{p}</span></td>')
                    elif "⚠️" in p or "Note" in p:
                        cells.append(f'<td><span class="badge-warn">{p}</span></td>')
                    else:
                        cells.append(f'<td>{p}</td>')
                html_lines.append('<tr>' + ''.join(cells) + '</tr>')
            continue
        else:
            if in_table:
                html_lines.append("</tbody></table>")
                in_table = False
                
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("#### "):
            html_lines.append(f"<h4>{line[5:]}</h4>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{line[2:]}</blockquote>")
        elif line.startswith("---"):
            html_lines.append("<hr/>")
        elif line.startswith("* ") or line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip():
            # Bold and inline code replacements
            txt = line
            txt = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', txt)
            txt = re.sub(r'`(.+?)`', r'<code>\1</code>', txt)
            html_lines.append(f"<p>{txt}</p>")
            
    if in_table:
        html_lines.append("</tbody></table>")
    if in_code:
        html_lines.append("</code></pre>")
        
    body_content = "\n".join(html_lines)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
  @page {{
    size: A4;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-right {{
      content: counter(page);
    }}
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
    color: #1f2937;
    background: #ffffff;
    font-size: 11pt;
  }}
  h1 {{ font-size: 20pt; color: #111827; border-bottom: 2px solid #3b82f6; padding-bottom: 6px; margin-top: 0; }}
  h2 {{ font-size: 14pt; color: #1e3a8a; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; margin-top: 18pt; page-break-after: avoid; }}
  h3 {{ font-size: 12pt; color: #1f2937; margin-top: 12pt; page-break-after: avoid; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12pt 0; font-size: 9.5pt; page-break-inside: avoid; }}
  th, td {{ border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; }}
  th {{ background: #f3f4f6; font-weight: 600; color: #111827; }}
  tr:nth-child(even) {{ background: #f9fafb; }}
  code {{ background: #f3f4f6; color: #b91c1c; padding: 1px 4px; border-radius: 3px; font-family: SFMono-Regular, Consolas, monospace; font-size: 9pt; }}
  pre {{ background: #1e293b; color: #f8fafc; padding: 10px 14px; border-radius: 6px; overflow: hidden; font-size: 8.5pt; line-height: 1.4; page-break-inside: avoid; }}
  pre code {{ background: transparent; color: inherit; padding: 0; }}
  blockquote {{ border-left: 4px solid #3b82f6; margin: 10pt 0; padding: 6px 12px; background: #eff6ff; color: #1e40af; border-radius: 0 4px 4px 0; }}
  li {{ margin-bottom: 3pt; }}
  hr {{ border: 0; height: 1px; background: #e5e7eb; margin: 16pt 0; }}
  .badge-pass {{ color: #059669; font-weight: 600; }}
  .badge-warn {{ color: #d97706; font-weight: 600; }}
</style>
</head>
<body>
{body_content}
</body>
</html>"""

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        
        # 1. PS Compliance Audit PDF
        audit_md = (BASE_DIR / "PS_COMPLIANCE_AUDIT.md").read_text(encoding="utf-8")
        audit_html = markdown_to_styled_html(audit_md, "AIPI — PS 26056 Full Compliance Audit")
        
        page = browser.new_page()
        page.set_content(audit_html)
        page.pdf(path=str(BASE_DIR / "PS_COMPLIANCE_AUDIT.pdf"), format="A4", print_background=True)
        page.pdf(path=str(BASE_DIR / "docs" / "PS_COMPLIANCE_AUDIT.pdf"), format="A4", print_background=True)
        print("Generated: PS_COMPLIANCE_AUDIT.pdf")
        
        # 2. Frontend API Guide PDF
        guide_md = (BASE_DIR / "FRONTEND_API_GUIDE.md").read_text(encoding="utf-8")
        guide_html = markdown_to_styled_html(guide_md, "AIPI API — Frontend Integration Guide & Contract")
        
        page.set_content(guide_html)
        page.pdf(path=str(BASE_DIR / "FRONTEND_API_GUIDE.pdf"), format="A4", print_background=True)
        page.pdf(path=str(BASE_DIR / "docs" / "FRONTEND_API_GUIDE.pdf"), format="A4", print_background=True)
        print("Generated: FRONTEND_API_GUIDE.pdf")
        
        # 3. Interactive Redoc Reference PDF (from local file)
        redoc_file = BASE_DIR / "api_docs_redoc.html"
        if redoc_file.exists():
            page.goto(f"file:///{redoc_file.resolve().as_posix()}", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.pdf(path=str(BASE_DIR / "API_DOCUMENTATION_REDOC.pdf"), format="A4", print_background=True)
            page.pdf(path=str(BASE_DIR / "docs" / "API_DOCUMENTATION_REDOC.pdf"), format="A4", print_background=True)
            print("Generated: API_DOCUMENTATION_REDOC.pdf")

        # 4. Interactive Swagger UI Reference PDF
        swagger_file = BASE_DIR / "api_docs_swagger.html"
        if swagger_file.exists():
            page.goto(f"file:///{swagger_file.resolve().as_posix()}", wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            page.pdf(path=str(BASE_DIR / "API_DOCUMENTATION_SWAGGER.pdf"), format="A4", print_background=True)
            page.pdf(path=str(BASE_DIR / "docs" / "API_DOCUMENTATION_SWAGGER.pdf"), format="A4", print_background=True)
            print("Generated: API_DOCUMENTATION_SWAGGER.pdf")
            
        browser.close()
        
    # Remove test file if exists
    test_pdf = BASE_DIR / "test.pdf"
    if test_pdf.exists():
        test_pdf.unlink()
        
    print("\nAll PDF documents successfully compiled and saved to workspace root and docs/!")

if __name__ == "__main__":
    main()
