#!/usr/bin/env python3
"""
Example using Devento SDK with environment variables.

This demonstrates how to use environment variables for configuration.
"""

import os
from devento import Devento, BoxConfig


def main():
    print("🌍 Devento SDK Example - Environment Variables")
    print("-" * 40)

    # Set environment variables (in real usage, these would be set in your shell)
    # os.environ['DEVENTO_API_KEY'] = 'your-api-key-here'
    # os.environ['DEVENTO_BASE_URL'] = 'https://api.devento.ai'
    # os.environ['DEVENTO_BOX_CPU'] = '2'
    # os.environ['DEVENTO_BOX_MIB_RAM'] = '2048'
    # os.environ['DEVENTO_BOX_TIMEOUT'] = '1800'

    # Check if API key is set
    if not os.environ.get("DEVENTO_API_KEY"):
        print("❌ DEVENTO_API_KEY environment variable not set!")
        print("\nPlease set it:")
        print("  export DEVENTO_API_KEY='your-api-key-here'")
        return

    print("✓ Using API key from DEVENTO_API_KEY environment variable")

    # Show current environment configuration
    print("\nCurrent environment configuration:")
    print(
        f"  DEVENTO_API_KEY: {'***' + os.environ.get('DEVENTO_API_KEY', '')[-4:] if os.environ.get('DEVENTO_API_KEY') else 'Not set'}"
    )
    print(
        f"  DEVENTO_BASE_URL: {os.environ.get('DEVENTO_BASE_URL', 'Not set (using default)')}"
    )
    print(
        f"  DEVENTO_BOX_CPU: {os.environ.get('DEVENTO_BOX_CPU', 'Not set (using default)')}"
    )
    print(
        f"  DEVENTO_BOX_MIB_RAM: {os.environ.get('DEVENTO_BOX_MIB_RAM', 'Not set (using default)')}"
    )
    print(
        f"  DEVENTO_BOX_TIMEOUT: {os.environ.get('DEVENTO_BOX_TIMEOUT', 'Not set (using default)')}"
    )

    try:
        # Initialize client without any parameters - uses environment variables
        print("\n1. Initialize client using environment variables:")
        devento = Devento()
        print("   ✓ Client initialized successfully")

        # Create a box using default configuration from environment
        print("\n2. Create box with environment defaults:")
        with devento.box() as box:
            result = box.run("echo 'Using environment configuration!'")
            print(f"   Output: {result.stdout.strip()}")

            # Show box configuration
            config = BoxConfig()
            print("\n   Box configuration from environment:")
            print(f"   - CPU: {config.cpu or 'Default (1)'}")
            print(f"   - RAM: {config.mib_ram or 'Default (1024 MiB)'} MiB")
            print(f"   - Timeout: {config.timeout} seconds")

        # Override environment variables with explicit configuration
        print("\n3. Override environment with explicit config:")
        custom_config = BoxConfig(
            cpu=1,  # Override environment CPU
            mib_ram=1024,  # Override environment RAM
            timeout=900,  # Override environment timeout
        )

        with devento.box(custom_config) as box:
            result = box.run("echo 'Using explicit configuration!'")
            print(f"   Output: {result.stdout.strip()}")
            print(f"   - CPU: {custom_config.cpu}")
            print(f"   - RAM: {custom_config.mib_ram} MiB")
            print(f"   - Timeout: {custom_config.timeout} seconds")

        print("\n✅ Environment variable configuration works correctly!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure you have set the DEVENTO_API_KEY environment variable:")
        print("  export DEVENTO_API_KEY='your-api-key-here'")


if __name__ == "__main__":
    main()
