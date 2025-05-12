#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour communiquer avec EKOS via DBUS.
"""

import logging
import asyncio
from typing import Any, Dict, Optional

from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

# Import du client HTTP
from src.http_client import HttpActionClient

logger = logging.getLogger(__name__)


class EkosController:
    """Classe pour contrôler EKOS via DBUS."""

    def __init__(
        self,
        dbus_service: str = "org.kde.kstars",
        dbus_path: str = "/KStars/Ekos",
        dbus_interface: str = "org.kde.kstars.Ekos",
        scheduler_interface: str = "org.kde.kstars.Ekos.Scheduler",
        config: Dict[str, Any] = None,
    ):
        """
        Initialize the EKOS controller.

        Args:
            dbus_service: DBUS service name
            dbus_path: DBUS object path
            dbus_interface: Main DBUS interface
            scheduler_interface: Scheduler DBUS interface
            config: Complete system configuration
        """
        self.dbus_service = dbus_service
        self.dbus_path = dbus_path
        self.dbus_interface = dbus_interface
        self.scheduler_interface = scheduler_interface
        self.bus = None
        self.ekos = None
        self.scheduler = None
        self.properties_interface = None
        self.ekos_properties_interface = None
        self.connected = False
        
        # Initialize HTTP client if configuration is provided
        self.http_client = None
        if config:
            self.http_client = HttpActionClient(config)
        
        logger.info(f"EkosController initialized with DBUS service {dbus_service}")

    def get_scheduler_status_string(self, status: int) -> str:
        """
        Convert numeric status code to descriptive string.
        
        Args:
            status: Numeric status code
            
        Returns:
            Textual description of the status
        """
        status_map = {
            0: "Stopped",
            1: "Running",
            2: "Paused",
            # Add other states if needed
        }
        return status_map.get(status, f"Unknown state ({status})")

    async def connect(self) -> bool:
        """
        Se connecte à EKOS via DBUS.

        Returns:
            True si la connexion est réussie, False sinon
        """
        try:
            # Connexion au bus de session
            self.bus = MessageBus()
            await self.bus.connect()
            
            # Introspection pour obtenir les interfaces
            ekos_introspection = await self.bus.introspect(
                self.dbus_service,
                self.dbus_path
            )
            
            scheduler_introspection = await self.bus.introspect(
                self.dbus_service,
                f"{self.dbus_path}/Scheduler"
            )
            
            # Afficher les interfaces disponibles
            logger.debug("Interfaces disponibles sur le chemin EKOS:")
            for interface in ekos_introspection.interfaces:
                logger.debug(f"  - Interface: {interface.name}")
                for method in interface.methods:
                    logger.debug(f"    - Méthode: {method.name}")
                for prop in interface.properties:
                    logger.debug(f"    - Propriété: {prop.name} (type: {prop.signature})")
                for signal in interface.signals:
                    logger.debug(f"    - Signal: {signal.name}")
            
            logger.debug("Interfaces disponibles sur le chemin Scheduler:")
            for interface in scheduler_introspection.interfaces:
                logger.debug(f"  - Interface: {interface.name}")
                for method in interface.methods:
                    logger.debug(f"    - Méthode: {method.name}")
                for prop in interface.properties:
                    logger.debug(f"    - Propriété: {prop.name} (type: {prop.signature})")
                for signal in interface.signals:
                    logger.debug(f"    - Signal: {signal.name}")
            
            # Création des objets proxy
            ekos_proxy = self.bus.get_proxy_object(
                self.dbus_service,
                self.dbus_path,
                ekos_introspection
            )
            
            scheduler_proxy = self.bus.get_proxy_object(
                self.dbus_service,
                f"{self.dbus_path}/Scheduler",
                scheduler_introspection
            )
            
            # Obtention des interfaces
            self.ekos = ekos_proxy.get_interface(self.dbus_interface)
            self.scheduler = scheduler_proxy.get_interface(self.scheduler_interface)
            
            # Obtention de l'interface Properties pour accéder aux propriétés
            # On utilise l'interface Properties du scheduler par défaut
            self.properties_interface = scheduler_proxy.get_interface('org.freedesktop.DBus.Properties')
            
            # Obtention de l'interface Properties pour EKOS principal également
            self.ekos_properties_interface = ekos_proxy.get_interface('org.freedesktop.DBus.Properties')
            
            # Liste des méthodes disponibles sur les interfaces
            logger.debug("Méthodes disponibles sur l'interface EKOS:")
            for method_name in dir(self.ekos):
                if not method_name.startswith('_'):
                    logger.debug(f"  - {method_name}")
            
            logger.debug("Méthodes disponibles sur l'interface Scheduler:")
            for method_name in dir(self.scheduler):
                if not method_name.startswith('_'):
                    logger.debug(f"  - {method_name}")
            
            logger.debug("Méthodes disponibles sur l'interface Properties:")
            for method_name in dir(self.properties_interface):
                if not method_name.startswith('_'):
                    logger.debug(f"  - {method_name}")
            
            # Vérification immédiate de l'état d'EKOS
            try:
                if self.ekos_properties_interface:
                    status = await self.dbus_property_operation("Get", self.dbus_interface, 'ekosStatus', 
                                                                 properties_interface=self.ekos_properties_interface)
                    logger.debug(f"État actuel d'EKOS: {status}")
            except Exception as e:
                logger.debug(f"Impossible de récupérer l'état initial d'EKOS: {str(e)}")
            
            self.connected = True
            logger.info("Connexion à EKOS réussie")
            return True
            
        except DBusError as e:
            logger.error(f"Échec de la connexion à EKOS: {str(e)}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la connexion à EKOS: {str(e)}")
            logger.exception(e)
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
        self.properties_interface = None
        self.ekos_properties_interface = None
        self.connected = False
        logger.info("Déconnexion d'EKOS effectuée")
        return True

    async def dbus_property_operation(self, operation: str, interface: str, property_name: str, value=None, properties_interface=None) -> Any:
        """
        Perform a D-Bus operation on a property safely.
        
        Args:
            operation: Operation to perform (Get, Set, GetAll)
            interface: Interface name
            property_name: Property name
            value: Value to set (only for Set)
            properties_interface: Properties interface for operations (if different from self.properties_interface)
            
        Returns:
            Operation result or None on error
        """
        # Use specified Properties interface or default
        prop_interface = properties_interface if properties_interface is not None else self.properties_interface
        
        if not prop_interface:
            logger.error(f"Unable to perform {operation} operation: Properties interface not available")
            return None
            
        try:
            logger.debug(f"Attempting D-Bus {operation} operation on {interface}.{property_name}")
            
            # List of possible methods to try in order
            methods = []
            if operation in ["Get", "Set", "GetAll"]:
                # Prefixed with call_
                methods.append(f"call_{operation}")
                # Without prefix
                methods.append(operation)
                
            # Try each method
            for method_name in methods:
                if hasattr(prop_interface, method_name):
                    try:
                        logger.debug(f"Trying with method {method_name}")
                        
                        # Call the method with the right arguments based on the operation
                        if operation == "Get":
                            result = await getattr(prop_interface, method_name)(interface, property_name)
                        elif operation == "Set":
                            result = await getattr(prop_interface, method_name)(interface, property_name, value)
                        elif operation == "GetAll":
                            result = await getattr(prop_interface, method_name)(interface)
                        
                        logger.debug(f"Operation {method_name} successful: {result}")
                        
                        # Extract value if it's a variant
                        if operation == "Get" and hasattr(result, 'value'):
                            return result.value
                        return result
                        
                    except Exception as e:
                        logger.debug(f"Method {method_name} failed: {str(e)}")
            
            logger.warning(f"All attempts at {operation} operation failed")
            return None
            
        except Exception as e:
            logger.error(f"Error during D-Bus {operation} operation: {str(e)}")
            return None

    async def get_property(self, interface: str, property_name: str) -> Any:
        """
        Récupère une propriété D-Bus en gérant les différentes API possibles.
        
        Args:
            interface: Nom de l'interface
            property_name: Nom de la propriété
            
        Returns:
            Valeur de la propriété ou None en cas d'erreur
        """
        # Utiliser notre nouvelle méthode pour effectuer l'opération Get
        return await self.dbus_property_operation("Get", interface, property_name)

    async def call_method(self, obj: Any, method_name: str, *args, **kwargs) -> Any:
        """
        Appelle une méthode D-Bus en gérant les différentes API possibles.
        
        Args:
            obj: Objet sur lequel appeler la méthode
            method_name: Nom de la méthode
            *args, **kwargs: Arguments à passer à la méthode
            
        Returns:
            Résultat de l'appel ou None en cas d'erreur
        """
        if not obj:
            logger.error(f"Impossible d'appeler {method_name}: objet non disponible")
            return None
            
        try:
            logger.debug(f"Tentative d'appel de la méthode {method_name} sur {obj}")
            
            # Essai 1: Appel direct avec le nom de méthode tel quel
            if hasattr(obj, method_name):
                logger.debug(f"Méthode {method_name} trouvée, appel direct")
                return await getattr(obj, method_name)(*args, **kwargs)
                
            # Essai 2: Appel avec le préfixe call_
            call_method = f"call_{method_name}"
            if hasattr(obj, call_method):
                logger.debug(f"Méthode {call_method} trouvée, appel avec préfixe call_")
                return await getattr(obj, call_method)(*args, **kwargs)
                
            # Essai 3: Cas spécial pour les méthodes qui commencent par get/set (propriétés)
            if method_name.startswith("get") and len(method_name) > 3:
                prop_name = method_name[3].lower() + method_name[4:]
                logger.debug(f"Essai d'accès à la propriété {prop_name} via get_property")
                
                # Si l'objet est le scheduler, utiliser l'interface Scheduler
                if obj == self.scheduler:
                    return await self.get_property(self.scheduler_interface, prop_name)
                # Si l'objet est l'interface Ekos principale
                elif obj == self.ekos:
                    return await self.get_property(self.dbus_interface, prop_name)
                # Si c'est l'interface Properties elle-même
                elif obj == self.properties_interface:
                    # Cas spécial pour Get/GetAll
                    if method_name == "get":
                        logger.debug("Cas spécial pour Get")
                        if len(args) >= 2:
                            interface, prop = args[0], args[1]
                            return await self.get_property(interface, prop)
            
            # Si rien ne fonctionne, essayer un dernier moyen via get_property pour les méthodes get_*
            if method_name.startswith("get_") and obj in [self.scheduler, self.ekos]:
                prop_name = method_name[4:]  # Enlever le "get_"
                interface = self.scheduler_interface if obj == self.scheduler else self.dbus_interface
                
                logger.debug(f"Dernier essai: accès à {prop_name} via get_property")
                return await self.get_property(interface, prop_name)
                
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à la méthode {method_name}: {str(e)}")
            logger.exception(e)  # Afficher la stack trace complète
            
        logger.warning(f"Méthode {method_name} non disponible sur l'objet")
        return None

    async def is_connected(self) -> bool:
        """
        Check if the connection to EKOS is active.

        Returns:
            True if connected, False otherwise
        """
        if not self.connected or not self.bus or not self.ekos or not self.scheduler:
            return False
            
        try:
            # Try to access a property to verify connection
            status = await self.get_property(self.scheduler_interface, 'status')
            return status is not None
        except Exception as e:
            logger.error(f"Error checking connection: {str(e)}")
            self.connected = False
            return False

    async def initialize_scheduler(self, in_recursion: bool = False) -> bool:
        """
        Initialise le scheduler si nécessaire.
        Cela permet de s'assurer que l'objet scheduler est bien créé et accessible.
        
        Args:
            in_recursion: Indique si cette méthode est appelée de manière récursive
            
        Returns:
            True if initialization succeeds, False otherwise
        """
        if not await self.is_connected():
            logger.warning("Tentative d'initialisation du scheduler sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Si on a déjà un scheduler fonctionnel, ne rien faire
            if self.scheduler is not None and not in_recursion:
                # Vérification du statut sans passer par get_scheduler_status pour éviter la récursion
                try:
                    logger.debug("Vérification directe du statut pour éviter la récursion")
                    value = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
                    if value is not None:
                        logger.debug(f"Scheduler déjà initialisé avec statut: {value}")
                        return True
                except Exception as e:
                    logger.debug(f"Vérification directe a échoué: {str(e)}")
            
            # Tentative de réinitialisation du scheduler
            logger.info("Tentative d'initialisation/réinitialisation du scheduler")
            
            from dbus_next.message_bus import MessageBus
            
            # Créer une nouvelle connexion au bus
            if self.bus is None:
                self.bus = MessageBus()
                await self.bus.connect()
            
            # Récupérer à nouveau les interfaces
            scheduler_introspection = await self.bus.introspect(
                self.dbus_service,
                f"{self.dbus_path}/Scheduler"
            )
            
            # Créer un nouveau proxy pour le scheduler
            scheduler_proxy = self.bus.get_proxy_object(
                self.dbus_service,
                f"{self.dbus_path}/Scheduler",
                scheduler_introspection
            )
            
            # Récupérer les interfaces
            self.scheduler = scheduler_proxy.get_interface(self.scheduler_interface)
            self.properties_interface = scheduler_proxy.get_interface('org.freedesktop.DBus.Properties')
            
            logger.info("Scheduler réinitialisé avec succès")
            
            # Vérifier que l'initialisation a fonctionné en utilisant dbus_property_operation
            value = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
            if value is not None:
                logger.debug(f"Vérification du scheduler réussie, statut: {value}")
                return True
            
            logger.warning("L'initialisation du scheduler a échoué")
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du scheduler: {str(e)}")
            logger.exception(e)
            return False

    async def get_scheduler_status(self) -> Optional[int]:
        """
        Get the current scheduler status.

        Returns:
            Scheduler status code, or None on error
        """
        if not await self.is_connected():
            logger.warning("Attempting to get scheduler status without active connection")
            if not await self.connect():
                return None
                
        try:
            # Initialize scheduler if needed, with flag to avoid recursion
            if self.scheduler is None:
                if not await self.initialize_scheduler(in_recursion=True):
                    logger.error("Unable to initialize scheduler")
                    return None
            
            # Try direct method call first
            if hasattr(self.scheduler, 'get_status'):
                logger.debug("Attempting via get_status directly")
                try:
                    status = await self.scheduler.get_status()
                    logger.debug(f"Result from get_status: {status}")
                    return status
                except Exception as e:
                    logger.debug(f"get_status failed: {str(e)}")
            
            # Try call_method
            logger.debug("Attempting via call_method on scheduler")
            status = await self.call_method(self.scheduler, "get_status")
            if status is not None:
                logger.debug(f"Scheduler status: {status} ({self.get_scheduler_status_string(status)})")
                return status
                
            # Fallback to property operation
            logger.debug("Attempting to get scheduler status via property operation")
            status = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
            if status is not None:
                logger.debug(f"Scheduler status from property: {status}")
                return status
            
            # If everything fails, try reinitializing
            logger.warning("All property access attempts failed, trying reinitialization")
            if await self.initialize_scheduler(in_recursion=True):
                # One last attempt after reinitialization
                status = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
                if status is not None:
                    return status
                    
            logger.warning("Unable to get scheduler status")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get scheduler status: {str(e)}")
            logger.exception(e)
            return None

    async def start_scheduler(self) -> bool:
        """
        Démarre le scheduler EKOS.

        Returns:
            True if the start succeeds, False otherwise
        """
        if not await self.is_connected():
            logger.warning("Tentative de démarrage du scheduler sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est déjà en cours d'exécution
            status = await self.get_scheduler_status()
            
            # Si le scheduler est déjà en cours d'exécution, on ne fait rien
            if status == 1:  # 1 = Running
                logger.info("Le scheduler est déjà en cours d'exécution")
                return True
                
            # Démarrer le scheduler en utilisant la méthode générique
            result = await self.call_method(self.scheduler, "start")
            logger.info("Commande de démarrage du scheduler envoyée")
            
            # Vérifier que le statut a bien changé (avec quelques tentatives)
            for _ in range(3):
                # Attendre un peu que le changement d'état prenne effet
                await asyncio.sleep(1)
                
                new_status = await self.get_scheduler_status()
                if new_status == 1:  # 1 = Running
                    logger.info("Démarrage du scheduler réussi")
                    return True
            
            logger.warning(f"Le scheduler n'a pas démarré comme prévu. Statut actuel: {new_status} ({self.get_scheduler_status_string(new_status)})")
            return False
                
        except Exception as e:
            logger.error(f"Échec du démarrage du scheduler: {str(e)}")
            return False

    async def abort_scheduler(self) -> bool:
        """
        Arrête le scheduler EKOS immédiatement.

        Returns:
            True if the stop succeeds, False otherwise
        """
        if not await self.is_connected():
            logger.warning("Tentative d'arrêt du scheduler sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est en cours d'exécution
            status = await self.get_scheduler_status()
            
            # Si le scheduler n'est pas en cours d'exécution ou si on ne peut pas déterminer son état, on ne fait rien
            if status is None or status != 1:  # Si différent de 1 (Running)
                logger.info(f"Le scheduler n'est pas en cours d'exécution (statut: {status}), aucune action requise")
                return True
                
            # Arrêter le scheduler en utilisant la méthode générique
            result = await self.call_method(self.scheduler, "stop")
            logger.info("Commande d'arrêt du scheduler envoyée")
            
            # Vérifier que le statut a bien changé (avec quelques tentatives)
            for _ in range(3):
                # Attendre un peu que le changement d'état prenne effet
                await asyncio.sleep(1)
                
                new_status = await self.get_scheduler_status()
                if new_status == 0:  # 0 = Stopped
                    logger.info("Arrêt du scheduler réussi")
                    return True
            
            logger.warning(f"Le scheduler n'a pas été arrêté comme prévu. Statut actuel: {new_status} ({self.get_scheduler_status_string(new_status)})")
            return False
                
        except Exception as e:
            logger.error(f"Échec de l'arrêt du scheduler: {str(e)}")
            return False

    async def stop_scheduler(self) -> bool:
        """
        Arrête le scheduler EKOS normalement.
        Cette méthode est identique à abort_scheduler() car l'interface D-Bus
        ne fournit qu'une méthode stop().

        Returns:
            True if the stop succeeds, False otherwise
        """
        # Réutiliser la méthode abort_scheduler car il n'y a pas de différence
        # dans l'interface D-Bus entre "stop" et "abort"
        return await self.abort_scheduler()

    async def is_ekos_running(self) -> bool:
        """
        Check if EKOS is running.
        
        Returns:
            True if EKOS is running, False otherwise
        """
        if not await self.is_connected():
            logger.warning("Attempting to check EKOS status without active connection")
            if not await self.connect():
                return False
                
        try:
            # Use the get_ekos_status method directly if available
            if hasattr(self.ekos, 'get_ekos_status'):
                status = await self.ekos.get_ekos_status()
                logger.debug(f"EKOS status from get_ekos_status: {status}")
                return status == 1  # 1 = Running
            
            # Alternative approach using call method
            status = await self.call_method(self.ekos, "get_ekos_status")
            if status is not None:
                logger.debug(f"EKOS status from call_method: {status}")
                return status == 1  # 1 = Running
                
            # Fallback to property operation
            logger.debug("Falling back to property operation")
            if hasattr(self, 'ekos_properties_interface') and self.ekos_properties_interface:
                status = await self.dbus_property_operation("Get", self.dbus_interface, 'ekosStatus', 
                                                           properties_interface=self.ekos_properties_interface)
            else:
                status = await self.dbus_property_operation("Get", self.dbus_interface, 'ekosStatus')
            
            if status is not None:
                logger.debug(f"EKOS status from property: {status}")
                return status == 1  # 1 = Running
                
            # If all attempts fail, try a direct method call
            try:
                profiles = await self.ekos.call_get_profiles()
                logger.debug(f"EKOS seems to be running (got profiles: {profiles})")
                return True
            except Exception as e:
                logger.debug(f"Failed to call get_profiles: {str(e)}")
            
            logger.warning("EKOS is not running or inaccessible")
            return False
                
        except Exception as e:
            logger.error(f"Error checking EKOS status: {str(e)}")
            return False

    async def start_ekos(self) -> bool:
        """
        Démarre EKOS s'il n'est pas déjà en cours d'exécution.
        Exécute les appels HTTP configurés avant le démarrage.
        
        Returns:
            True if EKOS is started successfully, False otherwise
        """
        # Vérifier si EKOS est déjà en cours d'exécution
        if await self.is_ekos_running():
            logger.info("EKOS est déjà en cours d'exécution")
            return True
            
        logger.info("Tentative de démarrage d'EKOS")
        
        try:
            # Exécuter les appels HTTP avant le démarrage si configurés
            if self.http_client:
                logger.info("Exécution des actions HTTP avant démarrage d'EKOS")
                if not await self.http_client.before_ekos_start():
                    logger.error("Échec des actions HTTP avant démarrage d'EKOS")
                    return False
            
            # Essayer de se connecter ou de reconnecter au bus
            if not await self.connect():
                logger.error("Impossible de se connecter au bus D-Bus pour démarrer EKOS")
                return False
                
            # Appeler la méthode start d'EKOS
            if hasattr(self.ekos, 'call_start'):
                await self.ekos.call_start()
                logger.info("Commande de démarrage d'EKOS envoyée (call_start)")
            elif hasattr(self.ekos, 'start'):
                await self.ekos.start()
                logger.info("Commande de démarrage d'EKOS envoyée (start)")
            else:
                logger.error("Impossible de trouver la méthode start pour EKOS")
                return False
                
            # Attendre que EKOS démarre
            for _ in range(5):  # Essayer pendant 5 secondes maximum
                await asyncio.sleep(1)
                if await self.is_ekos_running():
                    logger.info("EKOS a démarré avec succès")
                    return True
                    
            logger.warning("EKOS n'a pas démarré dans le délai imparti")
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage d'EKOS: {str(e)}")
            logger.exception(e)
            return False

    async def stop_ekos(self) -> bool:
        """
        Arrête EKOS s'il est en cours d'exécution.
        Exécute les appels HTTP configurés après l'arrêt.
        
        Returns:
            True if EKOS is stopped successfully, False otherwise
        """
        # Vérifier si EKOS est en cours d'exécution
        if not await self.is_ekos_running():
            logger.info("EKOS n'est pas en cours d'exécution, aucune action requise")
            return True
            
        logger.info("Tentative d'arrêt d'EKOS")
        
        try:
            # Arrêter d'abord le scheduler si nécessaire
            status = await self.get_scheduler_status()
            if status == 1:  # Running
                logger.info("Arrêt du scheduler avant d'arrêter EKOS")
                if not await self.abort_scheduler():
                    logger.warning("Échec de l'arrêt du scheduler, tentative d'arrêt d'EKOS malgré tout")
                    
            # Appeler la méthode stop d'EKOS
            if hasattr(self.ekos, 'call_stop'):
                await self.ekos.call_stop()
                logger.info("Commande d'arrêt d'EKOS envoyée (call_stop)")
            elif hasattr(self.ekos, 'stop'):
                await self.ekos.stop()
                logger.info("Commande d'arrêt d'EKOS envoyée (stop)")
            else:
                logger.error("Impossible de trouver la méthode stop pour EKOS")
                return False
                
            # Attendre que EKOS s'arrête
            ekos_stopped = False
            for _ in range(5):  # Essayer pendant 5 secondes maximum
                await asyncio.sleep(1)
                if not await self.is_ekos_running():
                    logger.info("EKOS a été arrêté avec succès")
                    ekos_stopped = True
                    break
                    
            if not ekos_stopped:
                logger.warning("EKOS ne s'est pas arrêté dans le délai imparti")
                return False
                
            # Exécuter les appels HTTP après l'arrêt si configurés
            if self.http_client:
                logger.info("Exécution des actions HTTP après arrêt d'EKOS")
                if not await self.http_client.after_ekos_stop():
                    logger.error("Échec des actions HTTP après arrêt d'EKOS")
                    # On ne considère pas cela comme un échec de l'arrêt d'EKOS lui-même
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt d'EKOS: {str(e)}")
            logger.exception(e)
            return False

    async def ensure_ekos_running(self) -> bool:
        """
        S'assure qu'EKOS est en cours d'exécution, le démarre si nécessaire.
        
        Returns:
            True if EKOS is running, False otherwise
        """
        if not await self.is_ekos_running():
            logger.info("EKOS n'est pas en cours d'exécution, tentative de démarrage")
            return await self.start_ekos()
        return True

    async def ensure_scheduler_running(self) -> bool:
        """
        S'assure que le scheduler EKOS est en cours d'exécution.
        Démarre EKOS si nécessaire, puis démarre le scheduler.
        
        Returns:
            True if the scheduler is running, False otherwise
        """
        # Vérifier et démarrer EKOS si nécessaire
        if not await self.ensure_ekos_running():
            logger.error("Impossible de démarrer EKOS, le scheduler ne peut pas être démarré")
            return False
            
        # Vérifier l'état du scheduler
        status = await self.get_scheduler_status()
        
        if status == 1:  # Running
            logger.info("Le scheduler est déjà en cours d'exécution")
            return True
            
        # Démarrer le scheduler
        return await self.start_scheduler()

    async def load_playlist(self, playlist_path: str) -> bool:
        """
        Charge une playlist dans le scheduler EKOS.
        
        Args:
            playlist_path: Full path to the EKOS playlist file (.esl)
            
        Returns:
            True if the playlist is loaded successfully, False otherwise
        """
        if not playlist_path:
            logger.error("Aucun chemin de playlist spécifié")
            return False
            
        # Normalisation du chemin
        import os
        playlist_path = os.path.abspath(os.path.expanduser(playlist_path))
        
        # Vérifier le format du fichier
        if not playlist_path.endswith('.esl'):
            logger.warning(f"Le fichier de playlist ne se termine pas par .esl: {playlist_path}")
            # Continuer quand même, au cas où ce serait un format valide
            
        # Vérifier l'existence du fichier
        if not os.path.exists(playlist_path):
            logger.error(f"Le fichier de playlist n'existe pas: {playlist_path}")
            return False
        
        if not await self.is_connected():
            logger.warning("Tentative de chargement de playlist sans connexion active")
            if not await self.connect():
                return False
                
        # S'assurer qu'EKOS est en cours d'exécution
        if not await self.ensure_ekos_running():
            logger.error("Impossible de démarrer EKOS, la playlist ne peut pas être chargée")
            return False
            
        # S'assurer que le scheduler est initialisé
        if not await self.initialize_scheduler():
            logger.error("Impossible d'initialiser le scheduler, la playlist ne peut pas être chargée")
            return False
            
        logger.info(f"Tentative de chargement de la playlist: {playlist_path}")
        
        # Liste des méthodes possibles pour charger la playlist
        load_methods = [
            # Méthode call_loadScheduler
            {"attr": "call_load_scheduler", "arg_count": 1},
            # Méthode loadScheduler
            {"attr": "loadScheduler", "arg_count": 1},
            # Méthode call_load
            {"attr": "call_load", "arg_count": 1},
            # Méthode load
            {"attr": "load", "arg_count": 1}
        ]
        
        # Essayer chaque méthode possible
        for method_info in load_methods:
            attr_name = method_info["attr"]
            arg_count = method_info["arg_count"]
            
            if hasattr(self.scheduler, attr_name):
                try:
                    logger.debug(f"Tentative de chargement avec la méthode {attr_name}")
                    
                    if arg_count == 1:
                        await getattr(self.scheduler, attr_name)(playlist_path)
                    else:
                        await getattr(self.scheduler, attr_name)()
                        
                    logger.info(f"Commande de chargement de playlist envoyée ({attr_name}): {playlist_path}")
                    
                    # Attendre un peu pour que le chargement prenne effet
                    await asyncio.sleep(2)
                    
                    # Essayer de vérifier que la playlist a bien été chargée
                    try:
                        # Tenter de récupérer la liste des jobs ou un autre indicateur
                        json_jobs = await self.call_method(self.scheduler, "get_json_jobs")
                        if json_jobs:
                            logger.debug(f"Vérification du chargement réussie: {json_jobs}")
                            return True
                    except Exception as e:
                        logger.debug(f"Impossible de vérifier le chargement: {str(e)}")
                        # On suppose que ça a fonctionné puisqu'il n'y a pas eu d'exception
                        return True
                        
                    return True
                    
                except Exception as e:
                    logger.warning(f"Méthode {attr_name} a échoué: {str(e)}")
                    # Continuer avec la méthode suivante
        
        # Dernière tentative avec call_method générique
        try:
            logger.debug("Tentative avec call_method générique")
            result = await self.call_method(self.scheduler, "load_scheduler", playlist_path)
            
            # Attendre un peu pour que le chargement prenne effet
            await asyncio.sleep(2)
            
            return True
        except Exception as e:
            logger.error(f"Échec de toutes les tentatives de chargement de playlist: {str(e)}")
            
        return False 