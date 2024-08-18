from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if hasattr(response, "data"):
        if "detail" in response.data:
            if "token" not in response.data["detail"].lower():
                response.data["message"] = response.data["detail"]
                del response.data["detail"]
        if response.status_code >= 300 and len(response.data.keys()) == 1:
            response.data["message"] = response.data[response.data.keys()[0]]
    return response
