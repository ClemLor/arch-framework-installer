# Démarrage

L'installation utilise Limine en UEFI. L'ESP FAT32 est montée sur `/boot` et
contient l'exécutable EFI, les noyaux, initramfs et `limine.conf`. Deux entrées
sont générées : `linux-lts` par défaut et `linux` en secours. L'initramfs utilise
les hooks systemd et `sd-encrypt` pour ouvrir LUKS2 avant le montage Btrfs.

Secure Boot est une préparation documentée, pas une activation automatique :
l'enrôlement de clés firmware reste une opération distincte et récupérable.

## Vérification du mode UEFI

L'installateur détecte `/sys/firmware/efi` et lit
`/sys/firmware/efi/fw_platform_size` lorsqu'il est disponible. Une valeur `64`
confirme l'UEFI x64 attendu. Le sous-dossier `efivars` n'est pas exigé pour la
détection, car `efivarfs` peut ne pas être monté. Si le chemin EFI est absent,
redémarrer et sélectionner explicitement l'entrée USB préfixée par `UEFI:` en
désactivant Legacy/CSM.
