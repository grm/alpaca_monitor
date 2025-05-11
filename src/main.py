#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module principal de l'application de surveillance météorologique pour EKOS.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from src.utils import load_config, setup_rotating_file_logger
from src.weather_monitor import WeatherMonitoringSystem


def parse_arguments():
    """
    Parse les arguments de ligne de commande.
    
    Returns:
        Les arguments parsés
    """
    parser = argparse.ArgumentParser(
        description="Surveillance météorologique pour contrôler EKOS automatiquement"
    )
    parser.add_argument(
        "-c", "--config", 
        default="config.yaml", 
        help="Chemin vers le fichier de configuration (par défaut: config.yaml)"
    )
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Active le mode verbeux (debug)"
    )
    return parser.parse_args()


def setup_logging(config: Dict[str, Any], verbose: bool = False) -> None:
    """
    Configure le système de logging.
    
    Args:
        config: Dictionnaire de configuration
        verbose: Si True, active le mode verbeux (debug)
    """
    log_config = config.get("logging", {})
    log_level = log_config.get("level", "INFO")
    
    if verbose:
        log_level = "DEBUG"
        
    # Configuration du logger console
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    # Ajout d'un logger fichier si configuré
    log_file = log_config.get("file")
    if log_file:
        max_size = log_config.get("max_size", 10485760)  # 10 Mo par défaut
        backup_count = log_config.get("backup_count", 5)  # 5 fichiers de rotation par défaut
        setup_rotating_file_logger(log_file, max_size, backup_count, log_level)
        
    logger = logging.getLogger(__name__)
    logger.info(f"Niveau de logging configuré à {log_level}")


def main() -> None:
    """Point d'entrée de l'application."""
    try:
        # Parsing des arguments de ligne de commande
        args = parse_arguments()
        
        # Chargement de la configuration
        config = load_config(args.config)
        
        # Configuration du logging
        setup_logging(config, args.verbose)
        logger = logging.getLogger(__name__)
        
        logger.info("Application de surveillance météorologique pour EKOS démarrée")
        logger.info(f"Utilisation du fichier de configuration: {args.config}")
        
        # Création et lancement du système de surveillance
        weather_system = WeatherMonitoringSystem(config)
        weather_system.run()
        
    except KeyboardInterrupt:
        print("\nArrêt de l'application...")
        sys.exit(0)
    except Exception as e:
        print(f"Erreur: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 