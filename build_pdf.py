import os
import subprocess
import markdown
import fitz

with open('Briqen_Backend_Architecture_Submission.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Add page break right before Section 5
split_marker = '### 5. Retry vs. Deliberate Regeneration'
if split_marker in text:
    parts = text.split(split_marker)
    text_with_break = parts[0] + '<div style="page-break-before: always;"></div>\n\n' + split_marker + parts[1]
else:
    text_with_break = text

html_content = markdown.markdown(text_with_break, extensions=['tables', 'fenced_code'])

full_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<style>
  @page {{
    size: letter;
    margin: 0.32in 0.44in 0.32in 0.44in;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 8.05pt;
    line-height: 1.25;
    color: #1e293b;
    margin: 0;
    padding: 0;
  }}
  h1 {{
    font-size: 13pt;
    margin: 0 0 2px 0;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.2px;
  }}
  p {{
    margin: 2px 0 3px 0;
  }}
  hr {{
    display: none;
  }}
  h3 {{
    font-size: 8.8pt;
    margin: 5px 0 2px 0;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 1.5px;
    letter-spacing: 0.2px;
    text-transform: uppercase;
  }}
  pre {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 3px;
    padding: 3px 5px;
    font-size: 6.85pt;
    line-height: 1.13;
    margin: 2px 0 3px 0;
    font-family: 'Consolas', 'Courier New', monospace;
  }}
  code {{
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 7.4pt;
    background: #f1f5f9;
    padding: 0.5px 2px;
    border-radius: 2px;
    color: #0f172a;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 3px 0 4px 0;
    font-size: 7.45pt;
    line-height: 1.18;
  }}
  th, td {{
    border: 1px solid #cbd5e1;
    padding: 2px 4px;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    background-color: #f1f5f9;
    font-weight: 600;
    color: #0f172a;
  }}
  ol, ul {{
    margin: 2px 0 3px 14px;
    padding: 0;
  }}
  li {{
    margin-bottom: 1.5px;
  }}
  a {{
    color: #0284c7;
    text-decoration: none;
  }}
</style>
</head>
<body>
{html_content}
</body>
</html>'''

with open('temp_submission.html', 'w', encoding='utf-8') as f:
    f.write(full_html)

html_path = os.path.abspath('temp_submission.html')
pdf_path = os.path.abspath('Briqen_Backend_Architecture_Submission.pdf')
file_url = 'file:///' + html_path.replace('\\', '/')

edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
cmd = [edge_path, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={pdf_path}', file_url]
res = subprocess.run(cmd, capture_output=True, text=True)
print('Edge return code:', res.returncode)

doc = fitz.open(pdf_path)
print('FINAL VERIFIED PAGE COUNT:', doc.page_count)
for i in range(doc.page_count):
    page = doc[i]
    lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
    print(f'=== PAGE {i+1} ===')
    print(' First 3 lines:', lines[:3])
    print(' Last 3 lines:', lines[-3:])
