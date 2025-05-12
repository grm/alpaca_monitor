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
        Initialise le contrôleur EKOS.

        Args:
            dbus_service: Nom du service DBUS
            dbus_path: Chemin de l'objet DBUS
            dbus_interface: Interface DBUS principale
            scheduler_interface: Interface DBUS du scheduler
            config: Configuration complète du système
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
        self.compat_mode = True  # Mode de compatibilité pour gérer les différences de versions
        
        # Initialisation du client HTTP si la configuration est fournie
        self.http_client = None
        if config:
            self.http_client = HttpActionClient(config)
        
        logger.info(f"EkosController initialisé avec service DBUS {dbus_service}")

    def get_scheduler_status_string(self, status: int) -> str:
        """
        Convertit le code d'état numérique en chaîne descriptive.
        
        Args:
            status: Code d'état numérique
            
        Returns:
            Description textuelle de l'état
        """
        status_map = {
            0: "Arrêté",
            1: "En cours d'exécution",
            2: "En pause",
            # Ajoutez d'autres états si nécessaire
        }
        return status_map.get(status, f"État inconnu ({status})")

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
        Effectue une opération D-Bus sur une propriété de manière sécurisée.
        
        Args:
            operation: L'opération à effectuer (Get, Set, GetAll)
            interface: Nom de l'interface
            property_name: Nom de la propriété
            value: Valeur à définir (uniquement pour Set)
            properties_interface: Interface Properties pour les opérations (si différente de self.properties_interface)
            
        Returns:
            Résultat de l'opération ou None en cas d'erreur
        """
        # Utiliser l'interface Properties spécifiée ou celle par défaut
        prop_interface = properties_interface if properties_interface is not None else self.properties_interface
        
        if not prop_interface:
            logger.error(f"Impossible d'effectuer l'opération {operation}: interface Properties non disponible")
            return None
            
        try:
            logger.debug(f"Tentative d'opération D-Bus {operation} sur {interface}.{property_name}")
            
            # Liste des méthodes possibles à essayer dans l'ordre
            methods = []
            if operation in ["Get", "Set", "GetAll"]:
                # Préfixé avec call_
                methods.append(f"call_{operation}")
                # Sans préfixe
                methods.append(operation)
                
            # Essayer chaque méthode
            for method_name in methods:
                if hasattr(prop_interface, method_name):
                    try:
                        logger.debug(f"Essai avec la méthode {method_name}")
                        
                        # Appeler la méthode avec les bons arguments selon l'opération
                        if operation == "Get":
                            result = await getattr(prop_interface, method_name)(interface, property_name)
                        elif operation == "Set":
                            result = await getattr(prop_interface, method_name)(interface, property_name, value)
                        elif operation == "GetAll":
                            result = await getattr(prop_interface, method_name)(interface)
                        
                        logger.debug(f"Opération {method_name} réussie: {result}")
                        
                        # Extraire la valeur si c'est un variant
                        if operation == "Get" and hasattr(result, 'value'):
                            return result.value
                        return result
                        
                    except Exception as e:
                        logger.debug(f"Méthode {method_name} a échoué: {str(e)}")
            
            # Tentative via D-Bus brut si les autres approches échouent
            try:
                # Récupérer un nouveau proxy Properties
                bus = MessageBus()
                await bus.connect()
                
                proxy = bus.get_proxy_object(
                    self.dbus_service,
                    f"{self.dbus_path}/Scheduler" if interface.endswith("Scheduler") else self.dbus_path,
                    None  # Pas d'introspection
                )
                new_prop_interface = proxy.get_interface('org.freedesktop.DBus.Properties')
                
                if operation == "Get":
                    result = await new_prop_interface.call_Get(interface, property_name)
                    if hasattr(result, 'value'):
                        return result.value
                    return result
                elif operation == "GetAll":
                    return await new_prop_interface.call_GetAll(interface)
                
            except Exception as e:
                logger.debug(f"Tentative brute a échoué: {str(e)}")
                
            logger.warning(f"Toutes les tentatives d'opération {operation} ont échoué")
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de l'opération D-Bus {operation}: {str(e)}")
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
        Vérifie si la connexion à EKOS est active.

        Returns:
            True si connecté, False sinon
        """
        if not self.connected or not self.bus or not self.ekos or not self.scheduler:
            return False
            
        try:
            # Mode de compatibilité: vérifier simplement la présence des objets
            if self.compat_mode:
                return True
                
            # Vérification complète en essayant d'accéder à une propriété
            status = await self.get_property(self.scheduler_interface, 'status')
            return status is not None
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la connexion: {str(e)}")
            self.connected = False
            return False

    async def initialize_scheduler(self, in_recursion: bool = False) -> bool:
        """
        Initialise le scheduler si nécessaire.
        Cela permet de s'assurer que l'objet scheduler est bien créé et accessible.
        
        Args:
            in_recursion: Indique si cette méthode est appelée de manière récursive
            
        Returns:
            True si l'initialisation réussit, False sinon
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
        Obtient le statut actuel du scheduler.

        Returns:
            Code d'état du scheduler, ou None en cas d'erreur
        """
        if not await self.is_connected():
            logger.warning("Tentative d'obtenir le statut du scheduler sans connexion active")
            if not await self.connect():
                return None
                
        try:
            # Tenter d'initialiser le scheduler en cas de problème, avec flag pour éviter récursion
            if self.scheduler is None:
                if not await self.initialize_scheduler(in_recursion=True):
                    logger.error("Impossible d'initialiser le scheduler")
                    return None
            
            # Approche 1: Utiliser dbus_property_operation directement
            logger.debug("Tentative d'obtention du statut via dbus_property_operation")
            status = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
            
            # Approche 2: Utiliser directement get_status si disponible
            if status is None and hasattr(self.scheduler, 'get_status'):
                logger.debug("Tentative via get_status directement")
                try:
                    status = await self.scheduler.get_status()
                    logger.debug(f"Résultat de get_status: {status}")
                except Exception as e:
                    logger.debug(f"get_status a échoué: {str(e)}")
                    
            # Approche 3: Si tout échoue, essayer de réinitialiser
            if status is None:
                logger.warning("Tentatives d'accès aux propriétés échouées, essai de réinitialisation")
                if await self.initialize_scheduler(in_recursion=True):
                    # Une dernière tentative après réinitialisation
                    status = await self.dbus_property_operation("Get", self.scheduler_interface, 'status')
            
            if status is not None:
                logger.debug(f"Statut du scheduler: {status} ({self.get_scheduler_status_string(status)})")
            else:
                logger.warning("Impossible d'obtenir le statut du scheduler")
                
            return status
        except Exception as e:
            logger.error(f"Échec de l'obtention du statut du scheduler: {str(e)}")
            logger.exception(e)
            return None

    async def start_scheduler(self) -> bool:
        """
        Démarre le scheduler EKOS.

        Returns:
            True si le démarrage est réussi, False sinon
        """
        if not await self.is_connected():
            logger.warning("Tentative de démarrage du scheduler sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est déjà en cours d'exécution
            status = await self.get_scheduler_status()
            
            # Si le scheduler est déjà en cours d'exécution, on ne fait rien
            if status == 1:  # 1 = En cours d'exécution
                logger.info("Le scheduler est déjà en cours d'exécution")
                return True
                
            # Démarrer le scheduler en utilisant la méthode générique
            result = await self.call_method(self.scheduler, "start")
            logger.info("Commande de démarrage du scheduler envoyée")
            
            # En mode compatibilité, on considère que c'est un succès
            if self.compat_mode:
                return True
                
            # Vérifier que le statut a bien changé (avec quelques tentatives)
            for _ in range(3):
                # Attendre un peu que le changement d'état prenne effet
                await asyncio.sleep(1)
                
                new_status = await self.get_scheduler_status()
                if new_status == 1:  # 1 = En cours d'exécution
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
            True si l'arrêt est réussi, False sinon
        """
        if not await self.is_connected():
            logger.warning("Tentative d'arrêt du scheduler sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Vérifier si le scheduler est en cours d'exécution
            status = await self.get_scheduler_status()
            
            # Si le scheduler n'est pas en cours d'exécution ou si on ne peut pas déterminer son état, on ne fait rien
            if status is None or status != 1:  # Si différent de 1 (En cours d'exécution)
                logger.info(f"Le scheduler n'est pas en cours d'exécution (statut: {status}), aucune action requise")
                return True
                
            # Arrêter le scheduler en utilisant la méthode générique
            result = await self.call_method(self.scheduler, "stop")
            logger.info("Commande d'arrêt du scheduler envoyée")
            
            # En mode compatibilité, on considère que c'est un succès
            if self.compat_mode:
                return True
                
            # Vérifier que le statut a bien changé (avec quelques tentatives)
            for _ in range(3):
                # Attendre un peu que le changement d'état prenne effet
                await asyncio.sleep(1)
                
                new_status = await self.get_scheduler_status()
                if new_status == 0:  # 0 = Arrêté
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
            True si l'arrêt est réussi, False sinon
        """
        # Réutiliser la méthode abort_scheduler car il n'y a pas de différence
        # dans l'interface D-Bus entre "stop" et "abort"
        return await self.abort_scheduler()

    async def is_ekos_running(self) -> bool:
        """
        Vérifie si EKOS est en cours d'exécution.
        
        Returns:
            True si EKOS est en cours d'exécution, False sinon
        """
        if not await self.is_connected():
            logger.warning("Tentative de vérification d'EKOS sans connexion active")
            if not await self.connect():
                return False
                
        try:
            # Vérifier l'état d'EKOS via la propriété ekosStatus
            logger.debug("Vérification de l'état d'EKOS")
            
            # Utiliser l'interface Properties d'EKOS pour récupérer l'état
            if hasattr(self, 'ekos_properties_interface') and self.ekos_properties_interface:
                status = await self.dbus_property_operation("Get", self.dbus_interface, 'ekosStatus', 
                                                            properties_interface=self.ekos_properties_interface)
            else:
                # Repli sur l'interface Properties standard
                status = await self.dbus_property_operation("Get", self.dbus_interface, 'ekosStatus')
            
            if status is not None:
                # Les valeurs possibles de ekosStatus sont:
                # 0 = Idle (non démarré)
                # 1 = En cours d'exécution
                # Autres valeurs possibles selon l'implémentation
                logger.debug(f"État d'EKOS: {status}")
                return status == 1  # 1 = En cours d'exécution
            else:
                # Si on ne peut pas obtenir l'état, essayer de vérifier la présence d'interfaces
                logger.debug("Impossible d'obtenir l'état d'EKOS, vérification des interfaces")
                if self.ekos and self.properties_interface:
                    # En mode compatibilité, supposer qu'EKOS est en cours d'exécution si on a les interfaces
                    if self.compat_mode:
                        logger.debug("Mode compatibilité: EKOS considéré comme en cours d'exécution")
                        return True
                        
                    # Essayer d'accéder à une autre propriété pour vérifier que l'interface est active
                    try:
                        # Essayer indiStatus
                        if hasattr(self, 'ekos_properties_interface') and self.ekos_properties_interface:
                            value = await self.dbus_property_operation("Get", self.dbus_interface, 'indiStatus',
                                                                       properties_interface=self.ekos_properties_interface)
                        else:
                            value = await self.dbus_property_operation("Get", self.dbus_interface, 'indiStatus')
                        return value is not None
                    except Exception as e:
                        logger.debug(f"Échec de la vérification secondaire: {str(e)}")
                
                logger.warning("EKOS n'est pas en cours d'exécution ou inaccessible")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'état d'EKOS: {str(e)}")
            return False

    async def start_ekos(self) -> bool:
        """
        Démarre EKOS s'il n'est pas déjà en cours d'exécution.
        Exécute les appels HTTP configurés avant le démarrage.
        
        Returns:
            True si EKOS est démarré avec succès, False sinon
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
            True si EKOS est arrêté avec succès, False sinon
        """
        # Vérifier si EKOS est en cours d'exécution
        if not await self.is_ekos_running():
            logger.info("EKOS n'est pas en cours d'exécution, aucune action requise")
            return True
            
        logger.info("Tentative d'arrêt d'EKOS")
        
        try:
            # Arrêter d'abord le scheduler si nécessaire
            status = await self.get_scheduler_status()
            if status == 1:  # En cours d'exécution
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
            True si EKOS est en cours d'exécution, False sinon
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
            True si le scheduler est en cours d'exécution, False sinon
        """
        # Vérifier et démarrer EKOS si nécessaire
        if not await self.ensure_ekos_running():
            logger.error("Impossible de démarrer EKOS, le scheduler ne peut pas être démarré")
            return False
            
        # Vérifier l'état du scheduler
        status = await self.get_scheduler_status()
        
        if status == 1:  # En cours d'exécution
            logger.info("Le scheduler est déjà en cours d'exécution")
            return True
            
        # Démarrer le scheduler
        return await self.start_scheduler() 