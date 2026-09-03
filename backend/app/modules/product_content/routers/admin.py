from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

ADMIN_HTML = """<!doctype html><html><head><title>Product Content</title>
<style>body{font:15px system-ui;margin:2rem}a{margin-right:1rem}</style></head><body>
<h1>Product Content Administration</h1><nav><a href="#types">Content Types</a>
<a href="#languages">Languages</a><a href="#dashboard">Dashboard</a>
<a href="#library">Content Library</a><a href="#blocks">Blocks</a>
<a href="#snippets">Snippets</a><a href="#templates">Templates</a>
<a href="#content">Product Content</a><a href="#seo">SEO</a>
<a href="#landing">Landing Pages</a><a href="#documents">Documents</a>
<a href="#videos">Videos</a><a href="#approval">Approval Queue</a>
<a href="#preview">Preview</a><a href="#broken-links">Broken Links</a>
<a href="#usage">Usage</a><a href="#history">History & Rollback</a>
<a href="#search">Search</a></nav><h2 id="dashboard">Content Dashboard</h2>
<p>Use the canonical API for reusable content, templates, scores, workflow,
usage and sanitized preview.</p><pre id="data">Loading languages…</pre>
<script>fetch('/api/v1/content/languages').then(r=>r.json())
.then(x=>data.textContent=JSON.stringify(x,null,2))</script></body></html>"""


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def content_admin() -> str:
    return ADMIN_HTML
