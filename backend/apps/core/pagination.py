from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    """50 per page by default; clients may ask for up to 1000 (?page_size=) for pickers."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000
