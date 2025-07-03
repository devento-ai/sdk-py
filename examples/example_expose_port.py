#!/usr/bin/env python3
"""Example of exposing ports from a Tavor sandbox."""

import time
from tavor import Tavor


def main():
    # Create a Tavor client
    client = Tavor()

    print("Creating a new sandbox...")
    with client.box() as box:
        print("Waiting for sandbox to be ready...")
        box.wait_until_ready()

        print("Starting a simple HTTP server on port 3000...")
        box.run("""
cat > server.py << 'EOF'
import http.server
import socketserver

PORT = 3000

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Server running on port {PORT}")
    httpd.serve_forever()
EOF

nohup python3 server.py > /dev/null 2>&1 & disown
        """)

        # Give the server a moment to start
        time.sleep(2)

        print("Exposing port 3000...")
        exposed_port = box.expose_port(3000)

        print("Port exposed successfully!")
        print(f"  Target port: {exposed_port.target_port}")
        print(f"  Proxy port: {exposed_port.proxy_port}")
        print(f"  Expires at: {exposed_port.expires_at}")

        # You can now access your service from outside the sandbox
        # using the proxy_port on the sandbox's hostname

        print("\nKeeping sandbox alive for 30 seconds...")
        print("You can test the exposed port during this time.")
        time.sleep(30)

    print("Done!")


if __name__ == "__main__":
    main()
