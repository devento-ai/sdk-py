"""Server-Sent Events (SSE) parsing utilities."""

from typing import Generator, Optional
from .models import SSEEvent


def parse_sse_message(message: str) -> Optional[SSEEvent]:
    """Parse a single SSE message.

    Args:
        message: Raw SSE message string

    Returns:
        SSEEvent if valid, None otherwise
    """
    lines = message.strip().split("\n")
    event = ""
    data = ""

    for line in lines:
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            data = line[6:]

    if event and data:
        return SSEEvent(event=event, data=data)

    return None


def parse_sse_stream(text: str) -> Generator[SSEEvent, None, None]:
    """Parse SSE stream text into individual events.

    Args:
        text: Raw SSE stream text

    Yields:
        SSEEvent objects
    """
    messages = text.split("\n\n")

    for message in messages:
        if message.strip():
            parsed = parse_sse_message(message)
            if parsed:
                yield parsed
