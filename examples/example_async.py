#!/usr/bin/env python3
"""
Example usage of the Tavor SDK - Asynchronous version

This demonstrates async usage patterns for the Tavor Python SDK.
Replace 'your-api-key-here' with your actual Tavor API key.
"""

import asyncio
from tavor import AsyncTavor, BoxConfig, TavorError


async def main():
    # Initialize the async client with your API key
    async with AsyncTavor(api_key="your-api-key-here") as tavor:
        print("🚀 Tavor SDK Example - Asynchronous")
        print("-" * 40)

        try:
            # Example 1: Simple async command execution
            print("1. Basic async command execution:")
            async with tavor.box() as box:
                result = await box.run("echo 'Hello from async Tavor!'")
                print(f"   Output: {result.stdout.strip()}")
                print(f"   Exit code: {result.exit_code}")

            # Example 2: Parallel execution
            print("\n2. Running commands in parallel:")
            async with tavor.box() as box:
                # Run multiple commands concurrently
                tasks = [
                    box.run("sleep 1 && echo 'Task 1 complete'"),
                    box.run("sleep 1 && echo 'Task 2 complete'"),
                    box.run("sleep 1 && echo 'Task 3 complete'"),
                ]

                results = await asyncio.gather(*tasks)

                for i, result in enumerate(results, 1):
                    print(f"   Task {i}: {result.stdout.strip()}")

            # Example 3: Using custom configuration
            print("\n3. Using custom box configuration:")
            config = BoxConfig(
                cpu=4,  # 4 CPU cores
                mib_ram=4096,  # 4 GB RAM
                timeout=1800,  # 30 minutes
                metadata={"example": "async", "language": "python"},
            )

            async with tavor.box(config=config) as box:
                # Install and use a package
                print("   Installing requests...")
                await box.run("pip install requests")

                result = await box.run("""python -c "
import requests
print('Requests library installed successfully')
print(f'Version: {requests.__version__}')
"
                """)
                print(f"   {result.stdout.strip()}")

            # Example 4: Async streaming output
            print("\n4. Async streaming output:")
            async with tavor.box() as box:

                def print_stdout(line):
                    print(f"   [ASYNC] {line.rstrip()}")

                await box.run(
                    'for i in {1..3}; do echo "Async step $i"; sleep 0.3; done',
                    on_stdout=print_stdout,
                )

            # Example 5: Multiple sandboxes concurrently
            print("\n5. Multiple sandboxes running concurrently:")

            async def run_task_in_sandbox(task_name, command):
                async with tavor.box() as box:
                    result = await box.run(command)
                    return f"{task_name}: {result.stdout.strip()}"

            # Run different tasks in separate sandboxes
            concurrent_tasks = [
                run_task_in_sandbox("Python", "python --version"),
                run_task_in_sandbox("System", "uname -a | cut -d' ' -f1-3"),
                run_task_in_sandbox("Date", "date"),
            ]

            results = await asyncio.gather(*concurrent_tasks)
            for result in results:
                print(f"   {result}")

            print("\n✅ All async examples completed successfully!")

        except TavorError as e:
            print(f"\n❌ Tavor SDK error: {e}")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
