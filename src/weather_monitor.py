#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour monitorer les conditions météorologiques et contrôler EKOS en conséquence.
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Any, Dict, Optional

import schedule

from src.alpaca_weather import AlpacaWeatherMonitor
from src.ekos_control import EkosController

logger = logging.getLogger(__name__)


class WeatherMonitoringSystem:
    """
    Système de surveillance météorologique qui contrôle EKOS
    en fonction des conditions météorologiques.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the monitoring system.

        Args:
            config: Dictionary containing the system configuration
        """
        self.config = config
        self.running = False
        self.weather_monitor = None
        self.ekos_controller = None
        self.last_weather_safe = None
        self.scheduler = schedule
        self.loop = asyncio.get_event_loop()
        
        logger.info("Weather monitoring system initialized")

    def setup(self) -> bool:
        """
        Configures the system components.

        Returns:
            True if setup is successful, False otherwise
        """
        try:
            # Initialize the weather monitor
            alpaca_config = self.config.get("alpaca", {})
            self.weather_monitor = AlpacaWeatherMonitor(
                host=alpaca_config.get("host", "127.0.0.1"),
                port=alpaca_config.get("port", 11111),
                device_number=alpaca_config.get("device_number", 0),
                timeout=alpaca_config.get("timeout", 5),
                max_retries=alpaca_config.get("max_retries", 3),
                retry_delay=alpaca_config.get("retry_delay", 1000)
            )
            
            # Initialize the EKOS controller
            ekos_config = self.config.get("ekos", {})
            self.ekos_controller = EkosController(
                dbus_service=ekos_config.get("dbus_service", "org.kde.kstars"),
                dbus_path=ekos_config.get("dbus_path", "/KStars/EKOS"),
                dbus_interface=ekos_config.get("dbus_interface", "org.kde.kstars.EKOS"),
                scheduler_interface=ekos_config.get("scheduler_interface", "org.kde.kstars.EKOS.Scheduler"),
                config=self.config  # Pass the complete configuration
            )
            
            # Configure weather check scheduling
            poll_interval = alpaca_config.get("poll_interval", 60)  # default 60 seconds
            self.scheduler.every(poll_interval).seconds.do(self._check_weather_and_update_ekos_wrapper)
            
            logger.info(f"Setup successful, weather check scheduled every {poll_interval} seconds")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure the system: {str(e)}")
            return False

    def _check_weather_and_update_ekos_wrapper(self) -> None:
        """
        Wrapper to run the asynchronous check_weather_and_update_ekos function
        in the asyncio loop.
        """
        if self.running:
            asyncio.run_coroutine_threadsafe(self.check_weather_and_update_ekos(), self.loop)

    async def check_weather_and_update_ekos(self) -> None:
        """
        Checks weather conditions and updates the EKOS scheduler state accordingly.
        """
        if not self.running:
            logger.warning("Weather check ignored because the system is not running")
            return

        logger.info("Checking weather conditions...")
        
        try:
            # Verify connection to the weather device
            if not await self.weather_monitor.is_connected():
                logger.warning("Weather device not connected, trying to connect...")
                if not await self.weather_monitor.connect():
                    logger.error("Unable to connect to the weather device")
                    return
            
            # Get the weather device status
            is_safe = await self.weather_monitor.is_safe()
            
            # If weather conditions are favorable, start the scheduler
            if is_safe:
                logger.info("Favorable weather conditions, checking EKOS scheduler")
                
                # First check if EKOS is running
                ekos_running = await self.ekos_controller.is_ekos_running()
                
                if not ekos_running:
                    logger.warning("EKOS is not running, trying to start it")
                    if await self.ekos_controller.start_ekos():
                        logger.info("EKOS started successfully")
                    else:
                        logger.error("Unable to start EKOS, scheduler cannot be started")
                        return
                
                # EKOS is now running, load the playlist if configured
                behavior_config = self.config.get("behavior", {})
                ekos_config = self.config.get("ekos", {})
                
                if behavior_config.get("load_playlist", False) and ekos_config.get("playlist_path"):
                    playlist_path = ekos_config.get("playlist_path")
                    status = await self.ekos_controller.get_scheduler_status()
                    
                    # Only load the playlist if the scheduler is not already running
                    if status != 1:  # 1 = Running
                        logger.info(f"Loading EKOS playlist: {playlist_path}")
                        load_result = await self.ekos_controller.load_playlist(playlist_path)
                        
                        if not load_result:
                            logger.error("Failed to load EKOS playlist")
                            # Continue anyway to try to start the scheduler
                        else:
                            logger.info("EKOS playlist loaded successfully")
                
                # Get scheduler status
                status = await self.ekos_controller.get_scheduler_status()
                
                # If the scheduler is not already running, start it
                if status != 1:  # 1 = Running
                    logger.info("Starting EKOS scheduler due to favorable weather conditions")
                    if await self.ekos_controller.start_scheduler():
                        logger.info("EKOS scheduler started successfully")
                    else:
                        logger.error("Failed to start EKOS scheduler")
                else:
                    logger.info("EKOS scheduler is already running")
            
            # If weather conditions are unfavorable, stop the scheduler
            else:
                logger.warning("Unfavorable weather conditions, stopping EKOS scheduler")
                
                # First check if EKOS is running
                ekos_running = await self.ekos_controller.is_ekos_running()
                
                if not ekos_running:
                    logger.info("EKOS is not running, no action required")
                    return
                
                # Get scheduler status
                status = await self.ekos_controller.get_scheduler_status()
                
                # If the scheduler is running, stop it
                if status == 1:  # 1 = Running
                    logger.warning("Stopping EKOS scheduler due to unfavorable weather conditions")
                    if await self.ekos_controller.abort_scheduler():
                        logger.info("EKOS scheduler stopped successfully")
                    else:
                        logger.error("Failed to stop EKOS scheduler")
                else:
                    logger.info("EKOS scheduler is not running, no action required")
                    
                # Option to also stop EKOS completely
                behavior_config = self.config.get('behavior', {})
                if behavior_config.get('stop_ekos_on_unsafe', False):
                    logger.info("Stopping EKOS due to prolonged unfavorable weather conditions")
                    if await self.ekos_controller.stop_ekos():
                        logger.info("EKOS stopped successfully")
                    else:
                        logger.error("Failed to stop EKOS")
                
        except Exception as e:
            logger.error(f"Error during weather check: {str(e)}")
            logger.exception(e)

    def start(self) -> bool:
        """
        Starts the monitoring system.

        Returns:
            True if startup is successful, False otherwise
        """
        logger.info("Starting weather monitoring system...")
        
        if self.running:
            logger.warning("The system is already running")
            return True
            
        # Configure components if not already done
        if not self.weather_monitor or not self.ekos_controller:
            if not self.setup():
                logger.error("Failed to start the system: setup failed")
                return False
                
        # Connect to the weather device (async)
        connect_result = self.loop.run_until_complete(self.weather_monitor.connect())
        if not connect_result:
            logger.error("Failed to start the system: unable to connect to the weather device")
            return False
        
        # Connect to EKOS (async)
        connect_result = self.loop.run_until_complete(self.ekos_controller.connect())
        if not connect_result:
            logger.error("Failed to start the system: unable to connect to EKOS")
            self.loop.run_until_complete(self.weather_monitor.disconnect())
            return False
            
        self.running = True
        
        # Check weather conditions immediately on startup
        self.loop.run_until_complete(self.check_weather_and_update_ekos())
        
        logger.info("Weather monitoring system started successfully")
        return True

    def stop(self) -> bool:
        """
        Stops the monitoring system.

        Returns:
            True if shutdown is successful, False otherwise
        """
        logger.info("Stopping weather monitoring system...")
        
        if not self.running:
            logger.warning("The system is not running")
            return True
            
        self.running = False
        
        # Cancel all scheduled tasks
        self.scheduler.clear()
        
        # Disconnect from the weather device (async)
        if self.weather_monitor:
            self.loop.run_until_complete(self.weather_monitor.disconnect())
            
        # Disconnect from EKOS
        if self.ekos_controller:
            self.ekos_controller.disconnect()
            
        logger.info("Weather monitoring system stopped successfully")
        return True

    def run(self) -> None:
        """
        Runs the monitoring system in a loop until interrupted.
        """
        if not self.start():
            logger.error("Unable to start the monitoring system")
            return
            
        logger.info("Monitoring system running, press Ctrl+C to stop")
        
        # Configure signal handlers for clean shutdown
        def signal_handler(sig, frame):
            logger.info("Stop signal received")
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Main loop
        try:
            while self.running:
                self.scheduler.run_pending()
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            self.stop() 