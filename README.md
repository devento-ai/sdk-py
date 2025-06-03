# Tavor Python SDK

Official Python SDK for [Tavor](https://tavor.dev), the cloud sandbox platform that provides secure, isolated execution environments.

## Installation

```bash
pip install tavor
```

For async support:

```bash
pip install tavor[async]
```

## Quick Start

```python
from tavor import Tavor

# Initialize the client
tavor = Tavor(api_key="sk-tavor-...")

# Create and use a sandbox
with tavor.box() as box:
    result = box.run("echo 'Hello from Tavor!'")
    print(result.stdout)  # "Hello from Tavor!"
```

## Features

- **Simple API**: Intuitive interface for creating and managing boxes
- **Automatic cleanup**: Boxes are automatically cleaned up when done
- **Streaming output**: Real-time command output streaming
- **Async support**: Full async/await support for concurrent operations
- **Type hints**: Complete type annotations for better IDE support
- **Error handling**: Comprehensive error handling with specific exception types

## Usage Examples

### Basic Command Execution

```python
from tavor import Tavor

tavor = Tavor(api_key="sk-tavor-...")

with tavor.box() as box:
    # Run simple commands
    result = box.run("pwd")
    print(f"Current directory: {result.stdout}")

    # Install packages
    box.run("pip install numpy pandas")

    # Run Python code
    result = box.run("python -c 'import numpy as np; print(np.array([1,2,3]))'")
    print(result.stdout)
```

### Error Handling

```python
from tavor import Tavor, CommandTimeoutError, TavorError

try:
    with tavor.box() as box:
        # This will timeout
        result = box.run("sleep 120", timeout=5)
except CommandTimeoutError as e:
    print(f"Command timed out: {e}")
except TavorError as e:
    print(f"Error: {e}")
```

### Streaming Output

```python
with tavor.box() as box:
    # Stream output as it's generated
    result = box.run(
        "for i in {1..5}; do echo \"Line $i\"; sleep 1; done",
        on_stdout=lambda line: print(f"[LIVE] {line}", end=""),
        on_stderr=lambda line: print(f"[ERROR] {line}", end="")
    )
```

### Custom Box Configuration

```python
from tavor import Tavor, BoxConfig, BoxTemplate

config = BoxConfig(
    template=BoxTemplate.PRO,  # More CPU and RAM
    timeout=7200,  # 2 hours
    metadata={"project": "data-analysis"}
)

with tavor.box(config=config) as box:
    # Run resource-intensive tasks
    result = box.run("python train_model.py")
```

### Async Operations

```python
import asyncio
from tavor import AsyncTavor

async def run_parallel_tasks():
    async with AsyncTavor(api_key="sk-tavor-...") as tavor:
        async with tavor.box() as box:
            # Run multiple commands in parallel
            results = await asyncio.gather(
                box.run("task1.py"),
                box.run("task2.py"),
                box.run("task3.py")
            )

            for result in results:
                print(result.stdout)

asyncio.run(run_parallel_tasks())
```

### Manual Box Management

```python
# Create a box without automatic cleanup
box = tavor.create_box()

try:
    # Wait for box to be ready
    box.wait_until_ready()

    # Run commands
    result = box.run("echo 'Hello'")
    print(result.stdout)

    # Check box status
    print(f"Box status: {box.status}")
finally:
    # Don't forget to clean up!
    box.stop()
```

## API Reference

### Client Classes

- `Tavor`: Main client for synchronous operations
- `AsyncTavor`: Client for async operations (requires `pip install tavor[async]`)

### Configuration

- `BoxConfig`: Configuration for box creation
  - `template`: Use predefined templates (BoxTemplate.BASIC, PRO) - defaults to BASIC
  - `template_id`: Use custom template ID
  - `timeout`: Maximum lifetime in seconds (default: 3600, or TAVOR_BOX_TIMEOUT env var)
  - `metadata`: Custom metadata dictionary

### Models

- `Box`: Represents a box instance
- `CommandResult`: Result of command execution
  - `stdout`: Command output
  - `stderr`: Error output
  - `exit_code`: Process exit code
  - `status`: Command status (QUEUED, RUNNING, DONE, FAILED, ERROR)

### Exceptions

- `TavorError`: Base exception for all SDK errors
- `APIError`: Base for API-related errors
- `AuthenticationError`: Invalid API key
- `BoxNotFoundError`: Box doesn't exist
- `CommandTimeoutError`: Command execution timeout
- `ValidationError`: Invalid request parameters

## Environment Variables

The SDK supports the following environment variables:

- `TAVOR_API_KEY`: Your API key (alternative to passing it in code)
- `TAVOR_BASE_URL`: API base URL (default: <https://api.tavor.dev>)
- `TAVOR_CPU`: CPU to allocate to the sandbox (default: 1)
- `TAVOR_MIB_RAM`: MiB RAM to allocate to the sandbox (default: 1024)
- `TAVOR_BOX_TIMEOUT`: Default box timeout in seconds (default: 3600)

Example:

```bash
export TAVOR_API_KEY="sk-tavor-..."
export TAVOR_BASE_URL="https://api.tavor.dev"
export TAVOR_BOX_TIMEOUT="7200"
export TAVOR_CPU="1"
export TAVOR_MIB_RAM="1024"

# Now you can initialize without parameters
python -c "from tavor import Tavor; client = Tavor()"
```

## Requirements

- Python 3.9+
- `requests` library
- `aiohttp` (optional, for async support)

## Support

- Documentation: <https://tavor.dev>
- Issues: <https://github.com/tavor-dev/sdk-py/issues>

## License

MIT License - see LICENSE file for details.
