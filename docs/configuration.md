# Configuration système

Les valeurs de `config/system.conf` sont validées avant toute opération de
stockage. Le hostname, le fuseau horaire, les locales, la keymap, le nom
d'utilisateur, le shell et les groupes doivent respecter des formats sûrs. Le
fuseau doit également correspondre à un fichier présent sous
`/usr/share/zoneinfo` dans l'ISO.

La création utilisateur est rejouable : un compte absent est créé et reçoit un
mot de passe interactif ; un compte déjà présent voit uniquement son shell et
ses groupes remis en conformité. Le mot de passe existant n'est jamais remplacé
silencieusement. Le fragment sudoers est écrit avec le mode `0440` puis vérifié
par `visudo`.

Le home et les répertoires XDG `.config`, `.cache`, `.local`, `.local/share`,
`.local/bin` et `.config/systemd/user` sont explicitement attribués au compte
installé. La vérification finale exécute un test d'écriture sous l'identité de
cet utilisateur ; cela évite qu'un parent créé par root empêche Fish, Niri ou
DMS d'initialiser leur configuration.

Les services sont déclarés dans `services/enable.list` et activés dans une seule
phase. Leur état `enabled` est vérifié après configuration. Les modules comme
Snapper écrivent leurs fichiers propres mais ne dupliquent pas l'activation des
unités systemd.
