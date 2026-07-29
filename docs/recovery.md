# Récupération

Conserver la phrase LUKS2 hors de la machine et vérifier les sauvegardes avant
l'installation. En cas de remplacement de carte mère, ouvrir le volume avec la
phrase de récupération puis réenrôler TPM2. Les snapshots Snapper facilitent un
retour système mais ne remplacent jamais une sauvegarde.

L'enrôlement TPM2 est lié au PCR 7. Après un changement de firmware, de carte
mère ou d'état Secure Boot, démarrer avec la passphrase puis supprimer et
réenrôler uniquement le jeton TPM2. L'installateur ne supprime jamais ce jeton
automatiquement pendant un rollback.

Le partitionnement, `luksFormat` et `mkfs` sont irréversibles : aucun rollback
automatique ne prétend restaurer les anciennes données.

---

## Revenir en arrière après une mise à jour

`snap-pac` prend un snapshot avant et après chaque transaction pacman. C'est ce
qui rend cette procédure possible : le snapshot date de juste avant la
transaction fautive, et non de la dernière heure ronde.

```bash
snapper list
```

Les paires `pre`/`post` portent la commande en description, ce qui permet
d'identifier la mise à jour concernée.

### Restaurer des fichiers, sans redémarrer

Le cas le plus fréquent et le moins risqué. Les snapshots sont lisibles
directement :

```bash
sudo snapper -c root status 42..0          # ce qui a changé depuis le snapshot 42
sudo snapper -c root diff 42..0 /etc/fstab
sudo snapper -c root undochange 42..0 /usr/bin/monprogramme
```

`undochange` sur un chemin précis est préférable à une restauration complète :
la portée reste maîtrisée.

### Restaurer le système entier

`snapper rollback` **n'est pas utilisable ici** : il suppose une disposition
openSUSE où le sous-volume racine est remplacé par le bootloader. Avec Limine et
`rootflags=subvol=@`, la racine est désignée par son nom, il faut donc échanger le
sous-volume à la main.

Depuis l'ISO live, jamais depuis le système à remplacer :

```bash
cryptsetup open /dev/nvme0n1p2 cryptroot
mount /dev/mapper/cryptroot /mnt            # niveau supérieur, pas @

mv /mnt/@ /mnt/@casse
btrfs subvolume snapshot /mnt/@snapshots/42/snapshot /mnt/@

umount /mnt
```

Points d'attention :

- monter le **niveau supérieur** (`subvolid=5`), pas `subvol=@` : on ne peut pas
  déplacer le sous-volume qu'on utilise ;
- `@casse` est conservé plutôt que supprimé, le temps de vérifier que le
  remplacement démarre ;
- `@home` n'est pas touché : les données utilisateur ne sont pas concernées par un
  retour arrière système ;
- après hibernation, l'image de reprise ne correspond plus au système restauré.
  Supprimer `/swap/swapfile` ou démarrer à froid avant de reprendre.

Une fois le démarrage confirmé :

```bash
btrfs subvolume delete /mnt/@casse
```

### Ce que le rollback ne fait pas

- il ne restaure pas `/boot` : l'ESP est en FAT32, hors Btrfs, donc noyaux et
  `limine.conf` ne sont pas revenus en arrière. Si la mise à jour fautive
  touchait le noyau, régénérer l'initramfs après restauration ;
- il ne restaure pas la base de données pacman au-delà du snapshot de `@` — elle
  y est incluse, mais les paquets téléchargés dans `@cache` ne le sont pas ;
- il ne remplace pas une sauvegarde. Les snapshots vivent sur le disque qu'ils
  protègent.

`nano` fait partie des paquets de base installés afin de pouvoir corriger la
configuration, les unités systemd et les fichiers de démarrage directement
depuis un TTY ou un environnement de récupération minimal.

Si une installation antérieure a créé les parents XDG en root et que Fish
affiche `Permission denied`, réparer uniquement les répertoires concernés sans
modifier récursivement tous les fichiers du home :

```bash
sudo chown reaper:reaper /home/reaper
sudo install -d -m0700 -o reaper -g reaper \
    /home/reaper/.cache \
    /home/reaper/.config \
    /home/reaper/.local \
    /home/reaper/.local/share
sudo install -d -m0755 -o reaper -g reaper \
    /home/reaper/.config/systemd \
    /home/reaper/.config/systemd/user \
    /home/reaper/.local/bin
```

Remplacer `reaper` par le compte configuré. Ne pas utiliser `chown -R` sans
examiner préalablement le contenu du home.
