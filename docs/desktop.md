# Desktop

Le profil installe Niri, Dank Material Shell (`dms-shell-niri`), Fish, Ghostty,
les portails XDG, PipeWire et les outils Wayland nécessaires. Hyprland n'est pas
une cible du projet. La configuration personnelle et les secrets restent dans
un dépôt de dotfiles séparé, appliqué avec GNU Stow après le premier démarrage.

## Démarrage de la session

`greetd` démarre automatiquement `niri-session` pour `USERNAME` lorsque
`DESKTOP_AUTOLOGIN=true`. L'installateur pose une configuration Niri minimale
dans `~/.config/niri/config.kdl` et la valide avec `niri validate` avant de
terminer l'installation. Cette configuration fournit les raccourcis essentiels
de DMS et Ghostty sans anticiper le futur dépôt de dotfiles.

Le drop-in `~/.config/systemd/user/niri.service.d/dms.conf` ajoute
`Wants=dms.service` à l'unité Niri, comme le profil Niri + DMS d'Archinstall.
DMS démarre ainsi avec la session Wayland et ses erreurs sont consultables avec
`journalctl --user -u dms.service`.

Une seconde unité utilisateur attend jusqu'à 60 secondes que l'IPC de DMS
réponde, puis demande le verrouillage avec `dms ipc call lock lock`. Ce délai
laisse à une VM peu dotée le temps de compiler les caches QML au premier
démarrage.

L'auto-login n'est accepté par la validation que si `DMS_LOCK_ON_START=true`.
Si DMS ne peut pas établir son écran de verrouillage, le lanceur ferme la session
Niri : le comportement échoue ainsi en mode sûr au lieu de laisser un bureau
ouvert. Après une déconnexion, `greetd` lance le greeter graphique DMS avec
`dms-greeter --command niri -p /usr/share/quickshell/dms`.

Le lanceur officiel du greeter est exécuté directement depuis le paquet DMS ;
l'installateur ne conserve donc pas de copie obsolète dans `/usr/local/bin`, ne
télécharge aucun script et n'utilise pas l'AUR. Un fichier tmpfiles crée
`/var/cache/dms-greeter` et `/var/lib/greeter` avec les droits attendus. La
synchronisation optionnelle du thème personnel peut être effectuée après le
premier démarrage avec `dms greeter sync`. Le verrouillage DMS protège la
session graphique, mais ne remplace ni le chiffrement du disque ni la
protection physique de la machine.

## Machines virtuelles

Niri a besoin d'un nœud de rendu DRM. Dans GNOME Boxes, l'accélération 3D doit
être activée avant le démarrage de la VM ; augmenter uniquement la RAM ne crée
pas ce périphérique. Le validateur post-installation signale explicitement
l'absence de `/dev/dri/renderD*`. Les erreurs de portail GTK ou l'avertissement
`import-environment` ne prouvent pas à eux seuls une panne du compositeur.
