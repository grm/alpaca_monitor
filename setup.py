#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

setup(
    name="kstars_monitoring",
    version="0.1.0",
    description="Application Python sans interface graphique ni exposition web",
    author="Votre Nom",
    author_email="votre.email@example.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    # Les dépendances sont gérées par Pipenv, pas besoin de les spécifier ici
    # mais vous pouvez les ajouter si nécessaire pour une installation directe via pip
    # install_requires=["package1", "package2"],
) 