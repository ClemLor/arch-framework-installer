# Arch Framework Installer

## Vision

Arch Framework Installer est un projet dont l'objectif est de fournir une installation Arch Linux entièrement reproductible pour un Framework Laptop.

Le système d'exploitation est considéré comme remplaçable. En cas de panne matérielle, de changement de SSD ou de réinstallation volontaire, l'objectif est de pouvoir retrouver un environnement de travail identique en lançant simplement les scripts du projet.

La priorité est donnée à la simplicité, la lisibilité, la stabilité et la reproductibilité.

---

## Objectifs

- Installer Arch Linux de manière reproductible.
- Utiliser une architecture modulaire.
- Séparer clairement l'installation, la configuration et les dotfiles.
- Documenter chaque décision technique.
- Pouvoir reconstruire un système complet en moins d'une heure.
- Produire des scripts simples, lisibles et idempotents.

---

## Principes

### Le système est jetable

Le système ne doit jamais être considéré comme unique.

Si quelque chose casse, la solution privilégiée est de réinstaller plutôt que de réparer pendant plusieurs heures.

### Chaque décision est documentée

Aucun paquet, service ou configuration ne doit être ajouté sans justification.

Chaque choix est documenté dans le dossier `docs/`.

### Modularité

Chaque composant possède une responsabilité unique.

Exemples :

- stockage
- démarrage
- chiffrement
- réseau
- environnement graphique
- applications

Les composants doivent pouvoir évoluer indépendamment.

### Idempotence

Tous les scripts doivent pouvoir être exécutés plusieurs fois sans produire d'effets indésirables.

### Simplicité

Une solution simple est toujours préférée à une solution complexe si elle répond au besoin.

---

## Architecture

Le projet est organisé en plusieurs couches.

```
Installation
        ↓
Configuration système
        ↓
Applications
        ↓
Dotfiles
```

Chaque couche peut être reconstruite indépendamment.

---

## Dépôts

Le projet est séparé en deux dépôts.

### arch-framework-installer

Contient :

- les scripts d'installation
- les scripts de maintenance
- les configurations système
- la documentation

### dotfiles

Contient :

- Fish
- Niri
- Dank
- Ghostty
- Yazi
- Git
- scripts utilisateur

---

## Documentation

Toute la documentation technique est située dans `docs/`.

Exemples :

- architecture
- stockage
- démarrage
- sécurité
- réseau
- bureau
- maintenance
- récupération

PROJECT.md décrit uniquement la philosophie générale du projet.

---

## Conventions

- Bash pour les opérations système.
- Python pour les traitements complexes si nécessaire.
- Un script = une responsabilité.
- Un fichier ne devrait pas dépasser environ 300 lignes.
- Les commentaires expliquent pourquoi, pas ce que fait le code.
- Les commits Git doivent être petits et atomiques.

---

## Roadmap

Les fonctionnalités seront développées dans l'ordre suivant :

1. Documentation
2. Installation de base
3. Stockage
4. Chiffrement
5. Démarrage
6. Réseau
7. Bureau
8. Applications
9. Bootstrap
10. Maintenance
11. Tests
12. Publication