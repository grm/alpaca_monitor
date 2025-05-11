# KStars Monitoring

Application de surveillance météorologique pour contrôler automatiquement EKOS en fonction des conditions météorologiques.

## Fonctionnalités

- Surveillance des conditions météorologiques via un dispositif compatible ASCOM Alpaca
- Utilisation de la méthode `isSafe` du dispositif météo Alpaca pour déterminer si les conditions sont favorables
- Contrôle automatique du scheduler EKOS (démarrage/arrêt) en fonction des conditions météorologiques via dasbus
- Logging avec rotation de fichiers

## Prérequis

- Python 3.10 ou supérieur
- Un dispositif météo compatible ASCOM Alpaca avec la méthode `isSafe` implémentée
- KStars avec EKOS installé et fonctionnel
- Un système avec D-Bus (généralement présent sur les systèmes Linux)
- PyGObject et ses dépendances système (nécessaires pour dasbus)

## Installation

1. Installez les dépendances système nécessaires pour PyGObject (requises par dasbus) :

   **Pour Ubuntu/Debian** :
   ```bash
   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 libgirepository1.0-dev
   ```

   **Pour Fedora** :
   ```bash
   sudo dnf install python3-gobject python3-gobject-devel gobject-introspection-devel cairo-gobject-devel
   ```

   **Pour Arch Linux** :
   ```bash
   sudo pacman -S python-gobject gobject-introspection cairo
   ```

2. Clonez ce dépôt :
```bash
git clone https://github.com/votre-utilisateur/kstars_monitoring.git
cd kstars_monitoring
```

3. Installez les dépendances Python :
```bash
pip install -r requirements.txt
```

Ou si vous utilisez pipenv :
```bash
pipenv install
pipenv shell
```

## Configuration

Créez ou modifiez le fichier `config.yaml` pour définir vos paramètres :

```yaml
# Configuration pour le monitoring météo et le contrôle d'EKOS

# Configuration de l'observatoire
observatory:
  name: "Mon Observatoire"
  
# Configuration de l'API Weather Alpaca
alpaca:
  host: "127.0.0.1"  # Adresse IP ou nom d'hôte du serveur Alpaca
  port: 11111        # Port du serveur Alpaca
  device_number: 0   # Numéro du dispositif météo
  poll_interval: 60  # Intervalle de vérification en secondes
  
# Configuration de connexion à EKOS via DBUS
ekos:
  dbus_service: "org.kde.kstars"
  dbus_path: "/KStars/EKOS"
  dbus_interface: "org.kde.kstars.EKOS"
  scheduler_interface: "org.kde.kstars.EKOS.Scheduler"
  
# Configuration du logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "kstars_monitoring.log"
  max_size: 10485760  # 10 MB
  backup_count: 5
```

## Utilisation

Pour démarrer l'application avec le fichier de configuration par défaut :

```bash
python -m src.main
```

Avec un fichier de configuration spécifique :

```bash
python -m src.main --config path/to/config.yaml
```

En mode verbeux (debug) :

```bash
python -m src.main --verbose
```

## Résolution des problèmes

### Erreur "No module named 'gi'"

Si vous obtenez l'erreur `ModuleNotFoundError: No module named 'gi'`, cela signifie que PyGObject n'est pas correctement installé. Suivez ces étapes :

1. Installez les dépendances système mentionnées dans la section Installation
2. Réinstallez PyGObject :
   ```bash
   pip install --no-binary :all: PyGObject
   ```
3. Si l'erreur persiste, essayez d'installer directement via votre gestionnaire de paquets :
   ```bash
   # Sur Ubuntu/Debian
   sudo apt install python3-gi
   ```

## À propos de dasbus

L'application utilise la bibliothèque dasbus pour communiquer avec EKOS via D-Bus. Dasbus présente plusieurs avantages :

1. Interface moderne et pythonique pour D-Bus
2. Gestion améliorée des erreurs avec des exceptions spécifiques
3. Support pour les types complexes D-Bus

Bien que dasbus nécessite toujours PyGObject comme dépendance, il offre une API plus propre et plus facile à utiliser que les alternatives.

## Fonctionnement

L'application interroge périodiquement le dispositif météo Alpaca en utilisant la méthode `isSafe` pour vérifier si les conditions sont favorables à l'observation astronomique. Cette méthode est implémentée par le dispositif météo et prend en compte tous les paramètres pertinents (nuages, humidité, vent, pluie, etc.) selon les seuils configurés dans le dispositif lui-même.

Si les conditions sont bonnes (isSafe retourne True), l'application démarre automatiquement le scheduler EKOS. Si les conditions se dégradent (isSafe retourne False), l'application arrête le scheduler pour protéger votre équipement.

La communication avec EKOS s'effectue via D-Bus en utilisant la bibliothèque dasbus, qui offre une interface Python moderne et intuitive pour interagir avec les services D-Bus.

## Développement

1. Installation des dépendances de développement :
```bash
pipenv install --dev
```

2. Tests :
```bash
pipenv run test
```

3. Vérification du style de code :
```bash
pipenv run lint
```

4. Vérification des types :
```bash
pipenv run typecheck
```

## Licence

Ce projet est sous licence [MIT](LICENSE). 