# Paquets

Les fichiers `packages/*.list` sont lus par `lib/pacstraps.sh`, nettoyés de leurs
commentaires, fusionnés et triés avant un unique appel à `pacstrap`. Les groupes
sont base, firmware, Framework, desktop, développement, fontes, multimédia et
optionnels. Le profil desktop officiel contient `niri` et `dms-shell-niri`.

Toute nouvelle dépendance doit être documentée et disponible depuis un dépôt de
confiance configuré dans l'ISO. Les logiciels AUR/propriétaires sont installés
après le premier démarrage par un workflow séparé et auditable.
