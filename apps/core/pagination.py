from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPageNumberPagination(PageNumberPagination):
    page_size_query_param = "count"

    def get_page_size(self, request):
        if self.page_size_query_param:
            try:
                return int(request.query_params[self.page_size_query_param])
            except (KeyError, ValueError):
                pass
            return self.page_size

    def get_paginated_response(self, data):
        return Response(
            {
                "total": self.page.paginator.count,
                "next": self.page.next_page_number() if self.page.has_next() else None,
                "previous": (
                    self.page.previous_page_number()
                    if self.page.has_previous()
                    else None
                ),
                "current": self.page.number,
                "results": data,
            }
        )
