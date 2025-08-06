# Devento Python SDK

Official Python SDK for [Devento](https://devento.ai), the cloud sandbox platform that provides secure, isolated execution environments.

## Installation

```bash
pip install devento
```

For async support:

```bash
pip install devento[async]
```

## Quick Start

```python
from devento import Devento

# Initialize the client
devento = Devento(api_key="sk-devento-...")

# Create and use a sandbox
with devento.box() as box:
    result = box.run("echo 'Hello from Devento!'")
    print(result.stdout)  # "Hello from Devento!"
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
from devento import Devento

devento = Devento(api_key="sk-devento-...")

with devento.box() as box:
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
from devento import Devento, CommandTimeoutError, DeventoError

try:
    with devento.box() as box:
        # This will timeout
        result = box.run("sleep 120", timeout=5)
except CommandTimeoutError as e:
    print(f"Command timed out: {e}")
except DeventoError as e:
    print(f"Error: {e}")
```

### Streaming Output

```python
with devento.box() as box:
    # Stream output as it's generated
    result = box.run(
        "for i in {1..5}; do echo \"Line $i\"; sleep 1; done",
        on_stdout=lambda line: print(f"[LIVE] {line}", end=""),
        on_stderr=lambda line: print(f"[ERROR] {line}", end="")
    )
```

### Custom Box Configuration

```python
from devento import Devento, BoxConfig

config = BoxConfig(
    cpu=2,
    mib_ram=2048,
    timeout=7200,  # 2 hours
    metadata={"project": "data-analysis"}
)

with devento.box(config=config) as box:
    # Run resource-intensive tasks
    result = box.run("python train_model.py")
```

### Web Support

Boxes can expose services to the internet via public URLs. Each box gets a unique hostname, and you can access specific ports using the `get_public_url()` method:

```python
with devento.box() as box:
    # Start a web server on port 8080
    box.run("python -m http.server 8080 &")

    # Wait for server to start
    box.run("sleep 2")

    # Get the public URL for port 8080
    public_url = box.get_public_url(8080)
    print(f"Access your server at: {public_url}")
    # Output: https://8080-uuid.deven.to

    # The service is now accessible from anywhere on the internet
    box.run(f"curl {public_url}")
```

This feature is useful for:

- Testing webhooks and callbacks
- Sharing development servers temporarily
- Demonstrating web applications
- Running services that need to be accessible from external systems

### Port Exposing

You can dynamically expose ports from inside the sandbox to random external ports. This is useful when you need to access services running inside the sandbox but don't know the port in advance or need multiple services:

```python
with devento.box() as box:
    # Start a service on port 3000 inside the sandbox
    box.run("python -m http.server 3000 &")

    # Give the server a moment to start
    box.run("sleep 2")

    # Expose the internal port 3000 to an external port
    exposed_port = box.expose_port(3000)

    print(f"Internal port {exposed_port.target_port} is now accessible on external port {exposed_port.proxy_port}")
    print(f"Port mapping expires at: {exposed_port.expires_at}")

    # You can now access the service using the proxy_port
    # For example: http://sandbox-hostname:proxy_port
```

The `expose_port` method returns an `ExposedPort` object with:

- `target_port` - The port inside the sandbox (what you requested)
- `proxy_port` - The external port assigned by the system
- `expires_at` - When this port mapping will expire

### Async Operations

```python
import asyncio
from devento import AsyncDevento

async def run_parallel_tasks():
    async with AsyncDevento(api_key="sk-devento-...") as devento:
        async with devento.box() as box:
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
box = devento.create_box()

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

- `Devento`: Main client for synchronous operations
- `AsyncDevento`: Client for async operations (requires `pip install devento[async]`)

### Configuration

- `BoxConfig`: Configuration for box creation
  - `cpu`: Number of CPUs to allocate (default: 1)
  - `mib_ram`: MiB RAM to allocate (default: 1024)
  - `timeout`: Maximum lifetime in seconds (default: 3600, or DEVENTO_BOX_TIMEOUT env var)
  - `metadata`: Custom metadata dictionary

### Models

- `Box`: Represents a box instance
  - `hostname`: Public hostname for web access (e.g., `uuid.deven.to`)
  - `get_public_url(port)`: Get the public URL for accessing a specific port
- `CommandResult`: Result of command execution
  - `stdout`: Command output
  - `stderr`: Error output
  - `exit_code`: Process exit code
  - `status`: Command status (QUEUED, RUNNING, DONE, FAILED, ERROR)
- `ExposedPort`: Result of exposing a port
  - `proxy_port`: External port assigned by the system
  - `target_port`: Port inside the sandbox
  - `expires_at`: When this port mapping expires

### Exceptions

- `DeventoError`: Base exception for all SDK errors
- `APIError`: Base for API-related errors
- `AuthenticationError`: Invalid API key
- `BoxNotFoundError`: Box doesn't exist
- `CommandTimeoutError`: Command execution timeout
- `ValidationError`: Invalid request parameters

## Environment Variables

The SDK supports the following environment variables:

- `DEVENTO_API_KEY`: Your API key (alternative to passing it in code)
- `DEVENTO_BASE_URL`: API base URL (default: <https://api.devento.ai>)
- `DEVENTO_CPU`: CPU to allocate to the sandbox (default: 1)
- `DEVENTO_MIB_RAM`: MiB RAM to allocate to the sandbox (default: 1024)
- `DEVENTO_BOX_TIMEOUT`: Default box timeout in seconds (default: 3600)

Example:

```bash
export DEVENTO_API_KEY="sk-devento-..."
export DEVENTO_BASE_URL="https://api.devento.ai"
export DEVENTO_BOX_TIMEOUT="7200"
export DEVENTO_CPU="1"
export DEVENTO_MIB_RAM="1024"

# Now you can initialize without parameters
python -c "from devento import Devento; client = Devento()"
```

## Requirements

- Python 3.9+
- `requests` library
- `aiohttp` (optional, for async support)

## Support

- Documentation: <https://devento.ai>
- Issues: <https://github.com/devento-ai/sdk-py/issues>

## License

MIT License - see LICENSE file for details.
