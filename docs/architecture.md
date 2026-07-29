# Architecture

## Objectif

L'objectif de cette architecture est de séparer clairement les responsabilités de chaque composant du projet.

Chaque dossier possède un rôle unique et ne doit pas contenir d'éléments qui ne lui appartiennent pas.

Cette organisation permet de rendre le projet simple à comprendre, facile à maintenir et facilement extensible.

---

# Vue d'ensemble

```
arch-framework-installer/
├── config/
├── docs/
├── lib/
├── packages/
├── services/
├── tasks/
├── templates/
├── install.sh
├── uninstall.sh
└── PROJECT.md
```

Les dossiers `assets/` et `tests/`, ainsi que `bootstrap.sh`, sont prévus mais
n'existent pas encore. Ils sont décrits ci-dessous à titre d'intention.

---

# Organisation

## assets/ (prévu)

Contient les ressources statiques utilisées par le projet. Le dossier n'existe
pas encore.

Exemples :

- logos
- captures d'écran
- illustrations
- modèles

Aucun fichier de configuration ne doit être placé ici.

---

## config/

Contient uniquement les fichiers de configuration utilisés par les scripts.

Actuellement, `config/system.conf` contient l'intégralité de la configuration et
constitue la source de vérité. Les autres fichiers `.conf` sont des espaces
réservés vides.

Les scripts lisent ces fichiers mais ne les modifient jamais.

---

## docs/

Documentation complète du projet.

Chaque domaine possède son propre document.

Exemples :

- storage.md
- boot.md
- security.md
- desktop.md

---

## lib/

Bibliothèque de fonctions.

Chaque fichier correspond à un domaine technique.

Exemples :

```
disk.sh      btrfs.sh     luks.sh
bootloader.sh  mount.sh   users.sh
commands.sh  logging.sh   validation.sh
```

La majorité de ces fichiers sont encore vides.

Les fichiers de ce dossier ne doivent jamais être exécutés directement.

Ils sont uniquement importés par les scripts.

---

## packages/

Définition des paquets à installer.

Les listes sont séparées par catégories, avec l'extension `.list` : un paquet
par ligne, sans syntaxe shell.

Exemple :

```
base.list
desktop.list
development.list
fonts.list
```

Les scripts utilisent ces listes pour installer les paquets.

---

## tasks/

Étapes d'installation, numérotées selon leur ordre d'exécution.

```
00_environment.sh   40_mount.sh          90_bootloader.sh
05_disk_selection.sh 50_base_system.sh   95_security.sh
10_storage.sh       60_configuration.sh  98_cleanup.sh
20_encryption.sh    70_packages.sh       99_finish.sh
30_filesystem.sh    80_users.sh
```

Chaque étape utilise les fonctions de `lib/` et n'exécute aucune commande
destructive directement.

---

## templates/

Modèles de fichiers de configuration écrits dans le système cible : `fstab`,
`crypttab`, `hostname`, `hosts`, `locale.gen`, `mkinitcpio.conf`,
`limine.conf`.

---

## Scripts exécutables

Les scripts exécutables sont situés à la racine du dépôt, pas dans un dossier
`scripts/`.

- `install.sh` : orchestrateur unique de l'installation
- `uninstall.sh` : non encore implémenté

Ils utilisent les fonctions présentes dans `lib/`.

---

## services/

Contient les unités systemd fournies par le projet.

Exemples :

- timers
- services utilisateur
- services système

---

## tests/ (prévu)

Tests automatiques. Le dossier n'existe pas encore.

Chaque module important possédera ses propres tests.

En attendant, la seule vérification statique disponible est :

```bash
shellcheck -x install.sh lib/*.sh
```

---

# Flux d'installation

L'installation suit les étapes suivantes :

```
install.sh
        │
        ▼
Lecture de la configuration
        │
        ▼
Préparation du disque
        │
        ▼
Installation d'Arch Linux
        │
        ▼
Configuration du système
        │
        ▼
Installation du chargeur de démarrage
        │
        ▼
Premier démarrage
        │
        ▼
bootstrap.sh
        │
        ▼
Installation des applications
        │
        ▼
Application des dotfiles
        │
        ▼
Système opérationnel
```

---

# Principes d'architecture

## Une responsabilité par fichier

Chaque script possède une responsabilité unique.

## Une responsabilité par dossier

Les dossiers ne doivent pas mélanger plusieurs domaines.

## Idempotence

Tous les scripts doivent pouvoir être exécutés plusieurs fois sans provoquer d'effets indésirables.

## Lisibilité

Le projet privilégie toujours un code clair à une optimisation prématurée.

## Documentation

Toute décision importante doit être documentée avant d'être implémentée.

## Exécution des commandes

Les scripts ne doivent pas exécuter directement les commandes susceptibles de modifier le système.

Ils doivent passer par une fonction commune chargée de :

* journaliser la commande ;
* gérer le mode simulation ;
* détecter les erreurs ;
* afficher un message compréhensible ;
* interrompre l’installation en cas d’échec critique.

Cette abstraction permet d’assurer un comportement homogène dans tous les modules.

---

# Évolutions futures

L'architecture doit permettre l'ajout de nouveaux modules sans modifier les composants existants.

Exemples :

- nouveau bureau
- nouveau chargeur de démarrage
- nouvelle méthode de chiffrement
- nouvelles applications

Les nouveaux modules doivent s'intégrer naturellement à l'organisation existante.