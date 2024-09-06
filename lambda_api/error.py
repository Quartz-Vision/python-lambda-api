class APIError(RuntimeError):
    _status = 500
    _message = None

    def __init__(self, message: str | None = None, status: int | None = None):
        super().__init__(message or self._message)
        self.status = status or self._status


class NotFoundError(APIError):
    _status = 404
    _message = "Not Found"


class BadRequestError(APIError):
    _status = 400
    _message = "Bad Request"


class UnauthorizedError(APIError):
    _status = 401
    _message = "Unauthorized"


class ForbiddenError(APIError):
    _status = 403
    _message = "Forbidden"


class InternalServerError(APIError):
    _status = 500
    _message = "Internal Server Error"


class MethodNotAllowedError(APIError):
    _status = 405
    _message = "Method Not Allowed"


class ConflictError(APIError):
    _status = 409
    _message = "Conflict"


class TooManyRequestsError(APIError):
    _status = 429
    _message = "Too Many Requests"


class UnsupportedMediaTypeError(APIError):
    _status = 415
    _message = "Unsupported Media Type"


class UnprocessableEntityError(APIError):
    _status = 422
    _message = "Unprocessable Entity"


class NotImplementedHTTPError(APIError):
    _status = 501
    _message = "Not Implemented"
