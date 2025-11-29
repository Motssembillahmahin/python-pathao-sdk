from fastapi import HTTPException, status


class HTTP400(HTTPException):
    def __init__(self, detail: str) -> None:
        """Raise HTTP 400 exception"""
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class HTTP401(HTTPException):
    def __init__(self, detail: str) -> None:
        """Raise HTTP 400 exception"""
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class HTTP403(HTTPException):
    def __init__(self, detail: str) -> None:
        """Raise HTTP 403 exception"""
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class HTTP404(HTTPException):
    def __init__(self, detail: str) -> None:
        """Raise HTTP 404 exception"""
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class HTTP500(HTTPException):
    def __init__(self, detail: str) -> None:
        """Raise HTTP 500 exception"""
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class ValidationError(Exception):
    """Custom exception for validation errors"""

    pass


class APIError(Exception):
    """Custom exception for API-related errors"""

    pass
