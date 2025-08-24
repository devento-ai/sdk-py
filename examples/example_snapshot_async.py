#!/usr/bin/env python3
"""Example of using snapshots with Devento async SDK."""

import asyncio
from devento import AsyncDevento


async def main():
    # Initialize the async client (uses DEVENTO_API_KEY env var)
    devento = AsyncDevento()

    # Use a sandbox with automatic cleanup
    async with devento.box() as box:
        print(f"Box {box.id} is ready!")

        # Run initial commands and create a test file
        result = await box.run(
            'w; echo "Hello from Devento!" | tee /test1; ls -al / | grep test1'
        )
        print("Output:", result.stdout)
        print("Exit code:", result.exit_code)

        # List existing snapshots (should be empty initially)
        snapshots = await box.list_snapshots()
        print("Existing snapshots:", snapshots)

        # Create a snapshot of the current state
        print("\nCreating snapshot...")
        snap = await box.create_snapshot(label="initial-state")
        print(f"New snapshot: {snap.id} - Status: {snap.status}")

        # Wait for the snapshot to be ready
        print("Waiting for snapshot to be ready...")
        await box.wait_snapshot_ready(snap.id)
        print("Snapshot is ready!")

        # Modify the file
        print("\nModifying the file...")
        result2 = await box.run(
            'w; ls -al / | grep test1; cat /test1; echo "new" > /test1'
        )
        print("Output:", result2.stdout)
        print("Exit code:", result2.exit_code)

        # Verify the change
        modified_content = await box.run("cat /test1")
        print(f"Modified content: {modified_content.stdout.strip()}")

        # Restore from snapshot
        print(f"\nRestoring snapshot {snap.id}...")
        restored_snap = await box.restore_snapshot(snap.id)
        print(f"Restore initiated - Status: {restored_snap.status}")

        # Wait for the box to be ready after restore
        print("Waiting for box to be ready after restore...")
        await box.wait_until_ready()

        # Verify the file is back to original state
        print("\nVerifying restore...")
        result3 = await box.run("w; ls -al / | grep test1; cat /test1")
        print("Output:", result3.stdout)
        print("Exit code:", result3.exit_code)

        restored_content = await box.run("cat /test1")
        print(f"Restored content: {restored_content.stdout.strip()}")

        # List all snapshots
        final_snapshots = await box.list_snapshots()
        print(f"\nTotal snapshots: {len(final_snapshots)}")
        for s in final_snapshots:
            print(f"  - {s.id}: {s.label or 'no label'} ({s.status})")

        # Clean up: delete the snapshot
        print(f"\nDeleting snapshot {snap.id}...")
        deleted = await box.delete_snapshot(snap.id)
        print(f"Snapshot deleted - Status: {deleted.status}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
