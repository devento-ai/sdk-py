"""Tests for Tavor exceptions."""

from tavor import (
    TavorError,
    APIError,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    BoxNotFoundError,
    ConflictError,
    ValidationError,
    ServerError,
    CommandTimeoutError,
    BoxTimeoutError,
)
from tavor.exceptions import map_status_to_exception


class TestExceptions:
    """Test exception classes and error mapping."""

    def test_tavor_error_base(self):
        """Test base TavorError."""
        error = TavorError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert isinstance(error, Exception)

    def test_api_error(self):
        """Test APIError with different parameters."""
        # Basic API error
        error = APIError(400)
        assert error.status_code == 400
        assert "API request failed with status 400" in str(error)
        assert error.response_data == {}

        # API error with message
        error = APIError(404, "Resource not found")
        assert error.status_code == 404
        assert str(error) == "Resource not found"

        # API error with response data
        response_data = {"error": "Invalid request", "field": "name"}
        error = APIError(422, "Validation failed", response_data)
        assert error.status_code == 422
        assert error.message == "Validation failed"
        assert error.response_data == response_data

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError(401, "Invalid API key")
        assert error.status_code == 401
        assert str(error) == "Invalid API key"
        assert isinstance(error, APIError)

    def test_forbidden_error(self):
        """Test ForbiddenError."""
        error = ForbiddenError(403, "Access denied")
        assert error.status_code == 403
        assert str(error) == "Access denied"
        assert isinstance(error, APIError)

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError(404, "Resource not found")
        assert error.status_code == 404
        assert str(error) == "Resource not found"
        assert isinstance(error, APIError)

    def test_box_not_found_error(self):
        """Test BoxNotFoundError."""
        error = BoxNotFoundError(404, "Box not found")
        assert error.status_code == 404
        assert str(error) == "Box not found"
        assert isinstance(error, NotFoundError)
        assert isinstance(error, APIError)

    def test_conflict_error(self):
        """Test ConflictError."""
        error = ConflictError(409, "Resource already exists")
        assert error.status_code == 409
        assert str(error) == "Resource already exists"
        assert isinstance(error, APIError)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError(422, "Invalid input")
        assert error.status_code == 422
        assert str(error) == "Invalid input"
        assert isinstance(error, APIError)

    def test_server_error(self):
        """Test ServerError."""
        error = ServerError(500, "Internal server error")
        assert error.status_code == 500
        assert str(error) == "Internal server error"
        assert isinstance(error, APIError)

    def test_command_timeout_error(self):
        """Test CommandTimeoutError."""
        # Default message
        error = CommandTimeoutError()
        assert str(error) == "Command execution timed out"
        assert isinstance(error, TavorError)

        # Custom message
        error = CommandTimeoutError("Command exceeded 30s limit")
        assert str(error) == "Command exceeded 30s limit"

    def test_box_timeout_error(self):
        """Test BoxTimeoutError."""
        # Default message
        error = BoxTimeoutError()
        assert str(error) == "Box timed out"
        assert isinstance(error, TavorError)

        # Custom message
        error = BoxTimeoutError("Box exceeded 1 hour limit")
        assert str(error) == "Box exceeded 1 hour limit"

    def test_map_status_to_exception(self):
        """Test status code to exception mapping."""
        # Test specific status codes
        error = map_status_to_exception(401, "Unauthorized")
        assert isinstance(error, AuthenticationError)
        assert error.status_code == 401
        assert error.message == "Unauthorized"

        error = map_status_to_exception(403, "Forbidden")
        assert isinstance(error, ForbiddenError)

        error = map_status_to_exception(404, "Not found")
        assert isinstance(error, NotFoundError)

        error = map_status_to_exception(409, "Conflict")
        assert isinstance(error, ConflictError)

        error = map_status_to_exception(422, "Invalid")
        assert isinstance(error, ValidationError)

        # Test 5xx errors
        error = map_status_to_exception(500, "Server error")
        assert isinstance(error, ServerError)

        error = map_status_to_exception(503, "Service unavailable")
        assert isinstance(error, ServerError)

        # Test unknown status codes
        error = map_status_to_exception(418, "I'm a teapot")
        assert isinstance(error, APIError)
        assert not isinstance(
            error, (AuthenticationError, ForbiddenError, NotFoundError)
        )
        assert error.status_code == 418

        # Test with response data
        response_data = {"errors": ["field1", "field2"]}
        error = map_status_to_exception(422, "Validation failed", response_data)
        assert isinstance(error, ValidationError)
        assert error.response_data == response_data
