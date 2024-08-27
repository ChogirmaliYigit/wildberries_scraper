from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if hasattr(response, "data"):
        if "detail" in response.data:
            response.data["message"] = response.data["detail"]
            del response.data["detail"]
        message = response.data.get("message")
        if isinstance(message, list):
            response.data["message"] = message[0]
    return response
