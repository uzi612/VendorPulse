import math


def paginate_queryset(queryset, request, default_page_size=10, max_page_size=100):
    """
    Shared pagination for list endpoints.

    Supports ?page= (1-based), ?page_size= (capped), and ?all=1 to return
    the full unpaginated list (flat response, used where the frontend
    aggregates rows client-side).

    Returns (rows, meta, all_requested) where meta is:
        {"count", "total_pages", "page", "page_size"}.
    """
    all_requested = request.GET.get('all') == '1'

    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', default_page_size))
    except (TypeError, ValueError):
        page_size = default_page_size
    page_size = min(max(1, page_size), max_page_size)

    count = queryset.count()
    if all_requested or count == 0:
        rows = list(queryset)
        size = count if all_requested else page_size
        return rows, {"count": count, "total_pages": 1, "page": 1, "page_size": size}, all_requested

    total_pages = max(1, math.ceil(count / page_size))
    page = min(page, total_pages)
    rows = list(queryset[(page - 1) * page_size: page * page_size])
    meta = {"count": count, "total_pages": total_pages, "page": page, "page_size": page_size}
    return rows, meta, all_requested
