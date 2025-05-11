#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module contenant des fonctions utilitaires pour l'application.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Charge un fichier de configuration YAML.
    
    Args:
        config_path: Chemin vers le fichier de configuration
        
    Returns:
        Dictionnaire contenant la configuration
        
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        yaml.YAMLError: Si le fichier n'est pas un YAML valide
    """
    logger.debug("Chargement de la configuration depuis %s", config_path)
    
    path = Path(config_path)
    if not path.exists():
        logger.error("Le fichier de configuration %s n'existe pas", config_path)
        raise FileNotFoundError(f"Le fichier {config_path} n'existe pas")
    
    try:
        with open(path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            logger.debug("Configuration chargée avec succès")
            return config
    except yaml.YAMLError as e:
        logger.error("Erreur lors du décodage du fichier YAML: %s", str(e))
        raise


def save_config(config: Dict[str, Any], config_path: str) -> None:
    """
    Sauvegarde un dictionnaire de configuration dans un fichier YAML.
    
    Args:
        config: Dictionnaire de configuration
        config_path: Chemin vers le fichier de configuration
    """
    logger.debug("Sauvegarde de la configuration dans %s", config_path)
    
    path = Path(config_path)
    # Créer le répertoire parent s'il n'existe pas
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(config, file, default_flow_style=False, sort_keys=False)
    
    logger.debug("Configuration sauvegardée avec succès")


def setup_rotating_file_logger(log_file: str, max_size: int, backup_count: int, log_level: str = "INFO") -> None:
    """
    Configure un logger avec rotation de fichiers.
    
    Args:
        log_file: Chemin vers le fichier de log
        max_size: Taille maximale du fichier de log en octets
        backup_count: Nombre de fichiers de sauvegarde à conserver
        log_level: Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Créer le répertoire parent s'il n'existe pas
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configurer le handler de fichier rotatif
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    
    # Définir le format et le niveau de log
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(getattr(logging, log_level))
    
    # Ajouter le handler au logger root
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    logger.debug(f"Logger fichier configuré avec rotation: {log_file}, taille max: {max_size}, copies: {backup_count}") 