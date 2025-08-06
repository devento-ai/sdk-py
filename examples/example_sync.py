#!/usr/bin/env python3
"""
Example usage of the Devento SDK - Synchronous version

This demonstrates basic usage patterns for the Devento Python SDK.
Replace 'your-api-key-here' with your actual Devento API key.
"""

from devento import Devento, BoxConfig, DeventoError


def main():
    # Initialize the client with your API key
    # devento = Devento(api_key="your-api-key-here")
    devento = Devento()

    print("🚀 Devento SDK Example - Synchronous")
    print("-" * 40)

    try:
        # Example 1: Simple command execution with context manager
        print("1. Basic command execution:")
        with devento.box() as box:
            result = box.run("echo 'Hello from Devento!'")
            print(f"   Output: {result.stdout.strip()}")
            print(f"   Exit code: {result.exit_code}")

        # Example 2: Using custom configuration
        print("\n2. Using custom box configuration:")
        config = BoxConfig(
            cpu=2,  # 2 CPU cores
            mib_ram=2048,  # 2 GB RAM
            timeout=3600,  # 1 hour
            metadata={"example": "sync", "language": "python"},
        )

        with devento.box(config=config) as box:
            # Install a package and use it
            print("   Installing numpy...")
            box.run("pip install numpy")

            result = box.run(
                "python -c 'import numpy; print(f\"NumPy version: {numpy.__version__}\")'"
            )
            print(f"   {result.stdout.strip()}")

        # Example 3: Streaming output
        print("\n3. Streaming command output:")
        with devento.box() as box:

            def print_stdout(line):
                print(f"   [LIVE] {line.rstrip()}")

            result = box.run(
                'for i in {1..3}; do echo "Processing step $i"; sleep 0.5; done',
                on_stdout=print_stdout,
            )

        # Example 4: Error handling
        print("\n4. Error handling:")
        with devento.box() as box:
            try:
                # This should fail
                result = box.run("exit 1")
                print(f"   Command succeeded unexpectedly: {result.stdout}")
            except Exception:
                print("   ✓ Handled command failure gracefully")
                print(f"   Exit code: {result.exit_code}")

        # Example 5: Pause & resume
        print("\n5. Pause & resume:")
        with devento.box() as box:
            result = box.run("uptime")
            print(f"   Output: {result.stdout.strip()}")
            print(f"   Exit code: {result.exit_code}")

            box.pause()

            box.resume()

            result = box.run("uptime")
            print(f"   Output: {result.stdout.strip()}")
            print(f"   Exit code: {result.exit_code}")

        print("\n✅ All examples completed successfully!")

    except DeventoError as e:
        print(f"\n❌ Devento SDK error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
