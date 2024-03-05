class APIError(RuntimeError):
    status = 500
    message = None

    def __init__(self, message: str | None = None, status: int | None = None):
        super().__init__(message or self.message)
        self.status = status or self.status


class NotFoundError(APIError):
    status = 404
    message = "Not Found"
