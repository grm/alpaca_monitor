#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module pour effectuer des appels HTTP dans le cadre du contrôle d'EKOS.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

class HttpActionClient:
    """Client pour effectuer des appels HTTP avec gestion des délais et des retries."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialise le client HTTP.
        
        Args:
            config: Configuration des appels HTTP
        """
        self.config = config.get('http_actions', {})
        self.enabled = self.config.get('enabled', False)
        self.timeout = self.config.get('timeout', 10)
        self.max_retries = self.config.get('max_retries', 2)
        self.delay_after_call = self.config.get('delay_after_call', 5)
        self.before_start_actions = self.config.get('before_start', [])
        self.after_stop_actions = self.config.get('after_stop', [])
        
        logger.info(f"Client HTTP initialisé (enabled: {self.enabled})")
        
    async def execute_http_request(self, action: Dict[str, Any]) -> bool:
        """
        Exécute une requête HTTP selon la configuration spécifiée.
        
        Args:
            action: Configuration de l'action HTTP à exécuter
            
        Returns:
            True si la requête a réussi, False sinon
        """
        if not self.enabled:
            logger.debug("Requête HTTP ignorée : client désactivé")
            return True
            
        url = action.get('url')
        method = action.get('method', 'GET').upper()
        headers = action.get('headers', {})
        
        if not url:
            logger.error("URL manquante pour la requête HTTP")
            return False
            
        logger.info(f"Exécution de la requête HTTP {method} vers {url}")
        
        # Utiliser aiohttp pour effectuer la requête de manière asynchrone
        try:
            # Configuration du timeout
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            # Tentatives de connexion (avec retry)
            for attempt in range(self.max_retries + 1):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        if method == 'GET':
                            async with session.get(url, headers=headers) as response:
                                status = response.status
                                if 200 <= status < 300:
                                    logger.info(f"Requête HTTP réussie: {status}")
                                    # Récupérer le corps de la réponse pour le debug
                                    response_text = await response.text()
                                    logger.debug(f"Réponse: {response_text[:500]}")
                                    return True
                                else:
                                    logger.warning(f"Échec de la requête HTTP: {status}")
                                    if attempt < self.max_retries:
                                        logger.info(f"Nouvelle tentative ({attempt+1}/{self.max_retries})")
                                        continue
                                    return False
                        else:
                            logger.warning(f"Méthode HTTP non supportée: {method}")
                            return False
                            
                except aiohttp.ClientError as e:
                    logger.error(f"Erreur de connexion HTTP: {str(e)}")
                    if attempt < self.max_retries:
                        logger.info(f"Nouvelle tentative ({attempt+1}/{self.max_retries})")
                        await asyncio.sleep(1)  # Petite pause avant de réessayer
                        continue
                    return False
                    
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la requête HTTP: {str(e)}")
            return False
            
        return False  # Ne devrait jamais arriver ici

    async def execute_action_sequence(self, actions: List[Dict[str, Any]]) -> bool:
        """
        Exécute une séquence d'actions HTTP avec les délais appropriés.
        
        Args:
            actions: Liste des actions HTTP à exécuter
            
        Returns:
            True si toutes les actions ont réussi, False sinon
        """
        if not self.enabled or not actions:
            return True
            
        logger.info(f"Exécution d'une séquence de {len(actions)} actions HTTP")
        
        for i, action in enumerate(actions):
            # Exécuter la requête
            success = await self.execute_http_request(action)
            
            if not success:
                logger.error(f"Échec de l'action HTTP {i+1}/{len(actions)}")
                return False
                
            # Déterminer le délai à appliquer après cet appel
            if i < len(actions) - 1:  # S'il reste des actions à effectuer
                delay = action.get('delay_after', self.delay_after_call)
                logger.info(f"Pause de {delay} secondes avant la prochaine action HTTP")
                await asyncio.sleep(delay)
                
        logger.info("Séquence d'actions HTTP terminée avec succès")
        return True

    async def before_ekos_start(self) -> bool:
        """
        Exécute les actions HTTP configurées avant le démarrage d'EKOS.
        
        Returns:
            True si toutes les actions ont réussi ou si désactivé, False sinon
        """
        if not self.enabled or not self.before_start_actions:
            return True
            
        logger.info("Exécution des actions HTTP avant démarrage d'EKOS")
        return await self.execute_action_sequence(self.before_start_actions)

    async def after_ekos_stop(self) -> bool:
        """
        Exécute les actions HTTP configurées après l'arrêt d'EKOS.
        
        Returns:
            True si toutes les actions ont réussi ou si désactivé, False sinon
        """
        if not self.enabled or not self.after_stop_actions:
            return True
            
        logger.info("Exécution des actions HTTP après arrêt d'EKOS")
        return await self.execute_action_sequence(self.after_stop_actions) 