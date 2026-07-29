# Mises à jour

## État

L'installateur ne met rien à jour. Ce document décrit la maintenance manuelle du
système installé, et ce que le projet devra automatiser.

---

## Système

```bash
sudo pacman -Syu
```

Arch est une distribution à publication continue : des mises à jour rares et
massives sont plus risquées que des mises à jour fréquentes et petites. Lire
`archlinux.org` avant une mise à jour qui touche le noyau ou `systemd`.

### Après une mise à jour de noyau

`mkinitcpio` régénère l'initramfs automatiquement. Les entrées de démarrage, en
revanche, ne sont régénérées que si `limine-mkinitcpio-hook` est installé — ce
paquet est dans l'AUR et n'est pas installé par l'installateur.

Sans lui, vérifier que `/boot/limine.conf` désigne bien les images présentes :

```bash
ls /boot/vmlinuz-* /boot/initramfs-*
grep -E 'kernel_path|module_path' /boot/limine.conf
```

### Après une mise à jour de micrologiciel

Le scellement TPM2 porte sur les PCR 0 et 7. Une mise à jour du BIOS change PCR
0, donc le déverrouillage automatique cesse de fonctionner.

C'est attendu. Saisir la phrase de passe, puis réenrôler — voir
`docs/recovery.md`.

```bash
sudo fwupdmgr refresh
sudo fwupdmgr get-updates
sudo fwupdmgr update
```

### Si le fichier d'échange est recréé

Le décalage de reprise devient faux et l'hibernation redémarre à froid sans le
signaler.

```bash
sudo btrfs inspect-internal map-swapfile --resume-offset /swap/swapfile
```

Reporter la valeur dans `resume_offset=` de `/boot/limine.conf`.

---

## AUR

À installer après le premier démarrage :

```bash
limine-mkinitcpio-hook
```

Le projet n'impose pas d'assistant AUR.

---

## Mettre à jour la configuration d'installation

La configuration enregistrée décrit une machine. Si un choix change — un noyau,
un groupe de paquets, la taille de l'échange — l'enregistrement doit suivre,
sinon la prochaine réinstallation reconstruit l'ancienne machine.

```bash
python -m arch_framework --tui --config framework-install.json
```

Le menu s'ouvre sur la configuration chargée, la modification est appliquée, et
`s` réenregistre.

---

## Mettre à jour le projet lui-même

Le dépôt n'est utilisé que depuis l'ISO live, donc il n'y a rien à mettre à jour
sur la machine installée. Il suffit de le cloner à jour au moment d'une
réinstallation.

Après une modification des étapes d'installation, la séquence de commandes de
référence change :

```bash
pytest tests/test_installer.py
```

Lire le `diff` sur `tests/golden/install-commands.txt` et ne le mettre à jour que
si l'écart est voulu.

---

## À automatiser

Par ordre d'utilité :

1. **Politique snapper.** `@snapshots` existe et `snapper` est installé, mais
   aucune configuration n'est appliquée. C'est la pièce manquante la plus
   importante : sans elle, il n'y a pas de retour arrière.
2. **Réenrôlement TPM2 après mise à jour de micrologiciel.** Détectable et
   scriptable.
3. **Vérification de santé** — espace disque, échecs de services, cohérence entre
   `limine.conf` et les images présentes.
4. **Sauvegarde.** Le projet n'en fournit aucune.
