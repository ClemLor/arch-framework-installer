# Récupération

## Principe

Le système est jetable. La question à se poser en premier n'est pas « comment
réparer » mais « est-ce plus rapide de réinstaller ».

Avec une configuration enregistrée et des dotfiles séparés, une réinstallation
complète prend moins d'une heure. Passer trois heures à diagnostiquer un problème
de démarrage est presque toujours le mauvais choix.

Ce document sert donc surtout à récupérer **les données** et à traiter les cas où
la réinstallation ne suffit pas — c'est-à-dire les problèmes de clé.

---

## Le disque ne s'ouvre plus

### TPM2 ne déverrouille plus

Symptôme : la phrase de passe est demandée alors qu'elle ne l'était plus.

Cause normale : mise à jour du micrologiciel, changement de l'état du démarrage
sécurisé, réinitialisation du BIOS. Le scellement porte sur les PCR 0 et 7 ; leur
valeur a changé.

Ce n'est pas une panne. Saisir la phrase de passe, démarrer, puis réenrôler :

```bash
sudo systemd-cryptenroll --wipe-slot=tpm2 /dev/nvme0n1p2
sudo systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=0+7 /dev/nvme0n1p2
```

### Phrase de passe oubliée

Utiliser la clé de secours notée à l'installation, à l'invite de démarrage.

Puis, une fois démarré, remplacer la phrase de passe :

```bash
sudo cryptsetup luksChangeKey /dev/nvme0n1p2
```

### Phrase de passe et clé de secours perdues

Les données sont irrécupérables. C'est la propriété attendue du chiffrement.

Réinstaller depuis la configuration enregistrée.

### La phrase de passe est refusée alors qu'elle est correcte

Vérifier la disposition du clavier. À l'invite de déverrouillage, la disposition
dépend de `sd-vconsole` dans l'initramfs. Essayer la même phrase telle qu'elle
serait tapée en QWERTY.

---

## Le système ne démarre pas

### Depuis l'ISO live

```bash
cryptsetup open /dev/nvme0n1p2 cryptroot
mount -o subvol=@,compress=zstd:3 /dev/mapper/cryptroot /mnt
mount -o subvol=@home,compress=zstd:3 /dev/mapper/cryptroot /mnt/home
mount /dev/nvme0n1p1 /mnt/boot
arch-chroot /mnt
```

De là :

| Problème | Action |
| --- | --- |
| Initramfs cassé | `mkinitcpio --allpresets` |
| Entrées de démarrage incorrectes | éditer `/boot/limine.conf` |
| Binaire Limine absent | `cp /usr/share/limine/BOOTX64.EFI /boot/EFI/BOOT/` |
| Paquet cassé | `pacman -S <paquet>` |

Voir `docs/boot.md` pour la table de diagnostic complète.

### Retour arrière par snapshot

Le sous-volume `@snapshots` existe et `snapper` est installé, mais **aucune
politique n'est configurée par l'installateur**. Cette partie reste à faire.

En attendant, un snapshot pris manuellement se restaure en montant le niveau
supérieur Btrfs et en remplaçant `@` :

```bash
mount /dev/mapper/cryptroot /mnt          # niveau supérieur
mv /mnt/@ /mnt/@cassé
btrfs subvolume snapshot /mnt/@snapshots/<n>/snapshot /mnt/@
```

---

## Récupérer les données seulement

C'est le cas le plus fréquent et le plus simple. Depuis l'ISO live :

```bash
cryptsetup open /dev/nvme0n1p2 cryptroot
mkdir /mnt/home
mount -o subvol=@home /dev/mapper/cryptroot /mnt/home
rsync -a /mnt/home/ /run/media/<cible>/sauvegarde/
```

Puis réinstaller.

---

## Réinstaller à l'identique

```bash
python -m arch_framework --install --config saved.json --creds creds.json
```

C'est le chemin pour lequel le projet existe. Il suppose que la configuration
enregistrée est conservée **ailleurs que sur la machine** — sur une clé USB, dans
un dépôt privé, ou imprimée.

Une configuration enregistrée uniquement sur le disque chiffré qu'elle décrit ne
sert à rien le jour où ce disque ne s'ouvre plus.

---

## Reprendre une installation interrompue

Les étapes terminées sont enregistrées dans
`/run/arch-framework-installer.state.json`. Relancer la même commande reprend là
où l'installation s'est arrêtée.

Deux limites :

- l'état est sur `tmpfs` : un redémarrage de l'ISO le perd, et l'installation
  repart du partitionnement ;
- reprendre avec une configuration différente est refusé. Supprimer le fichier
  d'état pour recommencer.

---

## Ce qu'il faut conserver hors de la machine

Par ordre d'importance :

1. la **clé de secours** LUKS, sur papier ;
2. la **configuration enregistrée** (`framework-install.json`) ;
3. une sauvegarde de `/home`.

Les deux premiers tiennent sur une feuille et une clé USB. Sans le premier, une
mise à jour de micrologiciel malheureuse suffit à perdre la machine ; sans le
second, la reproductibilité annoncée par le projet n'existe pas.

Le projet ne fournit **aucune sauvegarde automatique**.
