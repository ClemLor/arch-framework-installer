# Architecture

## Objectif

L'objectif de cette architecture est de séparer clairement les responsabilités de chaque composant du projet.

Chaque dossier possède un rôle unique et ne doit pas contenir d'éléments qui ne lui appartiennent pas.

Cette organisation permet de rendre le projet simple à comprendre, facile à maintenir et facilement extensible.

---

# Vue d'ensemble

```
arch-framework-installer/
├── assets/
├── config/
├── docs/
├── lib/
├── packages/
├── scripts/
├── services/
├── tests/
├── install.sh
├── bootstrap.sh
└── PROJECT.md
```

---

# Organisation

## assets/

Contient les ressources statiques utilisées par le projet.

Exemples :

- logos
- captures d'écran
- illustrations
- modèles

Aucun fichier de configuration ne doit être placé ici.

---

## config/

Contient uniquement les fichiers de configuration utilisés par les scripts.

Exemples :

- variables
- paramètres utilisateur
- listes de modules
- options d'installation

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
disk.sh
btrfs.sh
luks.sh
boot.sh
network.sh
users.sh
desktop.sh
```

Les fichiers de ce dossier ne doivent jamais être exécutés directement.

Ils sont uniquement importés par les scripts.

---

## packages/

Définition des paquets à installer.

Les listes sont séparées par catégories.

Exemple :

```
base.conf
desktop.conf
development.conf
fonts.conf
```

Les scripts utilisent ces listes pour installer les paquets.

---

## scripts/

Scripts exécutables.

Chaque script réalise une tâche complète.

Exemples :

- install.sh
- update.sh
- health-check.sh

Les scripts utilisent les fonctions présentes dans `lib/`.

---

## services/

Contient les unités systemd fournies par le projet.

Exemples :

- timers
- services utilisateur
- services système

---

## tests/

Tests automatiques.

Chaque module important possède ses propres tests.

Les tests permettent de vérifier que les scripts restent fonctionnels après les modifications.

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