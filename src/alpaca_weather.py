#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour communiquer avec Alpaca Weather via HTTP.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class AlpacaWeatherMonitor:
    """Classe pour monitorer un dispositif météo compatible avec le protocole ASCOM Alpaca."""

    def __init__(
        self,
        host: str,
        port: int,
        device_number: int = 0,
        api_version: int = 1,
        client_id: int = 1,
    ):
        """
        Initialise le moniteur météo Alpaca.

        Args:
            host: Hôte du serveur Alpaca
            port: Port du serveur Alpaca
            device_number: Numéro du dispositif météo
            api_version: Version de l'API Alpaca
            client_id: Identifiant du client
        """
        self.base_url = f"http://{host}:{port}"
        self.device_number = device_number
        self.api_version = api_version
        self.client_id = client_id
        self.connected = False
        logger.info(f"AlpacaWeatherMonitor initialisé avec {self.base_url}")

    def _build_url(self, endpoint: str) -> str:
        """
        Construit l'URL pour une requête API Alpaca.

        Args:
            endpoint: Point d'accès API

        Returns:
            URL complète pour la requête
        """
        return f"{self.base_url}/api/v{self.api_version}/observingconditions/{self.device_number}/{endpoint}"

    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Effectue une requête API à Alpaca.

        Args:
            method: Méthode HTTP (GET, PUT)
            endpoint: Point d'accès API
            params: Paramètres de la requête

        Returns:
            Réponse de l'API sous forme de dictionnaire

        Raises:
            RequestException: Si la requête échoue
        """
        url = self._build_url(endpoint)
        request_params = {"ClientID": self.client_id, "ClientTransactionID": int(time.time())}
        
        if params:
            request_params.update(params)

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=request_params, timeout=10)
            elif method.upper() == "PUT":
                response = requests.put(url, data=request_params, timeout=10)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")

            response.raise_for_status()
            return response.json()

        except RequestException as e:
            logger.error(f"Erreur lors de la requête à {url}: {str(e)}")
            raise

    def connect(self) -> bool:
        """
        Se connecte au dispositif météo.

        Returns:
            True si la connexion est réussie, False sinon
        """
        try:
            response = self._make_request("PUT", "connected", {"Connected": True})
            
            if response.get("ErrorNumber", 0) == 0:
                self.connected = True
                logger.info("Connexion au dispositif météo réussie")
                return True
            else:
                logger.error(f"Erreur lors de la connexion: {response.get('ErrorMessage', 'Erreur inconnue')}")
                return False
                
        except Exception as e:
            logger.error(f"Échec de la connexion au dispositif météo: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Se déconnecte du dispositif météo.

        Returns:
            True si la déconnexion est réussie, False sinon
        """
        try:
            response = self._make_request("PUT", "connected", {"Connected": False})
            
            if response.get("ErrorNumber", 0) == 0:
                self.connected = False
                logger.info("Déconnexion du dispositif météo réussie")
                return True
            else:
                logger.error(f"Erreur lors de la déconnexion: {response.get('ErrorMessage', 'Erreur inconnue')}")
                return False
                
        except Exception as e:
            logger.error(f"Échec de la déconnexion du dispositif météo: {str(e)}")
            return False

    def is_weather_safe(self) -> bool:
        """
        Vérifie si les conditions météorologiques sont sûres pour l'observation
        en utilisant la méthode isSafe fournie par Alpaca.

        Returns:
            True si les conditions sont sûres, False sinon
        """
        if not self.connected:
            logger.warning("Tentative de vérification météo sans connexion active")
            if not self.connect():
                return False

        try:
            # Appel à la méthode isSafe d'Alpaca
            response = self._make_request("GET", "issafe")
            
            if response.get("ErrorNumber", 0) == 0:
                is_safe = bool(response.get("Value", False))
                
                if is_safe:
                    logger.info("Alpaca indique que les conditions météorologiques sont favorables")
                else:
                    logger.warning("Alpaca indique que les conditions météorologiques sont défavorables")
                    
                return is_safe
            else:
                logger.error(f"Erreur lors de la vérification météo: {response.get('ErrorMessage', 'Erreur inconnue')}")
                return False
                
        except Exception as e:
            logger.error(f"Échec de la vérification météo: {str(e)}")
            return False 