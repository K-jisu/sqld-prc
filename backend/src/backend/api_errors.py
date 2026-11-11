class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, **details):
        self.status, self.code, self.message, self.details = status, code, message, details
        super().__init__(code)


def fail(code: str, message: str, status: int = 409, **details):
    raise APIError(status, code, message, **details)
