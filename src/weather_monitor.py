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
        Initialise le système de surveillance.

        Args:
            config: Dictionnaire contenant la configuration du système
        """
        self.config = config
        self.running = False
        self.weather_monitor = None
        self.ekos_controller = None
        self.last_weather_safe = None
        self.scheduler = schedule
        self.loop = asyncio.get_event_loop()
        
        logger.info("Système de surveillance météorologique initialisé")

    def setup(self) -> bool:
        """
        Configure les composants du système.

        Returns:
            True si la configuration est réussie, False sinon
        """
        try:
            # Initialiser le moniteur météo
            alpaca_config = self.config.get("alpaca", {})
            self.weather_monitor = AlpacaWeatherMonitor(
                host=alpaca_config.get("host", "127.0.0.1"),
                port=alpaca_config.get("port", 11111),
                device_number=alpaca_config.get("device_number", 0)
            )
            
            # Initialiser le contrôleur EKOS
            ekos_config = self.config.get("ekos", {})
            self.ekos_controller = EkosController(
                dbus_service=ekos_config.get("dbus_service", "org.kde.kstars"),
                dbus_path=ekos_config.get("dbus_path", "/KStars/EKOS"),
                dbus_interface=ekos_config.get("dbus_interface", "org.kde.kstars.EKOS"),
                scheduler_interface=ekos_config.get("scheduler_interface", "org.kde.kstars.EKOS.Scheduler")
            )
            
            # Configurer la planification des vérifications météo
            poll_interval = alpaca_config.get("poll_interval", 60)  # par défaut 60 secondes
            self.scheduler.every(poll_interval).seconds.do(self._check_weather_and_update_ekos_wrapper)
            
            logger.info(f"Configuration réussie, vérification météo planifiée toutes les {poll_interval} secondes")
            return True
            
        except Exception as e:
            logger.error(f"Échec de la configuration du système: {str(e)}")
            return False

    def _check_weather_and_update_ekos_wrapper(self) -> None:
        """
        Wrapper pour exécuter la fonction asynchrone check_weather_and_update_ekos
        dans la boucle asyncio.
        """
        if self.running:
            asyncio.run_coroutine_threadsafe(self.check_weather_and_update_ekos(), self.loop)

    async def check_weather_and_update_ekos(self) -> None:
        """
        Vérifie les conditions météorologiques et met à jour l'état du scheduler EKOS
        en fonction de celles-ci.
        """
        if not self.running:
            logger.warning("Vérification météo ignorée car le système n'est pas en cours d'exécution")
            return

        logger.info("Vérification des conditions météorologiques...")
        
        try:
            # Vérifier si les conditions météorologiques sont favorables en utilisant isSafe d'Alpaca
            is_weather_safe = self.weather_monitor.is_weather_safe()
            
            # Si le temps est le même que la dernière vérification, ne rien faire
            if self.last_weather_safe is not None and self.last_weather_safe == is_weather_safe:
                logger.debug(f"Pas de changement dans les conditions météorologiques: sûr = {is_weather_safe}")
                return
                
            self.last_weather_safe = is_weather_safe
            
            # Agir en fonction des conditions météorologiques
            if is_weather_safe:
                logger.info("Conditions météorologiques favorables, démarrage du scheduler EKOS")
                await self.ekos_controller.start_scheduler()
            else:
                logger.warning("Conditions météorologiques défavorables, arrêt du scheduler EKOS")
                # On utilise abort pour un arrêt immédiat en cas de conditions météo dangereuses
                await self.ekos_controller.abort_scheduler()
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des conditions météorologiques: {str(e)}")

    def start(self) -> bool:
        """
        Démarre le système de surveillance.

        Returns:
            True si le démarrage est réussi, False sinon
        """
        logger.info("Démarrage du système de surveillance météorologique...")
        
        if self.running:
            logger.warning("Le système est déjà en cours d'exécution")
            return True
            
        # Configurer les composants si ce n'est pas déjà fait
        if not self.weather_monitor or not self.ekos_controller:
            if not self.setup():
                logger.error("Échec du démarrage du système: la configuration a échoué")
                return False
                
        # Connexion au dispositif météo
        if not self.weather_monitor.connect():
            logger.error("Échec du démarrage du système: impossible de se connecter au dispositif météo")
            return False
        
        # Connexion à EKOS (async)
        connect_result = self.loop.run_until_complete(self.ekos_controller.connect())
        if not connect_result:
            logger.error("Échec du démarrage du système: impossible de se connecter à EKOS")
            self.weather_monitor.disconnect()
            return False
            
        self.running = True
        
        # Vérifier les conditions météorologiques immédiatement au démarrage
        self.loop.run_until_complete(self.check_weather_and_update_ekos())
        
        logger.info("Système de surveillance météorologique démarré avec succès")
        return True

    def stop(self) -> bool:
        """
        Arrête le système de surveillance.

        Returns:
            True si l'arrêt est réussi, False sinon
        """
        logger.info("Arrêt du système de surveillance météorologique...")
        
        if not self.running:
            logger.warning("Le système n'est pas en cours d'exécution")
            return True
            
        self.running = False
        
        # Annuler toutes les tâches planifiées
        self.scheduler.clear()
        
        # Déconnexion du dispositif météo
        if self.weather_monitor:
            self.weather_monitor.disconnect()
            
        # Déconnexion d'EKOS
        if self.ekos_controller:
            self.ekos_controller.disconnect()
            
        logger.info("Système de surveillance météorologique arrêté avec succès")
        return True

    def run(self) -> None:
        """
        Exécute le système de surveillance en boucle jusqu'à interruption.
        """
        if not self.start():
            logger.error("Impossible de démarrer le système de surveillance")
            return
            
        logger.info("Système de surveillance en cours d'exécution, appuyez sur Ctrl+C pour arrêter")
        
        # Configurer le gestionnaire de signaux pour arrêter proprement
        def signal_handler(sig, frame):
            logger.info("Signal d'arrêt reçu")
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Boucle principale
        try:
            while self.running:
                self.scheduler.run_pending()
                time.sleep(1)
        except Exception as e:
            logger.error(f"Erreur dans la boucle principale: {str(e)}")
            self.stop()
        finally:
            if self.running:
                self.stop() 