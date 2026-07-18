# Paquets

Les fichiers `packages/*.list` sont lus par `lib/pacstraps.sh`, nettoyés de leurs
commentaires, fusionnés et triés avant un unique appel à `pacstrap`. Les groupes
sont base, firmware, Framework, desktop, développement, fontes, multimédia et
optionnels. Le profil desktop officiel contient `niri` et `dms-shell-niri`.

Avant toute écriture disque, l'installateur rafraîchit les bases pacman et
vérifie avec `pacman --sync --info` que chaque paquet destiné à `pacstrap` est
disponible. Une faute de nom arrête donc l'installation avant le partitionnement.

`packages/aur.list` est une liste documentaire distincte. Elle contient
notamment LibreWolf et Microsoft Edge, qui ne sont jamais transmis à `pacstrap`.
Leurs PKGBUILDs doivent être vérifiés puis construits comme utilisateur non-root
après le premier démarrage.

Le paquet Arch fournissant le générateur systemd pour zram s'appelle
`zram-generator` (le projet amont est nommé systemd/zram-generator).

Toute nouvelle dépendance doit être documentée et disponible depuis un dépôt de
confiance configuré dans l'ISO. Les logiciels AUR/propriétaires sont installés
après le premier démarrage par un workflow séparé et auditable.
