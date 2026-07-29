# Démarrage

L'installation utilise Limine en UEFI. L'ESP FAT32 est montée sur `/boot` et
contient l'exécutable EFI, les noyaux, initramfs et `limine.conf`. Deux entrées
sont générées : `linux-lts` par défaut et `linux` en secours. L'initramfs utilise
les hooks systemd et `sd-encrypt` pour ouvrir LUKS2 avant le montage Btrfs.

Dans le profil non chiffré, `sd-encrypt` est retiré de l'initramfs et Limine
identifie directement la partition Btrfs par son `PARTUUID`.

Lorsque TPM2 est activé, la ligne noyau ajoute
`rd.luks.options=<UUID>=tpm2-device=auto` afin que systemd utilise le jeton
LUKS2 enrôlé, tout en conservant la passphrase comme solution de récupération.
Le hook `microcode` de mkinitcpio produit une image combinée ; aucune image
microcode séparée n'est nécessaire dans `limine.conf`.

Les exécutables EFI principal et de secours sont comparés au binaire fourni par
le paquet Limine. Un hook pacman local les redéploie après chaque installation
ou mise à jour de `limine`. La vérification exige également les noyaux et
initramfs `linux-lts` et `linux`, ainsi que leurs deux entrées de menu.

Secure Boot est une préparation documentée, pas une activation automatique :
l'enrôlement de clés firmware reste une opération distincte et récupérable.

## Ordre des hooks mkinitcpio

L'ordre est produit par `build_mkinitcpio_hooks` (`lib/memory.sh`) plutôt qu'écrit
à la main, parce que trois contraintes doivent tenir simultanément.

```
base systemd autodetect microcode modconf kms keyboard sd-vconsole block
[sd-encrypt] filesystems [resume] fsck
```

| Contrainte | Conséquence si violée |
| --- | --- |
| `systemd` avant `sd-encrypt` | `sd-encrypt` ne dispose pas de son environnement |
| `sd-encrypt` avant `filesystems` | la racine est cherchée avant l'ouverture du conteneur |
| `resume` après `filesystems` | l'image d'hibernation est un fichier, il faut son système de fichiers |

`sd-encrypt` n'est présent que si `LUKS_ENABLED=true`, `resume` que si
`HIBERNATION_ENABLED=true`.

## Reprise après hibernation

Deux paramètres noyau, tous deux nécessaires :

```
resume=/dev/mapper/cryptroot  resume_offset=<offset>
```

`resume` seul ne suffit pas : le noyau sait alors sur quel périphérique chercher
l'image, mais pas à quelle position. Il démarre à froid **sans signaler quoi que
ce soit**, ce qui est le symptôme le plus déroutant à diagnostiquer.

Avec LUKS, la reprise passe par `/dev/mapper/<LUKS_NAME>` : le conteneur est déjà
ouvert par `sd-encrypt` quand `resume` s'exécute.

Le décalage est lu par `btrfs inspect-internal map-swapfile --resume-offset`. Il
change si le swapfile est recréé, et doit alors être recalculé et reporté dans
`limine.conf` — voir `docs/update.md`.

## Vérification du mode UEFI

L'installateur détecte `/sys/firmware/efi` et lit
`/sys/firmware/efi/fw_platform_size` lorsqu'il est disponible. Une valeur `64`
confirme l'UEFI x64 attendu. Le sous-dossier `efivars` n'est pas exigé pour la
détection, car `efivarfs` peut ne pas être monté. Si le chemin EFI est absent,
redémarrer et sélectionner explicitement l'entrée USB préfixée par `UEFI:` en
désactivant Legacy/CSM.
