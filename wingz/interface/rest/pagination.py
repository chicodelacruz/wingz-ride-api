from rest_framework.pagination import PageNumberPagination


class RidePageNumberPagination(PageNumberPagination):
    """Page-number pagination with a client-controllable page size.

    Note on scale: page-number pagination compiles to LIMIT/OFFSET, and OFFSET makes
    the database walk and discard every skipped row, so deep pages get progressively
    more expensive on a large table. Cursor pagination avoids that, but it needs a
    stable ordering key — which the distance sort, being computed per request relative
    to an arbitrary point, does not have. See the README for the full trade-off.
    """

    page_size_query_param = "page_size"
    max_page_size = 100
