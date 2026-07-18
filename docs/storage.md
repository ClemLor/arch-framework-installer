# Storage

## Objectif

Le stockage constitue la base de l'installation.

Les choix réalisés dans cette partie doivent privilégier :

- la fiabilité
- la simplicité
- les performances
- la facilité de récupération
- la reproductibilité

Toutes les décisions décrites dans ce document concernent uniquement le stockage.

---

# Matériel cible

Le projet est conçu en priorité pour :

- Framework Laptop 13
- Intel Core Ultra 5 125H
- SSD NVMe PCIe
- UEFI

L'installation suppose que l'intégralité du disque est dédiée à Arch Linux.

Le partitionnement est destructif.

---

# Schéma de partitionnement

Le disque est organisé de la manière suivante.

```
Disk
│
├── EFI System Partition
│      FAT32
│      1 GiB
│
└── LUKS2
       │
       └── Btrfs
```

---

# Partition EFI

## Taille

1 GiB

### Pourquoi ?

Cette taille offre une marge confortable pour :

- plusieurs noyaux
- microcode Intel
- fichiers Limine
- futures évolutions

Une partition EFI trop petite devient rapidement une contrainte.

---

# Chiffrement

La totalité du système est chiffrée avec LUKS2.

Seule la partition EFI reste non chiffrée.

Le chiffrement protège :

- les données utilisateur
- les fichiers système
- les snapshots
- les fichiers temporaires

---

# Déverrouillage

Deux méthodes sont prévues.

## TPM2

Méthode principale.

Le TPM du Framework permet un démarrage transparent.

## Phrase de récupération

Toujours conservée.

Elle permet :

- remplacer la carte mère
- réinstaller
- démarrer sans TPM
- récupérer les données

Le TPM ne doit jamais être l'unique moyen de déverrouillage.

---

# Btrfs

Btrfs est utilisé comme système de fichiers principal.

## Raisons

- snapshots
- compression
- checksums
- sous-volumes
- administration simple

---

# Compression

Compression :

```
zstd
```

La compression est activée sur tout le système.

Elle permet :

- réduire les écritures SSD
- gagner de l'espace
- améliorer certaines performances

---

# Sous-volumes

Organisation retenue :

```
@
@home
@snapshots
@cache
@log
```

## Pourquoi ?

Séparer :

- le système
- les données utilisateur
- les snapshots
- les caches
- les journaux

Cette séparation simplifie les sauvegardes et la maintenance.

---

# Snapshots

Les snapshots sont gérés par Snapper.

Création :

- avant les mises à jour
- manuellement
- automatiquement selon la configuration

Les snapshots servent principalement à restaurer rapidement un état fonctionnel.

Ils ne remplacent pas une sauvegarde.

---

# Swap

Le système utilise :

- un swapfile
- zram

## Swapfile

Taille :

32 Go

Utilisé pour :

- l'hibernation
- les charges mémoire importantes

## zram

Utilisé pour :

- améliorer la réactivité
- réduire les accès disque

Les deux mécanismes sont complémentaires.

---

# Montage

Les systèmes de fichiers sont montés avec des options adaptées à un SSD moderne.

Les options exactes sont définies dans la configuration du projet afin de pouvoir évoluer sans modifier les scripts.

---

# Sauvegarde

Les snapshots ne constituent pas une stratégie de sauvegarde.

Les données importantes doivent être sauvegardées indépendamment.

Le projet ne fournit pas de solution de sauvegarde automatique.

---

# Principes

Les règles suivantes doivent toujours être respectées.

- une seule partition système
- une seule partition EFI
- Btrfs partout
- LUKS2 partout sauf EFI
- compression activée
- sous-volumes clairement séparés
- partitionnement simple
- récupération toujours possible

---

# Configuration centralisée

Les paramètres de stockage ne doivent pas être directement écrits dans les scripts.

Ils sont définis dans un fichier de configuration unique situé dans :

```text
config/system.conf
```

Ce fichier constitue la source de vérité de l’installation.

Exemple :

```bash
# Disk
TARGET_DISK="/dev/nvme0n1"
EFI_SIZE="1GiB"

# Encryption
LUKS_ENABLED="true"
LUKS_NAME="cryptroot"
TPM2_ENABLED="true"

# Filesystem
FILESYSTEM="btrfs"
BTRFS_COMPRESSION="zstd"
BTRFS_COMPRESSION_LEVEL="3"

# Memory
SWAP_SIZE="32GiB"
ZRAM_ENABLED="true"
```

Les scripts doivent lire ces valeurs sans modifier le fichier.

Les valeurs par défaut doivent être adaptées au matériel cible, mais peuvent être remplacées avant l’installation.

Les paramètres dangereux, notamment le disque cible, doivent être validés explicitement avant toute opération destructive.

---

# Mode simulation

L’installateur doit fournir un mode simulation accessible avec :

```bash
./install.sh --dry-run
```

Ce mode affiche les opérations prévues sans modifier le système.

Il doit notamment afficher :

* le disque sélectionné ;
* les partitions qui seraient créées ;
* les systèmes de fichiers qui seraient formatés ;
* les sous-volumes Btrfs qui seraient créés ;
* les commandes de chiffrement prévues ;
* les points de montage ;
* les paquets qui seraient installés ;
* les services qui seraient activés.

En mode simulation, aucune commande destructive ne doit être exécutée.

Cela inclut notamment :

* le partitionnement ;
* le formatage ;
* la création d’un conteneur LUKS ;
* l’effacement de données ;
* la modification de la configuration de démarrage ;
* l’enrôlement TPM2.

Les fonctions potentiellement destructives doivent utiliser une fonction commune d’exécution afin de garantir un comportement cohérent.

Exemple conceptuel :

```bash
run_command() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        printf '[DRY-RUN] %q ' "$@"
        printf '\n'
        return 0
    fi

    "$@"
}
```

Le mode simulation ne garantit pas que toutes les commandes réussiront sur le système réel. Il permet cependant de vérifier la configuration, l’ordre des opérations et les commandes générées avant l’installation.

---

# Évolutions futures

Les évolutions possibles comprennent notamment :

- ajout de nouveaux sous-volumes
- optimisation des options de montage
- amélioration de la politique Snapper

Toute évolution doit conserver la compatibilité avec les installations existantes.