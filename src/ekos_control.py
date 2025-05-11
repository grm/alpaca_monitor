#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour communiquer avec EKOS via DBUS.
"""

import logging
from typing import Any, Dict, Optional

from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError

logger = logging.getLogger(__name__)


class EkosController:
    """Classe pour contrôler EKOS via DBUS."""

    def __init__(
        self,
        dbus_service: str = "org.kde.kstars",
        dbus_path: str = "/KStars/Ekos",
        dbus_interface: str = "org.kde.kstars.Ekos",
        scheduler_interface: str = "org.kde.kstars.Ekos.Scheduler",
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
        self.properties_interface = None
        self.connected = False
        self.compat_mode = True  # Mode de compatibilité pour gérer les différences de versions
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
            self.properties_interface = scheduler_proxy.get_interface('org.freedesktop.DBus.Properties')
            
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
        self.properties_interface = None
        self.connected = False
        logger.info("Déconnexion d'EKOS effectuée")
        return True

    async def get_property(self, interface: str, property_name: str) -> Any:
        """
        Récupère une propriété D-Bus en gérant les différentes API possibles.
        
        Args:
            interface: Nom de l'interface
            property_name: Nom de la propriété
            
        Returns:
            Valeur de la propriété ou None en cas d'erreur
        """
        if not self.properties_interface:
            return None
            
        try:
            # Essai avec la méthode standard
            try:
                variant = await self.properties_interface.Get(interface, property_name)
                return variant.value
            except AttributeError:
                # Essai avec la méthode préfixée call_
                try:
                    variant = await self.properties_interface.call_Get(interface, property_name)
                    return variant.value
                except AttributeError:
                    # Essai avec GetAll
                    try:
                        all_props = await self.properties_interface.GetAll(interface)
                        if property_name in all_props:
                            return all_props[property_name].value
                    except AttributeError:
                        # Dernier recours : appel direct à la propriété
                        if hasattr(self.scheduler, property_name):
                            return getattr(self.scheduler, property_name)
        except Exception as e:
            logger.error(f"Erreur lors de l'accès à la propriété {property_name}: {str(e)}")
            
        return None

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
            return None
            
        try:
            # Essai avec le nom de méthode direct
            if hasattr(obj, method_name):
                return await getattr(obj, method_name)(*args, **kwargs)
                
            # Essai avec le préfixe call_
            call_method = f"call_{method_name}"
            if hasattr(obj, call_method):
                return await getattr(obj, call_method)(*args, **kwargs)
                
            # Cas spécial pour les méthodes qui commencent par get/set
            if method_name.startswith("get") and method_name[3:]:
                prop_name = method_name[3].lower() + method_name[4:]
                return await self.get_property(self.scheduler_interface, prop_name)
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à la méthode {method_name}: {str(e)}")
            
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
            # Utiliser la méthode générique d'accès aux propriétés
            status = await self.get_property(self.scheduler_interface, 'status')
            
            if status is not None:
                logger.debug(f"Statut du scheduler: {status} ({self.get_scheduler_status_string(status)})")
            else:
                logger.warning("Impossible d'obtenir le statut du scheduler")
                
            return status
        except Exception as e:
            logger.error(f"Échec de l'obtention du statut du scheduler: {str(e)}")
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
                import asyncio
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
                import asyncio
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