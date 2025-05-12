#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module to communicate with Alpaca Weather via HTTP.
"""

import logging
import time
from typing import Any, Dict, Optional, Callable
import traceback

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class AlpacaWeatherMonitor:
    """Class to monitor a weather device compatible with the ASCOM Alpaca SafetyMonitor protocol."""

    def __init__(
        self,
        host: str,
        port: int,
        device_number: int = 0,
        api_version: int = 1,
        client_id: int = 1,
        timeout: int = 5,
        max_retries: int = 3,
        retry_delay: int = 1000,
    ):
        """
        Initialize the Alpaca weather monitor.

        Args:
            host: Alpaca server host
            port: Alpaca server port
            device_number: Weather device number
            api_version: Alpaca API version
            client_id: Client identifier
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retry attempts in milliseconds
        """
        self.base_url = f"http://{host}:{port}"
        self.device_number = device_number
        self.api_version = api_version
        self.client_id = client_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connected = False
        logger.info(f"AlpacaWeatherMonitor initialized with {self.base_url}")

    def _build_url(self, endpoint: str) -> str:
        """
        Build the URL for an Alpaca API request.

        Args:
            endpoint: API endpoint

        Returns:
            Complete URL for the request
        """
        # Using SafetyMonitor instead of ObservingConditions
        return f"{self.base_url}/api/v{self.api_version}/safetymonitor/{self.device_number}/{endpoint}"

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API request to Alpaca.

        Args:
            method: HTTP method (GET, PUT)
            endpoint: API endpoint
            params: Request parameters

        Returns:
            API response as a dictionary

        Raises:
            RequestException: If the request fails
        """
        url = self._build_url(endpoint)
        request_params = {"ClientID": self.client_id, "ClientTransactionID": int(time.time())}
        
        if params:
            request_params.update(params)

        logger.debug(f"Request {method} to {url} with parameters: {request_params}")

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=request_params, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, data=request_params, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            
            response_json = response.json()
            logger.debug(f"Response received: {response_json}")
            
            return response_json

        except RequestException as e:
            logger.error(f"Error during request to {url}: {str(e)}")
            raise

    def _retry_request(self, request_func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Retry a request in case of failure.

        Args:
            request_func: Function to execute for the request

        Returns:
            API response

        Raises:
            Exception: If all attempts fail
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = request_func()
                return response
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed: {str(e)}")
                
                if attempt < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} ms...")
                    time.sleep(self.retry_delay / 1000)  # Convert to seconds
        
        if last_exception:
            logger.error(f"Failed after {self.max_retries} attempts. Last error: {str(last_exception)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise last_exception
        
        # Should never happen but just in case
        raise Exception(f"Failed after {self.max_retries} attempts for an unknown reason")

    async def is_connected(self) -> bool:
        """
        Check if the monitor is connected to the weather device.

        Returns:
            True if connected, False otherwise
        """
        return self.connected

    async def connect(self) -> bool:
        """
        Connect to the weather device asynchronously.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Execute a simple request to test the connection without changing state
            def request_func():
                return self._make_request("GET", "issafe")
            
            response = self._retry_request(request_func)
            
            if response.get("ErrorNumber", 0) == 0:
                self.connected = True
                logger.info("Successfully connected to the weather device")
                return True
            else:
                error_msg = response.get('ErrorMessage', 'Unknown error')
                error_num = response.get('ErrorNumber', 0)
                logger.error(f"Error during connection: {error_msg} (ErrorNumber: {error_num})")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to the weather device: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect from the weather device asynchronously.

        Note: For SafetyMonitor, there's no actual disconnection process,
        so we simply mark our local state as disconnected.
        
        Returns:
            True if disconnection is successful, False otherwise
        """
        self.connected = False
        logger.info("Successfully disconnected from the weather device")
        return True

    async def is_safe(self) -> bool:
        """
        Check if weather conditions are safe for observation
        using the isSafe method provided by Alpaca SafetyMonitor.

        Returns:
            True if conditions are safe, False otherwise
        """
        if not self.connected:
            logger.warning("Attempting to check weather without an active connection")
            if not await self.connect():
                return False

        try:
            # Call to Alpaca's isSafe method with retry
            def request_func():
                return self._make_request("GET", "issafe")
            
            response = self._retry_request(request_func)
            
            if response.get("ErrorNumber", 0) == 0:
                is_safe = bool(response.get("Value", False))
                
                if is_safe:
                    logger.info("Alpaca SafetyMonitor indicates favorable weather conditions")
                else:
                    logger.warning("Alpaca SafetyMonitor indicates unfavorable weather conditions")
                    
                return is_safe
            else:
                error_msg = response.get('ErrorMessage', 'Unknown error')
                error_num = response.get('ErrorNumber', 0)
                logger.error(f"Error during weather check: {error_msg} (ErrorNumber: {error_num})")
                return False
                
        except Exception as e:
            logger.error(f"Failed to check weather: {str(e)}")
            return False 