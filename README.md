# Alpaca Weather API Simulator

A simple ASCOM Alpaca SafetyMonitor API simulator for testing purposes. This simulator provides a mock SafetyMonitor device that can have its weather status (safe/unsafe) changed in real-time through the console.

## Features

- Implements the essential `/safetymonitor/{device_number}/issafe` endpoint
- Weather status can be changed on-the-fly without restarting
- Simple console interface for controlling the weather state
- Compatible with your existing Alpaca weather client

## Requirements

- Python 3.6 or higher

## Usage

### Starting the simulator

```bash
python alpaca_simulator.py [--port PORT]
```

Options:
- `--port PORT`: Port to run the server on (default: 11111)

### Controlling the simulator

Once the simulator is running, you can use the following commands in the console:

- `safe`: Set weather to safe conditions
- `unsafe`: Set weather to unsafe conditions
- `toggle`: Toggle between safe and unsafe
- `status`: Display current weather status
- `exit` or `quit`: Exit the simulator

### Example client configuration

Configure your client to connect to the simulator with the following settings:

```yaml
alpaca:
  host: "127.0.0.1"  # Local machine
  port: 11111        # Default simulator port
  device_number: 0   # Device number (default)
```

## Response format

The simulator follows the Alpaca API response format:

```json
{
  "ClientTransactionID": 1747081479, 
  "ErrorNumber": 0, 
  "ErrorMessage": "", 
  "ServerTransactionID": 717774164, 
  "Value": false
}
```

Where `Value` indicates whether the conditions are safe (`true`) or unsafe (`false`).

## API Endpoints

The simulator implements the following endpoints:

- `GET /api/v1/server/interfaces` - Returns available interfaces
- `GET /api/v1/safetymonitor/0/issafe` - Returns current weather safety status
- `GET /api/v1/safetymonitor/0/connected` - Always returns true
- `PUT /api/v1/safetymonitor/0/connected` - Connection control (always succeeds)

## License

This project is provided as free software. 