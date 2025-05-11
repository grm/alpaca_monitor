#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour communiquer avec EKOS via DBUS.
"""

import logging
from typing import Any, Dict, Optional

from dasbus.connection import SessionMessageBus
from dasbus.error import DBusError

logger = logging.getLogger(__name__)


class EkosController:
    """Classe pour contrôler EKOS via DBUS."""

    def __init__(
        self,
        dbus_service: str = "org.kde.kstars",
        dbus_path: str = "/KStars/EKOS",
        dbus_interface: str = "org.kde.kstars.EKOS",
        scheduler_interface: str = "org.kde.kstars.EKOS.Scheduler",
    ):
        """
        Initialise le contrôleur EKOS.

        Args:
            dbus_service: Nom du service DBUS
            dbus_path: Chemin de l'objet DBUS
            dbus_interface: Interface DBUS principale
            scheduler_interface: Interface DBUS du scheduler
        """
        self.dbus_service = dbus_service
        self.dbus_path = dbus_path
        self.dbus_interface = dbus_interface
        self.scheduler_interface = scheduler_interface
        self.bus = None
        self.ekos = None
        self.scheduler = None
        self.connected = False
        logger.info(f"EkosController initialisé avec service DBUS {dbus_service}")

    def connect(self) -> bool:
        """
        Se connecte à EKOS via DBUS.

        Returns:
            True si la connexion est réussie, False sinon
        """
        try:
            # Connexion au bus de session
            self.bus = SessionMessageBus()
            
            # Connexion à EKOS
            self.ekos = self.bus.get_proxy(
                self.dbus_service,
                self.dbus_path
            )
            
            # Connexion au scheduler
            self.scheduler = self.bus.get_proxy(
                self.dbus_service,
                f"{self.dbus_path}/Scheduler"
            )
            
            self.connected = True
            logger.info("Connexion à EKOS réussie")
            return True
            
        except DBusError as e:
            logger.error(f"Échec de la connexion à EKOS: {str(e)}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la connexion à EKOS: {str(e)}")
            self.connected = False
            return False
            
    def disconnect(self) -> bool:
        """
        Se déconnecte d'EKOS.

        Returns:
            True toujours
        """
        self.bus = None
        self.ekos = None
        self.scheduler = None
        self.connected = False
        logger.info("Déconnexion d'EKOS effectuée")
        return True

    def is_connected(self) -> bool:
        """
        Vérifie si la connexion à EKOS est active.

        Returns:
            True si connecté, False sinon
        """
        if not self.connected or not self.bus or not self.ekos:
            return False
            
        try:
            # Essaie d'accéder à une propriété ou méthode pour vérifier la connexion
            _ = self.ekos.getStatus()
            return True
        except Exception:
            self.connected = False
            return False

    def get_scheduler_status(self) -> Optional[int]:
        """
        Obtient le statut actuel du scheduler.

        Returns:
            Code d'état du scheduler, ou None en cas d'erreur
        """
        if not self.is_connected():
            logger.warning("Tentative d'obtenir le statut du scheduler sans connexion active")
            if not self.connect():
                return None
                
        try:
            status = self.scheduler.getStatus()
            logger.debug(f"Statut du scheduler: {status}")
            return status
        except Exception as e:
            logger.error(f"Échec de l'obtention du statut du scheduler: {str(e)}")
            return None

    def start_scheduler(self) -> bool:
        """
        Démarre le scheduler EKOS.

        Returns:
            True si le démarrage est réussi, False sinon
        """
        if not self.is_connected():
            logger.warning("Tentative de démarrage du scheduler sans connexion active")
            if not self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est déjà en cours d'exécution
            status = self.get_scheduler_status()
            
            # Si le scheduler est déjà en cours d'exécution, on ne fait rien
            if status == 1:  # 1 = En cours d'exécution
                logger.info("Le scheduler est déjà en cours d'exécution")
                return True
                
            # Démarrer le scheduler
            result = self.scheduler.start()
            
            if result:
                logger.info("Démarrage du scheduler réussi")
                return True
            else:
                logger.error("Échec du démarrage du scheduler")
                return False
                
        except Exception as e:
            logger.error(f"Échec du démarrage du scheduler: {str(e)}")
            return False

    def stop_scheduler(self) -> bool:
        """
        Arrête le scheduler EKOS.

        Returns:
            True si l'arrêt est réussi, False sinon
        """
        if not self.is_connected():
            logger.warning("Tentative d'arrêt du scheduler sans connexion active")
            if not self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est en cours d'exécution
            status = self.get_scheduler_status()
            
            # Si le scheduler n'est pas en cours d'exécution, on ne fait rien
            if status == 0:  # 0 = Idle/Arrêté
                logger.info("Le scheduler est déjà arrêté")
                return True
                
            # Arrêter le scheduler
            result = self.scheduler.stop()
            
            if result:
                logger.info("Arrêt du scheduler réussi")
                return True
            else:
                logger.error("Échec de l'arrêt du scheduler")
                return False
                
        except Exception as e:
            logger.error(f"Échec de l'arrêt du scheduler: {str(e)}")
            return False
            
    def abort_scheduler(self) -> bool:
        """
        Interrompt immédiatement le scheduler EKOS.

        Returns:
            True si l'interruption est réussie, False sinon
        """
        if not self.is_connected():
            logger.warning("Tentative d'interruption du scheduler sans connexion active")
            if not self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est en cours d'exécution
            status = self.get_scheduler_status()
            
            # Si le scheduler n'est pas en cours d'exécution, on ne fait rien
            if status == 0:  # 0 = Idle/Arrêté
                logger.info("Le scheduler est déjà arrêté")
                return True
                
            # Interrompre le scheduler
            result = self.scheduler.abort()
            
            if result:
                logger.info("Interruption du scheduler réussie")
                return True
            else:
                logger.error("Échec de l'interruption du scheduler")
                return False
                
        except Exception as e:
            logger.error(f"Échec de l'interruption du scheduler: {str(e)}")
            return False 