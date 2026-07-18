# Démarrage

L'installation utilise Limine en UEFI. L'ESP FAT32 est montée sur `/boot` et
contient l'exécutable EFI, les noyaux, initramfs et `limine.conf`. Deux entrées
sont générées : `linux-lts` par défaut et `linux` en secours. L'initramfs utilise
les hooks systemd et `sd-encrypt` pour ouvrir LUKS2 avant le montage Btrfs.

Secure Boot est une préparation documentée, pas une activation automatique :
l'enrôlement de clés firmware reste une opération distincte et récupérable.
