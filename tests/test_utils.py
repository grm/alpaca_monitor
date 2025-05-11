#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests pour le module utils.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.utils import load_config, save_config


def test_save_and_load_config():
    """Test que la sauvegarde et le chargement de config fonctionnent."""
    # Créer un fichier temporaire
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as temp_file:
        temp_path = temp_file.name
    
    try:
        # Configuration de test
        test_config = {
            "name": "test_app",
            "version": "0.1.0",
            "settings": {
                "debug": True,
                "log_level": "INFO"
            }
        }
        
        # Sauvegarder la configuration
        save_config(test_config, temp_path)
        
        # Vérifier que le fichier existe
        assert os.path.exists(temp_path)
        
        # Charger la configuration
        loaded_config = load_config(temp_path)
        
        # Vérifier que c'est la même configuration
        assert loaded_config == test_config
    finally:
        # Supprimer le fichier temporaire
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_load_config_file_not_found():
    """Test que load_config lève une exception si le fichier n'existe pas."""
    non_existent_path = "/path/to/non/existent/file.yaml"
    
    with pytest.raises(FileNotFoundError):
        load_config(non_existent_path)


def test_load_config_invalid_yaml():
    """Test que load_config lève une exception si le YAML est invalide."""
    # Créer un fichier temporaire avec un contenu YAML invalide
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as temp_file:
        temp_file.write(b"invalid: yaml: - [")
        temp_path = temp_file.name
    
    try:
        with pytest.raises(yaml.YAMLError):
            load_config(temp_path)
    finally:
        # Supprimer le fichier temporaire
        if os.path.exists(temp_path):
            os.unlink(temp_path) 