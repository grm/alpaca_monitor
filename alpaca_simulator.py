#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
A simple Alpaca weather API simulator for testing purposes.
This simulator only implements the SafetyMonitor interface's isSafe method.
Weather status can be changed through the console without restarting.
"""

import argparse
import json
import logging
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AlpacaSimulator')

# Global variable to track weather status
WEATHER_STATUS = {
    'is_safe': True  # Weather is safe by default
}

class AlpacaRequestHandler(BaseHTTPRequestHandler):
    """Handler for Alpaca API requests."""
    
    def _set_headers(self, content_type='application/json'):
        """Set the common headers for all responses."""
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS
        self.end_headers()
    
    def _build_response(self, value=None, error_number=0, error_message=''):
        """Build a standard Alpaca API response."""
        # Generate transaction IDs as in the specification
        client_transaction_id = 0
        server_transaction_id = random.randint(0, 1000000000)
        
        # Extract the client transaction ID from the request if provided
        if self.path.find('?') != -1:
            query = parse_qs(urlparse(self.path).query)
            if 'ClientTransactionID' in query:
                try:
                    client_transaction_id = int(query['ClientTransactionID'][0])
                except (ValueError, IndexError):
                    pass
        
        # Build the standard response structure
        response = {
            'ClientTransactionID': client_transaction_id,
            'ServerTransactionID': server_transaction_id,
            'ErrorNumber': error_number,
            'ErrorMessage': error_message
        }
        
        # Add the value if provided
        if value is not None:
            response['Value'] = value
            
        return response
    
    def do_GET(self):
        """Handle GET requests."""
        path = self.path.split('?')[0]  # Remove query parameters
        
        # Log the request
        logger.info(f"Received GET request: {self.path}")
        
        # Handle API discovery request
        if path == '/api/v1/server/interfaces':
            self._set_headers()
            interfaces = ["ISafetyMonitor"]
            response = self._build_response(interfaces)
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Handle the isSafe endpoint
        if path.endswith('/issafe'):
            self._set_headers()
            response = self._build_response(WEATHER_STATUS['is_safe'])
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Handle connected status (always return true for simplicity)
        if path.endswith('/connected'):
            self._set_headers()
            response = self._build_response(True)
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Handle any other request
        self._set_headers()
        response = self._build_response(
            None, 
            error_number=1,
            error_message=f"Endpoint not implemented: {path}"
        )
        self.wfile.write(json.dumps(response).encode())
    
    def do_PUT(self):
        """Handle PUT requests."""
        path = self.path.split('?')[0]  # Remove query parameters
        
        # Log the request
        logger.info(f"Received PUT request: {self.path}")
        
        # Handle the connect endpoint
        if path.endswith('/connected'):
            self._set_headers()
            response = self._build_response(True)
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Handle any other request
        self._set_headers()
        response = self._build_response(
            None, 
            error_number=1,
            error_message=f"Endpoint not implemented: {path}"
        )
        self.wfile.write(json.dumps(response).encode())
        
    def log_message(self, format, *args):
        """Override to disable request logging to stderr."""
        pass

def run_server(port):
    """Run the HTTP server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, AlpacaRequestHandler)
    logger.info(f"Starting Alpaca simulator on port {port}")
    # Run the server in a separate thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return httpd

def console_interface():
    """
    Interactive console interface to control the weather status.
    This allows changing the weather status without restarting the server.
    """
    print("\nAlpaca Weather Simulator Console")
    print("--------------------------------")
    print("Current weather status: " + ("SAFE" if WEATHER_STATUS['is_safe'] else "UNSAFE"))
    print("\nCommands:")
    print("  safe    - Set weather to safe")
    print("  unsafe  - Set weather to unsafe")
    print("  toggle  - Toggle weather status")
    print("  status  - Show current status")
    print("  exit    - Exit the simulator")
    print("--------------------------------")
    
    while True:
        try:
            command = input("\nEnter command: ").strip().lower()
            
            if command == 'safe':
                WEATHER_STATUS['is_safe'] = True
                print("Weather status set to SAFE")
                logger.info("Weather status set to SAFE")
            
            elif command == 'unsafe':
                WEATHER_STATUS['is_safe'] = False
                print("Weather status set to UNSAFE")
                logger.info("Weather status set to UNSAFE")
            
            elif command == 'toggle':
                WEATHER_STATUS['is_safe'] = not WEATHER_STATUS['is_safe']
                status = "SAFE" if WEATHER_STATUS['is_safe'] else "UNSAFE"
                print(f"Weather status toggled to {status}")
                logger.info(f"Weather status toggled to {status}")
            
            elif command == 'status':
                status = "SAFE" if WEATHER_STATUS['is_safe'] else "UNSAFE"
                print(f"Current weather status: {status}")
            
            elif command == 'exit' or command == 'quit':
                print("Exiting simulator...")
                return
            
            else:
                print(f"Unknown command: {command}")
                print("Available commands: safe, unsafe, toggle, status, exit")
                
        except KeyboardInterrupt:
            print("\nExiting simulator...")
            return
        
        except Exception as e:
            print(f"Error: {str(e)}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='ASCOM Alpaca Weather API Simulator')
    parser.add_argument('--port', type=int, default=11111, help='Port to run the server on (default: 11111)')
    args = parser.parse_args()
    
    # Start the server
    httpd = run_server(args.port)
    
    try:
        # Run the console interface
        console_interface()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Stop the server
        httpd.shutdown()

if __name__ == '__main__':
    main() 