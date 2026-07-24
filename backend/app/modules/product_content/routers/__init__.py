from app.modules.product_content.routers import (
    admin,
    content_types,
    documents,
    landing_pages,
    languages,
    library,
    preview,
    product_content,
    prompts,
    scoring,
    search,
    seo,
    templates,
    usage,
    videos,
)

ROUTERS = (
    languages.router,
    content_types.router,
    product_content.router,
    seo.router,
    landing_pages.router,
    documents.router,
    videos.router,
    library.router,
    templates.router,
    preview.router,
    scoring.router,
    prompts.router,
    usage.router,
    search.router,
    admin.router,
)

__all__ = ["ROUTERS"]
