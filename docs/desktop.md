# Desktop

Le profil installe Niri, Dank Material Shell (`dms-shell-niri`), Fish, Ghostty,
les portails XDG, PipeWire et les outils Wayland nécessaires. Hyprland n'est pas
une cible du projet. La configuration personnelle et les secrets restent dans
un dépôt de dotfiles séparé, appliqué avec GNU Stow après le premier démarrage.

## Démarrage de la session

`greetd` démarre automatiquement `niri-session` pour `USERNAME` lorsque
`DESKTOP_AUTOLOGIN=true`. DMS est ensuite lancé par l'autostart XDG, donc après
la création du socket Wayland. Le lanceur attend que l'IPC de DMS réponde, puis
demande immédiatement le verrouillage avec `dms ipc call lock lock`.

L'auto-login n'est accepté par la validation que si `DMS_LOCK_ON_START=true`.
Si DMS ne peut pas établir son écran de verrouillage, le lanceur ferme la session
Niri : le comportement échoue ainsi en mode sûr au lieu de laisser un bureau
ouvert. Après une déconnexion, `greetd` lance le greeter graphique DMS avec
`dms-greeter --command niri -p /usr/share/quickshell/dms`.

Le lanceur officiel du greeter est copié depuis le paquet DMS déjà installé ;
l'installateur ne télécharge aucun script et n'utilise pas l'AUR. Le cache
`/var/cache/dms-greeter` appartient à l'utilisateur système `greeter`. La
synchronisation optionnelle du thème personnel peut être effectuée après le
premier démarrage avec `dms greeter sync`. Le verrouillage DMS protège la
session graphique, mais ne remplace ni le chiffrement du disque ni la
protection physique de la machine.
