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

Les paramètres de stockage ne sont jamais écrits en dur dans le code.

Ils forment un document unique, décrit par des modèles pydantic
(`arch_framework/lib/models/`) et enregistré en JSON :

```json
{
  "disk": {
    "target_disk": "/dev/nvme0n1",
    "efi_size": "1GiB",
    "filesystem": "btrfs",
    "compression": "zstd",
    "compression_level": 3,
    "subvolumes": ["@", "@home", "@snapshots", "@cache", "@log", "@swap"]
  },
  "encryption": {
    "enabled": true,
    "mapper_name": "cryptroot",
    "tpm2_enabled": true,
    "recovery_key": true
  },
  "swap": {
    "size": "32GiB",
    "zram_enabled": true,
    "hibernation_enabled": true
  }
}
```

La sérialisation est déterministe : rejouer ce fichier reconstruit la même
machine, ce qui est la raison d’être du projet.

Les valeurs par défaut viennent du profil Framework
(`arch_framework/profiles/framework.py`) et sont modifiables par le menu guidé.

Les règles de validation sont placées selon leur portée :

| Portée | Emplacement |
| --- | --- |
| Un seul champ | Sur le champ (format de taille, bornes de l’EFI) |
| Plusieurs champs | Sur `InstallConfig` (hibernation exige `@swap`) |
| Dépend du matériel observé | Méthode explicite (`validate_capacity`) |

La dernière catégorie existe parce qu’une taille de disque minimale ne dit rien
de ce qu’il reste à la racine une fois le fichier d’échange retiré : un disque de
64 GiB avec 32 GiB d’échange satisfait le minimum tout en ne laissant que
31 GiB.

Le disque cible n’est jamais accepté sur la seule foi de la configuration. La
vérification est reprise juste avant `wipefs` — voir `docs/security.md`.

---

# Mode simulation

L’installateur fournit un mode simulation :

```bash
python -m arch_framework --install --dry-run --config saved.json
python -m arch_framework --plan-storage
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

Aucune opération destructive ne contourne `lib/command.py`. L’écriture de fichiers
dans la cible passe de même par `TargetSystem.write` : écrire `/mnt/etc/fstab` est
aussi destructeur que `mkfs`, et une simulation ne doit rien créer.

Les valeurs qui n’existent qu’après une étape antérieure — UUID, décalage de
reprise — sont remplacées par des marqueurs explicites, sinon `fstab`, `crypttab`
et `limine.conf` seraient rendus vides et donc invérifiables :

```
UUID=<UUID-of-/dev/nvme0n1p1>  /boot  vfat  defaults,umask=0077  0 2
```

La vérification du disque cible s’applique **aussi** en simulation : répéter une
opération qui serait refusée n’a pas de sens.

Le mode simulation ne garantit pas que toutes les commandes réussiront sur le
système réel. Il permet de vérifier la configuration, l’ordre des opérations, les
unités des arguments et le contenu des fichiers générés.

La séquence complète est par ailleurs figée dans
`tests/golden/install-commands.txt` — voir `docs/testing.md`.

---

# Évolutions futures

Les évolutions possibles comprennent notamment :

- ajout de nouveaux sous-volumes
- optimisation des options de montage
- amélioration de la politique Snapper

Toute évolution doit conserver la compatibilité avec les installations existantes.