# Paquets

Les fichiers `packages/*.list` sont lus par `lib/pacstraps.sh`, nettoyés de leurs
commentaires, fusionnés et triés avant un unique appel à `pacstrap`. Les groupes
sont base, firmware, Framework, desktop, développement, fontes, multimédia et
optionnels. Le profil desktop contient `niri`, `dms-shell-niri`, ainsi que
`matugen`, `cava`, `kimageformats` et `cups-pk-helper`, utilisés par les modules
de thème, visualisation audio, images et impression de DMS. Le profil Framework
ajoute `intel-media-driver` et `vulkan-intel` pour l'accélération graphique des
GPU Intel modernes. `mesa` reste fourni par les dépendances officielles de
Niri.

Avant toute écriture disque, l'installateur rafraîchit les bases pacman et
vérifie avec `pacman --sync --info` que chaque paquet destiné à `pacstrap` est
disponible. Une faute de nom arrête donc l'installation avant le partitionnement.

`packages/aur.list` est une liste documentaire distincte. Elle contient
notamment LibreWolf et Microsoft Edge, qui ne sont jamais transmis à `pacstrap`.
Leurs PKGBUILDs doivent être vérifiés puis construits comme utilisateur non-root
après le premier démarrage.

Le paquet Arch fournissant le générateur systemd pour zram s'appelle
`zram-generator` (le projet amont est nommé systemd/zram-generator).
`jq` est installé pour vérifier les métadonnées JSON LUKS2 sans analyser la
sortie tabulaire de `systemd-cryptenroll`.

Toute nouvelle dépendance doit être documentée et disponible depuis un dépôt de
confiance configuré dans l'ISO. Les logiciels AUR/propriétaires sont installés
après le premier démarrage par un workflow séparé et auditable.
