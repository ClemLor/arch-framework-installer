# Démarrage

## Chaîne complète

```
Micrologiciel UEFI
        │
        ▼
/boot/EFI/BOOT/BOOTX64.EFI          (Limine)
        │
        ▼
/boot/limine.conf                   (entrées de démarrage)
        │
        ▼
vmlinuz-linux-lts + initramfs
        │
        ▼
sd-encrypt ouvre le conteneur LUKS  (TPM2, puis phrase de passe)
        │
        ▼
montage de @ depuis /dev/mapper/cryptroot
        │
        ▼
systemd
```

---

## Pourquoi Limine

Le choix ne repose pas sur les performances, elles sont indifférentes ici.

- La configuration est un fichier texte lisible, pas un script généré. Un
  problème de démarrage se diagnostique en lisant `limine.conf`.
- Il gère les entrées de snapshot Btrfs, ce qui est la condition du retour
  arrière après une mise à jour ratée.
- Il n'exige pas de réécrire une configuration à chaque changement de noyau,
  contrairement à GRUB.

`systemd-boot` aurait aussi convenu. Limine a été retenu pour son intégration
avec les snapshots.

### Chemin d'installation

Le binaire est placé en `/boot/EFI/BOOT/BOOTX64.EFI`, qui est le chemin de repli
pour support amovible. Aucune entrée n'est créée dans la NVRAM.

C'est volontaire : ce chemin fonctionne sans dépendre de variables EFI, donc il
survit à une réinitialisation du micrologiciel. En contrepartie, la machine n'a
pas d'entrée nommée dans son menu de démarrage.

---

## Ordre des crochets mkinitcpio

C'est la partie la plus facile à casser silencieusement.

```
base systemd autodetect microcode modconf kms keyboard sd-vconsole block
sd-encrypt filesystems resume fsck
```

Trois contraintes :

| Contrainte | Conséquence si violée |
| --- | --- |
| `systemd` avant `sd-encrypt` | `sd-encrypt` ne dispose pas de son environnement |
| `sd-encrypt` avant `filesystems` | La racine est cherchée avant que le conteneur soit ouvert |
| `resume` après `filesystems` | L'image d'hibernation est un fichier, il faut son système de fichiers |

Les crochets `systemd` sont utilisés plutôt que `busybox` parce que le
déverrouillage TPM2 en dépend.

`keyboard` et `sd-vconsole` sont présents pour que la disposition du clavier soit
correcte à la saisie de la phrase de passe. Sans eux, une phrase de passe tapée
sur un clavier suisse est saisie en QWERTY.

---

## Ligne de commande du noyau

```
rd.luks.uuid=<UUID>  root=/dev/mapper/cryptroot  rootflags=subvol=@  rw
resume=/dev/mapper/cryptroot  resume_offset=<offset>
```

| Paramètre | Rôle |
| --- | --- |
| `rd.luks.uuid` | Lu par `sd-encrypt` pour trouver le conteneur |
| `rootflags=subvol=@` | Sans lui, le noyau monte le niveau supérieur Btrfs, qui contient les sous-volumes et non une racine |
| `resume` | Périphérique contenant l'image d'hibernation |
| `resume_offset` | Position de l'image dans ce périphérique |

`resume` seul ne suffit pas : le noyau sait alors sur quel périphérique chercher
mais pas où, et démarre à froid sans le signaler.

---

## crypttab.initramfs, pas crypttab

L'entrée du conteneur racine est écrite dans `/etc/crypttab.initramfs`.

`/etc/crypttab` serait lu trop tard : il se trouve sur le système de fichiers que
le conteneur doit précisément rendre accessible.

```
cryptroot  UUID=<UUID>  none  luks,discard,tpm2-device=auto
```

`tpm2-device=auto` est ce qui déclenche la tentative de déverrouillage
automatique. En cas d'échec, la phrase de passe est demandée.

---

## Entrées générées

Une entrée par noyau configuré, plus une entrée de secours utilisant l'initramfs
`fallback` du premier noyau.

L'image de secours n'inclut pas les modules détectés automatiquement, donc elle
démarre encore lorsqu'un changement de matériel rend l'initramfs optimisé
inadapté.

`default_entry: 1` sélectionne la première entrée, `timeout: 3` laisse trois
secondes pour en choisir une autre.

---

## Maintenance des entrées

`limine-mkinitcpio-hook` régénère automatiquement les entrées à l'installation ou
au retrait d'un noyau. Ce paquet **n'existe que dans l'AUR** : il ne peut pas être
installé pendant `pacstrap`, faute d'assistant AUR et d'environnement de
compilation dans l'ISO.

L'installateur le signale et le laisse pour après le premier démarrage. Tant
qu'il n'est pas installé, `limine.conf` doit être mis à jour à la main après un
changement de noyau.

Le système démarre sans lui : c'est la condition à respecter.

---

## Diagnostic

| Symptôme | Cause probable |
| --- | --- |
| Aucun menu | Binaire absent de `/boot/EFI/BOOT/`, ou ESP non montée |
| Menu puis arrêt immédiat | Chemin de noyau erroné dans `limine.conf` |
| Phrase de passe non demandée, puis échec | `sd-encrypt` absent ou après `filesystems` |
| Phrase de passe refusée alors qu'elle est correcte | Disposition de clavier — vérifier `sd-vconsole` |
| Racine introuvable après déverrouillage | `rootflags=subvol=@` manquant |
| Démarrage à froid après hibernation | `resume_offset` manquant ou périmé |

Le décalage de reprise change si le fichier d'échange est recréé. Il doit alors
être recalculé :

```bash
btrfs inspect-internal map-swapfile --resume-offset /swap/swapfile
```
