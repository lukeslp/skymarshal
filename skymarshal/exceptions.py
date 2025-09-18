"""
Skymarshal Exceptions and Error Utilities

File Purpose: Centralized exception types and simple error handling helpers
Primary Classes/Functions: SkymarshalError, APIError, DataError, FileError, AuthenticationError, handle_error, safe_execute
Inputs and Outputs (I/O): Accepts exceptions and console; prints user-friendly messages
"""

from typing import Any, Callable, Optional

from rich.console import Console


class SkymarshalError(Exception):
    """Base exception for all Skymarshal-specific errors."""

    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        self.message = message
        self.details = details
        self.original_error = original_error
        super().__init__(message)


class AuthenticationError(SkymarshalError):
    """Raised when authentication fails or expires."""

    pass


class APIError(SkymarshalError):
    """Raised when AT Protocol API calls fail."""

    pass


class DataError(SkymarshalError):
    """Raised when data operations fail."""

    pass


class FileError(SkymarshalError):
    """Raised when file operations fail."""

    pass


class ValidationError(SkymarshalError):
    """Raised when input validation fails."""

    pass


def handle_error(
    console: Console,
    error: Exception,
    operation: str,
    show_details: bool = False,
    reraise: bool = False,
) -> None:
    """
    Standardized error handling function.

    Args:
        console: Rich console for output
        error: The exception that occurred
        operation: Description of the operation that failed
        show_details: Whether to show detailed error information
        reraise: Whether to re-raise the exception after handling
    """
    if isinstance(error, SkymarshalError):
        console.print(f"[red]{operation} failed: {error.message}[/]")
        if show_details and error.details:
            console.print(f"[dim]   Details: {error.details}[/]")
        if show_details and error.original_error:
            console.print(f"[dim]   Original error: {error.original_error}[/]")
    else:
        console.print(f"[red]{operation} failed: {str(error)}[/]")
        if show_details:
            console.print(f"[dim]   Error type: {type(error).__name__}[/]")

    if reraise:
        raise error


def safe_execute(
    func: Callable,
    *args,
    console: Optional[Console] = None,
    operation: str = "Operation",
    default_return: Any = None,
    **kwargs,
):
    """
    Safely execute a function with standardized error handling.

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        console: Rich console for error output
        operation: Description of the operation for error messages
        default_return: Value to return if function fails
        **kwargs: Keyword arguments for the function

    Returns:
        Function result or default_return if function fails
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if console:
            handle_error(console, e, operation)
        return default_return


def wrap_api_errors(func):
    """
    Decorator to wrap AT Protocol API errors in APIError exceptions.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            if any(
                keyword in error_msg
                for keyword in ["auth", "unauthorized", "token", "expired", "forbidden"]
            ):
                raise AuthenticationError(
                    "Authentication required",
                    details="Your session may have expired. Please log in again.",
                    original_error=e,
                )
            elif any(keyword in error_msg for keyword in ["rate", "limit", "throttle"]):
                raise APIError(
                    "Rate limit exceeded",
                    details="Please wait before making more requests.",
                    original_error=e,
                )
            elif any(
                keyword in error_msg for keyword in ["network", "connection", "timeout"]
            ):
                raise APIError(
                    "Network error",
                    details="Please check your internet connection and try again.",
                    original_error=e,
                )
            else:
                raise APIError("API request failed", details=str(e), original_error=e)

    return wrapper
