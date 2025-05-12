#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify connection with the Alpaca simulator and to diagnose
why EKOS is not starting when weather is set to safe.
"""

import argparse
import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AlpacaTest')

# Import the AlpacaWeatherMonitor class from your project
try:
    from src.alpaca_weather import AlpacaWeatherMonitor
    logger.info("Successfully imported AlpacaWeatherMonitor")
except ImportError as e:
    logger.error(f"Failed to import AlpacaWeatherMonitor: {str(e)}")
    logger.error("Make sure you're running this script from the project root directory")
    sys.exit(1)

# Try to import EkosController too
try:
    from src.ekos_control import EkosController
    logger.info("Successfully imported EkosController")
    HAS_EKOS = True
except ImportError as e:
    logger.error(f"Note: Cannot import EkosController: {str(e)}")
    logger.error("EKOS testing will be skipped")
    HAS_EKOS = False

async def test_alpaca_connection(host, port, device_number):
    """Test connection to the Alpaca weather simulator."""
    logger.info(f"Testing connection to Alpaca weather simulator at {host}:{port}")
    
    # Create an instance of AlpacaWeatherMonitor
    monitor = AlpacaWeatherMonitor(
        host=host,
        port=port,
        device_number=device_number,
        timeout=5,
        max_retries=2
    )
    
    # Try to connect
    logger.info("Attempting to connect to the weather device...")
    connected = await monitor.connect()
    
    if not connected:
        logger.error("Failed to connect to the Alpaca weather simulator")
        return False
    
    logger.info("Successfully connected to the Alpaca weather simulator")
    
    # Check current weather status
    logger.info("Checking current weather status...")
    is_safe = await monitor.is_safe()
    logger.info(f"Current weather status: {'SAFE' if is_safe else 'UNSAFE'}")
    
    # Test with multiple attempts to ensure consistent results
    logger.info("Performing multiple weather checks...")
    for i in range(3):
        start_time = time.time()
        status = await monitor.is_safe()
        elapsed = time.time() - start_time
        logger.info(f"Check {i+1}: Status = {'SAFE' if status else 'UNSAFE'} (took {elapsed:.3f}s)")
    
    # Disconnect
    logger.info("Disconnecting from the weather device...")
    await monitor.disconnect()
    
    return True

async def test_ekos_control(dbus_service, dbus_path, dbus_interface, scheduler_interface):
    """Test connection to EKOS via DBUS."""
    if not HAS_EKOS:
        logger.warning("EKOS controller not available, skipping EKOS tests")
        return False
    
    logger.info(f"Testing connection to EKOS via DBUS (service: {dbus_service})")
    
    # Create a minimal config for the EkosController
    config = {
        "http_actions": {
            "enabled": False
        }
    }
    
    # Create an instance of EkosController
    controller = EkosController(
        dbus_service=dbus_service,
        dbus_path=dbus_path,
        dbus_interface=dbus_interface,
        scheduler_interface=scheduler_interface,
        config=config
    )
    
    # Try to connect to EKOS
    logger.info("Attempting to connect to EKOS...")
    connected = await controller.connect()
    
    if not connected:
        logger.error("Failed to connect to EKOS via DBUS")
        logger.error("Possible causes:")
        logger.error("  1. KStars is not running")
        logger.error("  2. Incorrect DBUS service name or path")
        logger.error("  3. DBUS permissions issue")
        return False
    
    logger.info("Successfully connected to EKOS via DBUS")
    
    # Check if EKOS is running
    is_running = await controller.is_ekos_running()
    logger.info(f"Is EKOS currently running? {'Yes' if is_running else 'No'}")
    
    if not is_running:
        logger.info("Attempting to start EKOS...")
        start_result = await controller.start_ekos()
        if start_result:
            logger.info("EKOS started successfully")
            is_running = True
        else:
            logger.error("Failed to start EKOS")
            logger.error("Possible causes:")
            logger.error("  1. KStars is not properly initialized")
            logger.error("  2. DBUS method call permissions issue")
            logger.error("  3. KStars configuration issue")
    
    # If EKOS is running, check scheduler status
    if is_running:
        logger.info("Checking EKOS scheduler status...")
        status = await controller.get_scheduler_status()
        status_str = controller.get_scheduler_status_string(status)
        logger.info(f"Current scheduler status: {status} ({status_str})")
        
        if status != 1:  # If not running
            logger.info("Attempting to start the scheduler...")
            scheduler_result = await controller.start_scheduler()
            if scheduler_result:
                logger.info("Scheduler started successfully")
            else:
                logger.error("Failed to start the scheduler")
    
    # Disconnect from EKOS
    logger.info("Disconnecting from EKOS...")
    controller.disconnect()
    
    return True

async def run_tests(host, port, device_number, test_ekos, dbus_settings):
    """Run all tests."""
    # Test Alpaca simulator connection
    alpaca_success = await test_alpaca_connection(host, port, device_number)
    
    if not alpaca_success:
        logger.error("Alpaca connection test failed")
        return
    
    # Test EKOS control if requested
    if test_ekos and HAS_EKOS:
        ekos_success = await test_ekos_control(
            dbus_settings.get("service", "org.kde.kstars"),
            dbus_settings.get("path", "/KStars/Ekos"),
            dbus_settings.get("interface", "org.kde.kstars.Ekos"),
            dbus_settings.get("scheduler_interface", "org.kde.kstars.Ekos.Scheduler")
        )
        
        if not ekos_success:
            logger.error("EKOS control test failed")
            return
    
    logger.info("All tests completed")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Test ASCOM Alpaca and EKOS connection')
    parser.add_argument('--host', default='127.0.0.1', help='Alpaca server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=11111, help='Alpaca server port (default: 11111)')
    parser.add_argument('--device', type=int, default=0, help='Alpaca device number (default: 0)')
    parser.add_argument('--test-ekos', action='store_true', help='Also test EKOS control via DBUS')
    parser.add_argument('--dbus-service', default='org.kde.kstars', help='DBUS service name')
    parser.add_argument('--dbus-path', default='/KStars/Ekos', help='DBUS path')
    parser.add_argument('--dbus-interface', default='org.kde.kstars.Ekos', help='DBUS interface')
    parser.add_argument('--scheduler-interface', default='org.kde.kstars.Ekos.Scheduler', help='Scheduler interface')
    
    args = parser.parse_args()
    
    # Collect DBUS settings
    dbus_settings = {
        "service": args.dbus_service,
        "path": args.dbus_path,
        "interface": args.dbus_interface,
        "scheduler_interface": args.scheduler_interface
    }
    
    # Run all tests
    asyncio.run(run_tests(args.host, args.port, args.device, args.test_ekos, dbus_settings))

if __name__ == '__main__':
    main() 