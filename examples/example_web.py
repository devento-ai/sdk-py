#!/usr/bin/env python3
"""
Example usage of the Tavor SDK - Web Support

This demonstrates how to use the web support feature to expose services
to the internet from your Tavor boxes.

Replace 'your-api-key-here' with your actual Tavor API key.
"""

from tavor import Tavor, BoxConfig, TavorError
import time


def main():
    # Initialize the client with your API key
    tavor = Tavor(api_key="your-api-key-here")

    print("🌐 Tavor SDK Example - Web Support")
    print("-" * 40)

    try:
        # Example 1: Basic web server with public URL
        print("1. Starting a simple web server:")
        with tavor.box() as box:
            # Create a simple HTML file
            box.run("""cat > index.html << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>Tavor Web Demo</title>
</head>
<body>
    <h1>Hello from Tavor!</h1>
    <p>This page is served from a Tavor box and accessible via the internet.</p>
    <p>Current time: <span id="time"></span></p>
    <script>
        document.getElementById('time').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
EOF""")

            # Start Python's built-in web server
            box.run("python -m http.server 8080 > server.log 2>&1 &")

            # Give the server time to start
            time.sleep(2)

            # Get the public URL
            public_url = box.get_public_url(8080)
            print("   ✅ Web server started!")
            print(f"   🌍 Public URL: {public_url}")
            print("   📝 This URL is accessible from anywhere on the internet")

            # Test the server locally
            result = box.run(f"curl -s {public_url} | head -5")
            print("\n   Preview of the response:")
            print("   " + result.stdout.replace("\n", "\n   "))

            # Keep the server running for demonstration
            print("\n   Server will run for 10 seconds...")
            time.sleep(10)

        # Example 2: Multiple services on different ports
        print("\n2. Running multiple services:")
        with tavor.box() as box:
            # Start multiple services
            box.run("python -m http.server 8000 > web1.log 2>&1 &")
            box.run("python -m http.server 8001 > web2.log 2>&1 &")
            box.run("python -m http.server 8002 > web3.log 2>&1 &")

            time.sleep(2)

            # Get public URLs for each service
            services = [
                ("Web Server 1", 8000),
                ("Web Server 2", 8001),
                ("Web Server 3", 8002),
            ]

            print("   Multiple services running:")
            for name, port in services:
                url = box.get_public_url(port)
                print(f"   - {name}: {url}")

        # Example 3: Flask application (if Flask is available)
        print("\n3. Flask web application:")
        config = BoxConfig(
            cpu=1,
            mib_ram=1024,
            timeout=3600,
            metadata={"example": "web", "framework": "flask"},
        )

        with tavor.box(config=config) as box:
            # Install Flask
            print("   Installing Flask...")
            box.run("pip install flask")

            # Create a simple Flask app
            box.run('''cat > app.py << 'EOF'
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>Flask on Tavor</h1>
    <p>This Flask app is running in a Tavor box!</p>
    <p><a href="/api/status">Check API Status</a></p>
    """

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'running',
        'time': datetime.now().isoformat(),
        'message': 'Flask app running on Tavor!'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF''')

            # Start the Flask app
            print("   Starting Flask application...")
            box.run("python app.py > flask.log 2>&1 &")

            # Wait for Flask to start
            time.sleep(3)

            # Get the public URL
            flask_url = box.get_public_url(5000)
            print("   ✅ Flask app started!")
            print(f"   🌍 Public URL: {flask_url}")
            print(f"   📡 API endpoint: {flask_url}/api/status")

            # Test the API
            result = box.run(f"curl -s {flask_url}/api/status")
            print("\n   API Response:")
            print(f"   {result.stdout}")

            print("\n   Flask app will run for 10 seconds...")
            time.sleep(10)

        # Example 4: Webhook receiver
        print("\n4. Webhook receiver example:")
        with tavor.box() as box:
            # Create a simple webhook receiver
            box.run("""cat > webhook_server.py << 'EOF'
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        print(f"Received webhook at {self.path}")
        print(f"Headers: {dict(self.headers)}")
        print(f"Body: {body.decode()}")
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {'status': 'received', 'message': 'Webhook processed successfully'}
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        # Custom logging
        print(f"[WEBHOOK] {format % args}")

print("Starting webhook server on port 9000...")
server = HTTPServer(('', 9000), WebhookHandler)
server.serve_forever()
EOF""")

            # Start the webhook server
            box.run("python webhook_server.py > webhook.log 2>&1 &")
            time.sleep(2)

            webhook_url = box.get_public_url(9000)
            print("   ✅ Webhook receiver started!")
            print(f"   🌍 Webhook URL: {webhook_url}")
            print(f"   📨 Send webhooks to: {webhook_url}/webhook")

            # Test the webhook
            print("\n   Testing webhook with a sample payload...")
            box.run(f"""curl -X POST {webhook_url}/webhook \
                -H "Content-Type: application/json" \
                -d '{{"event": "test", "data": {{"message": "Hello Tavor!"}}}}'
            """)

            # Show the webhook logs
            time.sleep(1)
            logs = box.run("tail -n 10 webhook.log")
            print("\n   Webhook server logs:")
            print("   " + logs.stdout.replace("\n", "\n   "))

        print("\n✅ All web examples completed successfully!")
        print("\n💡 Tips:")
        print("   - Public URLs are in the format: https://{port}-{hostname}")
        print("   - Each box gets a unique hostname like 'uuid.tavor.app'")
        print("   - URLs are accessible from anywhere on the internet")
        print("   - Perfect for testing webhooks, sharing demos, or temporary services")

    except TavorError as e:
        print(f"\n❌ Tavor SDK error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
