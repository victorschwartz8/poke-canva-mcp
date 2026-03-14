import os
import asyncio

from fastmcp import FastMCP

from auth import canva_client

mcp = FastMCP(
    name="canva",
    instructions=(
        "Use these tools to interact with Canva designs and templates. "
        "Use create_carousel for Instagram carousels (1080x1350 multi-page). "
        "Use create_design for other formats. "
        "Use list_templates and autofill_template to create designs from brand templates. "
        "Use export_design to download finished designs as PNG, JPG, or PDF."
    ),
)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _poll_job(endpoint: str, timeout: int = 120) -> dict:
    """Poll an async Canva job until it completes."""
    async with await canva_client() as client:
        for _ in range(timeout // 2):
            resp = await client.get(endpoint)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("job", data).get("status", data.get("status"))
            if status == "success":
                return data
            if status == "failed":
                error = data.get("job", data).get("error", {})
                raise RuntimeError(f"Job failed: {error.get('message', status)}")
            await asyncio.sleep(2)
    raise TimeoutError(f"Job at {endpoint} did not complete within {timeout}s")


# ── Designs ──────────────────────────────────────────────────────────────────


@mcp.tool
async def create_design(
    title: str,
    design_type: str = "presentation",
    width: int | None = None,
    height: int | None = None,
    page_count: int = 1,
) -> str:
    """Create a new Canva design.

    Args:
        title: Title of the design.
        design_type: Canva design type preset. Common values: 'presentation',
            'doc', 'whiteboard', 'poster'. Ignored if width/height are set.
        width: Custom width in pixels (e.g. 1080 for Instagram).
        height: Custom height in pixels (e.g. 1080 for square, 1350 for portrait).
        page_count: Number of pages to create (default 1).
    """
    body: dict = {"title": title}
    if width and height:
        body["design_type"] = {
            "type": "custom",
            "width": width,
            "height": height,
        }
    else:
        body["design_type"] = {"type": "preset", "name": design_type}

    if page_count > 1:
        body["page_count"] = page_count

    async with await canva_client() as client:
        resp = await client.post("/designs", json=body)
        resp.raise_for_status()
        data = resp.json()

    design = data["design"]
    urls = design.get("urls", {})
    edit_url = urls.get("edit_url", "N/A")
    return (
        f"Created design: {design['title']}\n"
        f"ID: {design['id']}\n"
        f"Edit: {edit_url}"
    )


@mcp.tool
async def create_carousel(
    title: str,
    page_count: int = 5,
) -> str:
    """Create an Instagram carousel design (1080x1350, multi-page).

    Args:
        title: Title of the carousel.
        page_count: Number of slides (default 5).
    """
    return await create_design(
        title=title,
        width=1080,
        height=1350,
        page_count=page_count,
    )


@mcp.tool
async def list_designs(
    query: str | None = None,
    continuation: str | None = None,
) -> str:
    """List the user's Canva designs.

    Args:
        query: Optional search query to filter designs by title.
        continuation: Pagination token from a previous response.
    """
    params: dict = {}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation

    async with await canva_client() as client:
        resp = await client.get("/designs", params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return "No designs found."

    lines = []
    for d in items:
        urls = d.get("urls", {})
        thumb = urls.get("thumbnail_url", "")
        lines.append(
            f"- {d.get('title', 'Untitled')}\n"
            f"  ID: {d['id']}\n"
            f"  Created: {d.get('created_at', 'unknown')}\n"
            f"  Thumbnail: {thumb}"
        )

    cont = data.get("continuation")
    if cont:
        lines.append(f"\n(more results available — continuation: {cont})")

    return "\n".join(lines)


@mcp.tool
async def get_design(design_id: str) -> str:
    """Get metadata for a Canva design.

    Args:
        design_id: The design ID.
    """
    async with await canva_client() as client:
        resp = await client.get(f"/designs/{design_id}")
        resp.raise_for_status()
        data = resp.json()

    d = data["design"]
    urls = d.get("urls", {})
    lines = [
        f"Title: {d.get('title', 'Untitled')}",
        f"ID: {d['id']}",
        f"Created: {d.get('created_at', 'unknown')}",
        f"Updated: {d.get('updated_at', 'unknown')}",
        f"Page count: {d.get('page_count', 'unknown')}",
        f"Edit URL: {urls.get('edit_url', 'N/A')}",
        f"View URL: {urls.get('view_url', 'N/A')}",
        f"Thumbnail: {urls.get('thumbnail_url', 'N/A')}",
    ]
    return "\n".join(lines)


@mcp.tool
async def get_design_pages(design_id: str) -> str:
    """Get page-level details for a Canva design.

    Args:
        design_id: The design ID.
    """
    async with await canva_client() as client:
        resp = await client.get(f"/designs/{design_id}/pages")
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return "No pages found."

    lines = []
    for i, page in enumerate(items, 1):
        thumb = page.get("thumbnail", {}).get("url", "N/A")
        lines.append(
            f"Page {i}: {page.get('title', 'Untitled')}\n"
            f"  ID: {page['id']}\n"
            f"  Thumbnail: {thumb}"
        )
    return "\n".join(lines)


# ── Templates ────────────────────────────────────────────────────────────────


@mcp.tool
async def list_templates(
    query: str | None = None,
    continuation: str | None = None,
) -> str:
    """List available Canva brand templates.

    Args:
        query: Optional search query to filter templates.
        continuation: Pagination token from a previous response.
    """
    params: dict = {}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation

    async with await canva_client() as client:
        resp = await client.get("/brand-templates", params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return "No brand templates found."

    lines = []
    for t in items:
        lines.append(
            f"- {t.get('title', 'Untitled')}\n"
            f"  ID: {t['id']}\n"
            f"  Created: {t.get('created_at', 'unknown')}"
        )

    cont = data.get("continuation")
    if cont:
        lines.append(f"\n(more results available — continuation: {cont})")

    return "\n".join(lines)


@mcp.tool
async def get_template_fields(template_id: str) -> str:
    """Get the fillable fields in a Canva brand template.

    Use this to discover which fields can be autofilled before calling autofill_template.

    Args:
        template_id: The brand template ID (get from list_templates).
    """
    async with await canva_client() as client:
        resp = await client.get(f"/brand-templates/{template_id}/dataset")
        resp.raise_for_status()
        data = resp.json()

    dataset = data.get("dataset", {})
    if not dataset:
        return "No fillable fields found in this template."

    lines = []
    for name, field in dataset.items():
        field_type = field.get("type", "unknown")
        lines.append(f"- {name} ({field_type})")
    return "\n".join(lines)


@mcp.tool
async def autofill_template(
    template_id: str,
    title: str,
    data: dict[str, str],
) -> str:
    """Create a design by autofilling a brand template with data.

    Args:
        template_id: The brand template ID.
        title: Title for the new design.
        data: Dict mapping field names to values.
            For text fields: {"field_name": "text value"}
            Use get_template_fields to discover available fields.
    """
    # Build the autofill data in Canva's format
    autofill_data = {}
    for key, value in data.items():
        autofill_data[key] = {"type": "text", "text": value}

    body = {
        "brand_template_id": template_id,
        "title": title,
        "data": autofill_data,
    }

    async with await canva_client() as client:
        resp = await client.post("/autofills", json=body)
        resp.raise_for_status()
        job_data = resp.json()

    job_id = job_data["job"]["id"]
    result = await _poll_job(f"/autofills/{job_id}")

    design = result.get("job", {}).get("result", {}).get("design", {})
    design_id = design.get("id", "unknown")
    edit_url = design.get("urls", {}).get("edit_url", "N/A")

    return (
        f"Autofilled template into new design\n"
        f"Design ID: {design_id}\n"
        f"Edit: {edit_url}"
    )


# ── Export ───────────────────────────────────────────────────────────────────


@mcp.tool
async def export_design(
    design_id: str,
    format: str = "png",
    pages: list[int] | None = None,
    quality: int = 80,
) -> str:
    """Export a Canva design as an image or PDF.

    Args:
        design_id: The design ID to export.
        format: Export format — 'png', 'jpg', or 'pdf' (default 'png').
        pages: Optional list of 1-based page numbers to export.
            If omitted, all pages are exported.
        quality: JPEG quality 1-100 (default 80, only used for jpg format).
    """
    body: dict = {
        "design_id": design_id,
        "format": {
            "type": format,
        },
    }

    if format == "jpg":
        body["format"]["quality"] = quality

    if pages:
        body["pages"] = [p - 1 for p in pages]  # Canva uses 0-based

    async with await canva_client() as client:
        resp = await client.post("/exports", json=body)
        resp.raise_for_status()
        job_data = resp.json()

    job_id = job_data["job"]["id"]
    result = await _poll_job(f"/exports/{job_id}")

    urls = result.get("job", {}).get("urls", [])
    if not urls:
        return "Export completed but no download URLs returned."

    lines = ["Export complete! Download URLs:"]
    for i, url in enumerate(urls, 1):
        lines.append(f"  Page {i}: {url}")
    return "\n".join(lines)


# ── Assets ───────────────────────────────────────────────────────────────────


@mcp.tool
async def upload_asset(
    name: str,
    image_url: str,
) -> str:
    """Upload an image to the Canva asset library from a URL.

    Args:
        name: Name for the asset in the library.
        image_url: Public URL of the image to upload.
    """
    body = {
        "name": name,
        "url": image_url,
    }

    async with await canva_client() as client:
        resp = await client.post("/asset-uploads", json=body)
        resp.raise_for_status()
        data = resp.json()

    job_id = data["job"]["id"]
    result = await _poll_job(f"/asset-uploads/{job_id}")

    asset = result.get("job", {}).get("asset", {})
    return (
        f"Uploaded asset: {name}\n"
        f"Asset ID: {asset.get('id', 'unknown')}"
    )


# ── Folders ──────────────────────────────────────────────────────────────────


@mcp.tool
async def list_folder_items(
    folder_id: str,
    continuation: str | None = None,
) -> str:
    """List items in a Canva folder.

    Args:
        folder_id: The folder ID to browse.
        continuation: Pagination token from a previous response.
    """
    params: dict = {}
    if continuation:
        params["continuation"] = continuation

    async with await canva_client() as client:
        resp = await client.get(f"/folders/{folder_id}/items", params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items", [])
    if not items:
        return "Folder is empty."

    lines = []
    for item in items:
        item_type = item.get("type", "unknown")
        name = item.get("name", item.get("title", "Untitled"))
        lines.append(f"- [{item_type}] {name}  (id: {item.get('id', 'N/A')})")

    cont = data.get("continuation")
    if cont:
        lines.append(f"\n(more results available — continuation: {cont})")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, path="/mcp")
