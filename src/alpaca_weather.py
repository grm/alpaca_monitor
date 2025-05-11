#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour communiquer avec Alpaca Weather via HTTP.
"""

import logging
import time
from typing import Any, Dict, Optional, Callable
import traceback

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class AlpacaWeatherMonitor:
    """Classe pour monitorer un dispositif météo compatible avec le protocole ASCOM Alpaca SafetyMonitor."""

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
        Initialise le moniteur météo Alpaca.

        Args:
            host: Hôte du serveur Alpaca
            port: Port du serveur Alpaca
            device_number: Numéro du dispositif météo
            api_version: Version de l'API Alpaca
            client_id: Identifiant du client
            timeout: Délai d'attente des requêtes en secondes
            max_retries: Nombre maximal de tentatives
            retry_delay: Délai entre les tentatives en millisecondes
        """
        self.base_url = f"http://{host}:{port}"
        self.device_number = device_number
        self.api_version = api_version
        self.client_id = client_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
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
        # Utilisation du SafetyMonitor au lieu de ObservingConditions
        return f"{self.base_url}/api/v{self.api_version}/safetymonitor/{self.device_number}/{endpoint}"

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

        logger.debug(f"Requête {method} à {url} avec paramètres: {request_params}")

        try:
            if method.upper() == "GET":
                response = requests.get(url, params=request_params, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, data=request_params, timeout=self.timeout)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")

            response.raise_for_status()
            
            response_json = response.json()
            logger.debug(f"Réponse reçue: {response_json}")
            
            return response_json

        except RequestException as e:
            logger.error(f"Erreur lors de la requête à {url}: {str(e)}")
            raise

    def _retry_request(self, request_func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Réessaie une requête en cas d'échec.

        Args:
            request_func: Fonction à exécuter pour la requête

        Returns:
            Réponse de l'API

        Raises:
            Exception: Si toutes les tentatives échouent
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = request_func()
                return response
            except Exception as e:
                last_exception = e
                logger.warning(f"Tentative {attempt}/{self.max_retries} échouée: {str(e)}")
                
                if attempt < self.max_retries:
                    logger.info(f"Nouvelle tentative dans {self.retry_delay} ms...")
                    time.sleep(self.retry_delay / 1000)  # Conversion en secondes
        
        if last_exception:
            logger.error(f"Échec après {self.max_retries} tentatives. Dernière erreur: {str(last_exception)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise last_exception
        
        # Ne devrait jamais arriver mais au cas où
        raise Exception(f"Échec après {self.max_retries} tentatives pour une raison inconnue")

    def connect(self) -> bool:
        """
        Se connecte au dispositif météo.

        Returns:
            True si la connexion est réussie, False sinon
        """
        try:
            # Exécute une requête simple pour tester la connexion sans changer l'état
            def request_func():
                return self._make_request("GET", "issafe")
            
            response = self._retry_request(request_func)
            
            if response.get("ErrorNumber", 0) == 0:
                self.connected = True
                logger.info("Connexion au dispositif météo réussie")
                return True
            else:
                error_msg = response.get('ErrorMessage', 'Erreur inconnue')
                error_num = response.get('ErrorNumber', 0)
                logger.error(f"Erreur lors de la connexion: {error_msg} (ErrorNumber: {error_num})")
                return False
                
        except Exception as e:
            logger.error(f"Échec de la connexion au dispositif météo: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        Se déconnecte du dispositif météo.

        Note: Pour SafetyMonitor, il n'y a pas de déconnexion à proprement parler,
        donc nous marquons simplement notre état local comme déconnecté.
        
        Returns:
            True si la déconnexion est réussie, False sinon
        """
        self.connected = False
        logger.info("Déconnexion du dispositif météo réussie")
        return True

    def is_weather_safe(self) -> bool:
        """
        Vérifie si les conditions météorologiques sont sûres pour l'observation
        en utilisant la méthode isSafe fournie par Alpaca SafetyMonitor.

        Returns:
            True si les conditions sont sûres, False sinon
        """
        if not self.connected:
            logger.warning("Tentative de vérification météo sans connexion active")
            if not self.connect():
                return False

        try:
            # Appel à la méthode isSafe d'Alpaca avec retry
            def request_func():
                return self._make_request("GET", "issafe")
            
            response = self._retry_request(request_func)
            
            if response.get("ErrorNumber", 0) == 0:
                is_safe = bool(response.get("Value", False))
                
                if is_safe:
                    logger.info("Alpaca SafetyMonitor indique que les conditions météorologiques sont favorables")
                else:
                    logger.warning("Alpaca SafetyMonitor indique que les conditions météorologiques sont défavorables")
                    
                return is_safe
            else:
                error_msg = response.get('ErrorMessage', 'Erreur inconnue')
                error_num = response.get('ErrorNumber', 0)
                logger.error(f"Erreur lors de la vérification météo: {error_msg} (ErrorNumber: {error_num})")
                return False
                
        except Exception as e:
            logger.error(f"Échec de la vérification météo: {str(e)}")
            return False 