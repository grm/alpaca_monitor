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
                device_number=alpaca_config.get("device_number", 0),
                timeout=alpaca_config.get("timeout", 5),
                max_retries=alpaca_config.get("max_retries", 3),
                retry_delay=alpaca_config.get("retry_delay", 1000)
            )
            
            # Initialiser le contrôleur EKOS
            ekos_config = self.config.get("ekos", {})
            self.ekos_controller = EkosController(
                dbus_service=ekos_config.get("dbus_service", "org.kde.kstars"),
                dbus_path=ekos_config.get("dbus_path", "/KStars/EKOS"),
                dbus_interface=ekos_config.get("dbus_interface", "org.kde.kstars.EKOS"),
                scheduler_interface=ekos_config.get("scheduler_interface", "org.kde.kstars.EKOS.Scheduler"),
                config=self.config  # Passer la configuration complète
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
            # Vérifier la connexion au dispositif météo
            if not await self.weather_monitor.is_connected():
                logger.warning("Dispositif météo non connecté, tentative de connexion...")
                if not await self.weather_monitor.connect():
                    logger.error("Impossible de se connecter au dispositif météo")
                    return
            
            # Récupérer l'état du dispositif météo
            is_safe = await self.weather_monitor.is_safe()
            
            # Si conditions météo favorables, démarrer le scheduler
            if is_safe:
                logger.info("Conditions météorologiques favorables, vérification du scheduler EKOS")
                
                # Vérifier d'abord qu'EKOS est en cours d'exécution
                ekos_running = await self.ekos_controller.is_ekos_running()
                
                if not ekos_running:
                    logger.warning("EKOS n'est pas en cours d'exécution, tentative de démarrage")
                    if await self.ekos_controller.start_ekos():
                        logger.info("EKOS a été démarré avec succès")
                    else:
                        logger.error("Impossible de démarrer EKOS, le scheduler ne peut pas être démarré")
                        return
                
                # Récupérer le statut du scheduler
                status = await self.ekos_controller.get_scheduler_status()
                
                # Si le scheduler n'est pas déjà en cours d'exécution, le démarrer
                if status != 1:  # 1 = En cours d'exécution
                    logger.info("Démarrage du scheduler EKOS suite à des conditions météorologiques favorables")
                    if await self.ekos_controller.start_scheduler():
                        logger.info("Scheduler EKOS démarré avec succès")
                    else:
                        logger.error("Échec du démarrage du scheduler EKOS")
                else:
                    logger.info("Le scheduler EKOS est déjà en cours d'exécution")
            
            # Si conditions météo défavorables, arrêter le scheduler
            else:
                logger.warning("Conditions météorologiques défavorables, arrêt du scheduler EKOS")
                
                # Vérifier d'abord qu'EKOS est en cours d'exécution
                ekos_running = await self.ekos_controller.is_ekos_running()
                
                if not ekos_running:
                    logger.info("EKOS n'est pas en cours d'exécution, aucune action requise")
                    return
                
                # Récupérer le statut du scheduler
                status = await self.ekos_controller.get_scheduler_status()
                
                # Si le scheduler est en cours d'exécution, l'arrêter
                if status == 1:  # 1 = En cours d'exécution
                    logger.warning("Arrêt du scheduler EKOS en raison de conditions météorologiques défavorables")
                    if await self.ekos_controller.abort_scheduler():
                        logger.info("Scheduler EKOS arrêté avec succès")
                    else:
                        logger.error("Échec de l'arrêt du scheduler EKOS")
                else:
                    logger.info("Le scheduler EKOS n'est pas en cours d'exécution, aucune action requise")
                    
                # Option pour arrêter également EKOS complètement
                behavior_config = self.config.get('behavior', {})
                if behavior_config.get('stop_ekos_on_unsafe', False):
                    logger.info("Arrêt d'EKOS en raison de conditions météorologiques défavorables prolongées")
                    if await self.ekos_controller.stop_ekos():
                        logger.info("EKOS arrêté avec succès")
                    else:
                        logger.error("Échec de l'arrêt d'EKOS")
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification météorologique: {str(e)}")
            logger.exception(e)

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
                
        # Connexion au dispositif météo (async)
        connect_result = self.loop.run_until_complete(self.weather_monitor.connect())
        if not connect_result:
            logger.error("Échec du démarrage du système: impossible de se connecter au dispositif météo")
            return False
        
        # Connexion à EKOS (async)
        connect_result = self.loop.run_until_complete(self.ekos_controller.connect())
        if not connect_result:
            logger.error("Échec du démarrage du système: impossible de se connecter à EKOS")
            self.loop.run_until_complete(self.weather_monitor.disconnect())
            return False
        
        # Charger la playlist EKOS si configurée
        behavior_config = self.config.get("behavior", {})
        ekos_config = self.config.get("ekos", {})
        
        if behavior_config.get("load_playlist", False) and ekos_config.get("playlist_path"):
            playlist_path = ekos_config.get("playlist_path")
            logger.info(f"Chargement de la playlist EKOS: {playlist_path}")
            load_result = self.loop.run_until_complete(self.ekos_controller.load_playlist(playlist_path))
            
            if not load_result:
                logger.error("Échec du chargement de la playlist EKOS")
                # On ne considère pas cela comme un échec fatal, on continue le démarrage
            else:
                logger.info("Playlist EKOS chargée avec succès")
            
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
        
        # Déconnexion du dispositif météo (async)
        if self.weather_monitor:
            self.loop.run_until_complete(self.weather_monitor.disconnect())
            
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