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
└── System partition
       ├── profil chiffré : LUKS2 → Btrfs
       └── profil non chiffré : Btrfs direct
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

Le profil par défaut chiffre la totalité du système avec LUKS2.

Seule la partition EFI reste non chiffrée.

Le chiffrement protège :

- les données utilisateur
- les fichiers système
- les snapshots
- les fichiers temporaires

Pour une installation sans chiffrement ni passphrase, définir simultanément :

```bash
LUKS_ENABLED="false"
TPM2_ENABLED="false"
```

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

Snapper gère les snapshots, `snap-pac` les déclenche autour des transactions
pacman.

| Déclencheur | Mécanisme |
| --- | --- |
| avant et après chaque transaction pacman | `snap-pac` |
| horaire | `snapper-timeline.timer` |
| manuel | `snapper create` |

Les deux mécanismes sont nécessaires. Le timeline seul laisserait jusqu'à une
heure de modifications sans lien entre le dernier snapshot et la mise à jour
fautive : revenir en arrière annulerait alors bien plus que la mise à jour.

## Emplacement

`@snapshots` est monté sur `/.snapshots` **avant** l'installation de snapper.

La configuration est donc écrite directement plutôt que via
`snapper create-config`, qui veut créer `/.snapshots` lui-même et échoue si le
chemin existe déjà.

Ce montage séparé est ce qui empêche la racine de contenir ses propres
snapshots — sans quoi un retour arrière ne serait pas propre. La vérification
finale refuse l'installation si `/.snapshots` n'est pas un point de montage.

Le répertoire est en `750` : un snapshot contient tout ce que contenait la
racine.

## Rétention

Bornée dans les deux dimensions : `NUMBER_LIMIT="20"` et les limites de timeline
(6 horaires, 7 quotidiens, 4 hebdomadaires, 2 mensuels). Un Btrfs plein est
sensiblement plus difficile à récupérer qu'une mise à jour cassée.

`EMPTY_PRE_POST_CLEANUP` supprime les paires où rien n'a changé, sinon chaque
transaction sans effet laisserait un couple inutile.

`NUMBER_LIMIT_IMPORTANT` ne conserve rien tant que rien n'est marqué important.
C'est le rôle de `/etc/snap-pac.ini`, qui signale les mises à jour de noyau, de
`systemd`, de `cryptsetup`, de Limine et les `pacman -Syu` complets. snap-pac
snapshote la configuration `root` par défaut : ce fichier n'active pas la
fonctionnalité, il désigne ce qui mérite d'être gardé plus longtemps.

## Limites

Les snapshots servent à restaurer rapidement un état fonctionnel. Ils ne
remplacent pas une sauvegarde : ils vivent sur le disque qu'ils protègent.

Ils ne couvrent pas `/boot`, qui est en FAT32 hors Btrfs — noyaux et
`limine.conf` ne reviennent pas en arrière.

La procédure de retour arrière est décrite dans `docs/recovery.md`. `snapper
rollback` n'est pas utilisable avec cette disposition.

---

# Swap

Deux mécanismes, avec des rôles distincts et des priorités différentes.

| Mécanisme | Priorité | Rôle |
| --- | --- | --- |
| zram | 100 | pagination courante |
| swapfile | 10 | hibernation, et débordement en dernier recours |

Les priorités ne sont pas décoratives. À priorité égale, le noyau répartit la
pagination sur les deux, ce qui envoie des pages actives sur le disque sans
raison et rend le swapfile indisponible pour l'hibernation.

## zram

Compression `zstd`, taille égale à la moitié de la mémoire.

**zram exige un réglage du noyau.** La valeur par défaut `vm.swappiness=60` est
calibrée pour un swap sur disque, où écrire coûte cher et où le noyau doit
l'éviter. zram travaille à la vitesse de la mémoire : la même prudence le laisse
inutilisé pendant que le noyau libère du cache à la place.

C'est exactement le symptôme observé — zram présent mais quasiment jamais
utilisé.

Le fichier `/etc/sysctl.d/99-zram.conf` corrige cela :

```
vm.swappiness = 180
vm.page-cluster = 0
vm.watermark_boost_factor = 0
vm.watermark_scale_factor = 125
```

`page-cluster = 0` désactive la lecture anticipée : elle est rentable sur un
disque et ne coûte que de la décompression sur zram.

## Swapfile et hibernation

L'hibernation écrit le contenu de la mémoire sur un support persistant. zram
disparaît à la coupure du courant et ne peut donc pas servir de zone de reprise.

Conditions, vérifiées par `validate_config` :

- `SWAP_SIZE` supérieur à zéro ;
- `SWAP_SIZE` au moins égal à la mémoire installée — une image d'hibernation
  est le contenu de la RAM, et le noyau ne découvre le manque de place qu'en
  cours de mise en veille ;
- sous-volume `@swap` présent.

Le sous-volume `@swap` est indispensable : le copy-on-write corrompt un
swapfile. L'attribut est retiré à la création du sous-volume, tant qu'il est
encore vide — le poser après coup n'affecte pas les extents existants. Le
sous-volume est monté sans compression, un swapfile compressé étant inutilisable.

Le fichier est créé par `btrfs filesystem mkswapfile`, qui gère le
copy-on-write et la compression, contrairement à `dd` suivi de `mkswap`.

Un swapfile sans hibernation reste possible : simple débordement au-delà de
zram.

Voir `docs/boot.md` pour les paramètres `resume` et `resume_offset`.

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
- LUKS2 partout sauf EFI dans le profil chiffré
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
# SWAP_SIZE="0GiB" désactive le swapfile ; zram seul, pas d'hibernation.
# Une valeur non nulle exige le sous-volume @swap.
SWAP_SIZE="0GiB"
ZRAM_ENABLED="true"
HIBERNATION_ENABLED="false"
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

## Implémentation réelle

`tasks/10_storage.sh` applique le plan GPT uniquement depuis l'ISO Arch en UEFI,
avec `ENABLE_REAL_INSTALLATION=true`, après validation du disque et saisie de son
chemin complet. Le moteur utilise `wipefs`, `sgdisk`, `partprobe` et
`udevadm settle`, attend les deux périphériques et vérifie GPT, types et
alignement. Le rollback ne prétend jamais restaurer les données détruites.
