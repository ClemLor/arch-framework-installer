# Paquets

## AUR

Aucun paquet AUR n'est installé pendant l'installation.

Trois raisons, pas une préférence :

- l'ISO live n'a ni environnement de compilation ni utilisateur non privilégié ;
- `makepkg` refuse de s'exécuter en root, et le contourner laisserait des
  fichiers appartenant à root dans l'arbre de compilation ;
- un PKGBUILD cassé — tarball déplacé, somme de contrôle changée — est courant.
  Pendant l'installation, cela ferait échouer une tâche et déclencherait le
  rollback d'un système par ailleurs complet et amorçable.

L'installateur écrit donc un script, exécuté une fois après le premier
démarrage :

```bash
afi-aur-setup
```

Il construit `paru` depuis son PKGBUILD, puis installe la liste enregistrée dans
`/usr/local/share/arch-framework-installer/aur.list`. La liste est copiée dans le
système cible parce que le dépôt n'est plus disponible après le redémarrage.

Le script :

- refuse de s'exécuter en root ;
- demande l'accès `sudo` une fois au départ, plutôt qu'au milieu d'une longue
  compilation où une invite expirée l'abandonnerait ;
- installe les paquets **un par un**. Un seul `--needed` groupé abandonne tout
  l'ensemble dès qu'un PKGBUILD est cassé, ce qui laisserait la majorité de la
  liste non installée ;
- est réexécutable : il ignore ce qui est déjà installé. C'est nécessaire, la
  première compilation cassée arrivera.

Les échecs sont listés à la fin et le script sort en erreur, sans empêcher les
autres paquets de s'installer.

### Contenu

| Paquet | Note |
| --- | --- |
| `librewolf-bin` | Firefox sans télémétrie |
| `microsoft-edge-stable-bin` | |
| `visual-studio-code-bin` | build Microsoft, **pas** `code` |
| `cursor-bin` | |

`visual-studio-code-bin` et `code` (dépôt extra) ne sont pas interchangeables :
seul le premier accède au Marketplace Microsoft, donc à Copilot, Pylance et aux
extensions Remote. Le second utilise Open VSX.

`paru` ne figure pas dans la liste : c'est lui qui l'installe.

### Prérequis

`git`, `base-devel` et `sudo` sont dans `base.list` précisément pour que ce
script puisse fonctionner. La vérification finale refuse l'installation s'ils
manquent — le découvrir après un redémarrage serait pire.

---

Les fichiers `packages/*.list` sont lus par `lib/pacstraps.sh`, nettoyés de leurs
commentaires, fusionnés et triés avant un unique appel à `pacstrap`. Les groupes
sont base, firmware, Framework, desktop, développement, fontes, multimédia et
optionnels. Le profil desktop contient `niri`, `dms-shell-niri`, ainsi que
`matugen`, `cava`, `kimageformats` et `cups-pk-helper`, utilisés par les modules
de thème, visualisation audio, images et impression de DMS. Le profil Framework
ajoute `intel-media-driver` et `vulkan-intel` pour l'accélération graphique des
GPU Intel modernes. `mesa` reste fourni par les dépendances officielles de
Niri.

`qt5ct` et `qt6ct` permettent aux palettes Matugen générées par DMS d'atteindre
les applications Qt. `github-cli` facilite la restauration des dépôts privés de
dotfiles et de fonds d'écran sans manipuler de jeton dans un script.
`perl-image-exiftool` contrôle les métadonnées des images avant leur ajout au
dépôt de fonds d'écran.

Avant toute écriture disque, l'installateur rafraîchit les bases pacman et
vérifie avec `pacman --sync --info` que chaque paquet destiné à `pacstrap` est
disponible. Une faute de nom arrête donc l'installation avant le partitionnement.

`packages/aur.list` n'est plus une simple liste documentaire : elle est copiée
dans le système cible et consommée par `afi-aur-setup` après le premier
démarrage. Elle n'est jamais transmise à `pacstrap`. Voir la section AUR en tête
de ce document.

Le paquet Arch fournissant le générateur systemd pour zram s'appelle
`zram-generator` (le projet amont est nommé systemd/zram-generator).
`jq` est installé pour vérifier les métadonnées JSON LUKS2 sans analyser la
sortie tabulaire de `systemd-cryptenroll`.

Toute nouvelle dépendance doit être documentée et disponible depuis un dépôt de
confiance configuré dans l'ISO. Les logiciels AUR/propriétaires sont installés
après le premier démarrage par un workflow séparé et auditable.
