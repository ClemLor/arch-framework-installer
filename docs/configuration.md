# Configuration

## Deux façons de configurer

| Méthode | Fichier | Usage |
| --- | --- | --- |
| Édition directe | `config/system.conf` | valeurs par défaut, versionnées |
| Menu guidé | `config/generated.conf` | réponses propres à la machine |

`lib/config.sh` charge `config/system.conf`, puis `config/generated.conf` s'il
existe. Le second écrase le premier. Supprimer `generated.conf` ramène
l'installateur à ses valeurs par défaut.

`generated.conf` n'est pas versionné : il décrit une machine, pas le projet.

## Menu guidé

```bash
python3 -m configurator                 # interface plein écran, puis Save ou Install
python3 -m configurator --text          # invites simples, scriptables
python3 -m configurator --show          # état courant et problèmes, sans rien modifier
python3 -m configurator --dry-run       # Install suit la simulation à l'écran
```

L'interface plein écran (`configurator/tui/`) est choisie dès que le terminal s'y
prête : `curses` disponible, `TERM` utilisable, entrée et sortie sur un terminal.
Sinon — ou avec `--text`, ou `AFI_NO_TUI=1` — ce sont les invites simples, ligne
par ligne, qui restent la voie scriptable et testable.

| Touche | Effet |
| --- | --- |
| `↑` `↓` (ou `k` `j`) | déplacer la sélection |
| `Entrée` | modifier le réglage sélectionné |
| `Échap` | abandonner la question courante (équivaut à `:q` en mode texte) |
| `s` / `i` | enregistrer / installer |
| `q` | quitter sans rien écrire |

Les deux interfaces posent les **mêmes** questions : les éditeurs de
`configurator/menu.py` sont partagés, et seul le dos — `configurator/prompts.py` —
change. Une règle ajoutée dans `constraints.py` se voit donc dans les deux, sans
second endroit à mettre à jour.

`AFI_TUI_ASCII=1` force le jeu de caractères ASCII, pour une console dont la
police ne rend pas `… ✔ ✘`.

Le configurateur **n'installe rien**. Il écrit `config/generated.conf` puis, si
vous choisissez Install, passe la main à `install.sh` par `exec`. Toute opération
destructive reste dans le code Bash, qui est la seule implémentation, et
`validate_config` reste l'autorité : il s'exécute sur l'ISO live avec le matériel
réel devant lui.

Il n'utilise que la bibliothèque standard : aucune dépendance à installer sur
l'ISO.

### Suivi d'une simulation à l'écran

Avec `--dry-run`, Install garde l'écran et affiche les 15 tâches de `tasks/` en
train de s'exécuter : phase courante, durée, échec et rollback, plus la sortie
brute de l'installateur en bas.

```
 Arch Framework Installer — dry run   1/15
 ✔ [01/15] Environment ................ 1s
 > [02/15] Disk selection ............. validate
   [03/15] GPT partitioning ..........
 ─────────────────────────────────────────────
 [02/15] Disk selection           …
 Disk selection: validate
 c interrupt   ^v scroll the log
```

Une **installation réelle**, elle, continue de passer la main au terminal comme
avant. `install.sh` y pose cinq questions — chemin du disque à retaper deux fois,
phrase de passe LUKS, mots de passe root et utilisateur — et une interface plein
écran ne peut pas partager un terminal avec un enfant qui interroge l'utilisateur.
Les rendre non interactives voudrait dire réécrire `lib/luks.sh`, `lib/users.sh` et
`lib/ui.sh`, c'est-à-dire le chemin le plus dangereux du projet ; ce n'est pas fait
ici. En simulation ces cinq questions sont déjà sautées (`tasks/10_storage.sh`,
`tasks/20_encryption.sh`, `lib/users.sh`, et `run_command` qui n'exécute rien),
d'où le périmètre retenu.

`c` demande confirmation puis envoie `SIGINT` au groupe de processus : le trap de
`lib/task.sh` s'exécute, le nettoyage et le rollback ont lieu, et la simulation se
termine par 130. Quitter en cours de route n'est pas proposé — cela laisserait un
processus root installer sans personne pour regarder.

### Verrouillage des options incompatibles

Une option devenue incompatible reste affichée, grisée, avec sa raison. La
masquer laisserait chercher où elle est passée ; l'accepter puis échouer dans
`validate_config` ferait perdre du temps sans rien expliquer.

```
Swapfile size
   1) [-] no swapfile (zram only)
          locked: Hibernation writes the contents of memory to persistent
          storage. zram is cleared when power is cut, so a swapfile is required.
   2) [-] 8.0 GiB
          locked: A hibernation image is the whole of memory. A swapfile
          smaller than installed RAM cannot hold it.
   4) [x] 32.0 GiB (enough for hibernation)
```

Les règles sont déclarées dans `configurator/constraints.py` et reflètent les
contrôles de `lib/config.sh`. La disponibilité d'une valeur est calculée en
l'appliquant à une copie de la configuration puis en réévaluant les règles :
ajouter une règle change donc ce que le menu propose, sans second endroit à
mettre à jour.

Un cas mérite attention : choisir une taille de swap **crée** le sous-volume
`@swap`. Le verrouillage évalue donc la taille *avec* le sous-volume qu'elle
implique, sinon toute taille non nulle serait bloquée faute d'un sous-volume que
le menu allait ajouter de lui-même — bloquer un choix pour l'une de ses propres
conséquences.

### Clavier

Le clavier a **deux** noms, dans deux systèmes de nommage différents :

| Variable | Portée | Exemple |
| --- | --- | --- |
| `KEYMAP` | console, invite de déverrouillage LUKS | `fr_CH` |
| `XKB_LAYOUT` / `XKB_VARIANT` | session graphique | `ch` / `fr_nodeadkeys` |

`fr_CH` n'est pas une disposition xkb valide, et `ch` n'est pas un keymap console
valide : une seule valeur ne peut pas servir les deux.

Le menu les définit donc **ensemble**, à partir d'un seul choix. Ne renseigner que
`KEYMAP` laisse la session graphique en QWERTY US alors que la console est
correcte — un symptôme qui ne ressemble pas à un problème de configuration
clavier.

Niri lit sa propre configuration et non `/etc/X11`, donc la disposition est
injectée dans `config.kdl` :

```kdl
input {
    keyboard {
        xkb {
            layout "ch"
            variant "fr_nodeadkeys"
        }
        numlock
    }
}
```

`/etc/X11/xorg.conf.d/00-keyboard.conf` est également écrit à partir des mêmes
valeurs. Niri ne le consulte pas, mais tout le reste oui — y compris un
compositeur substitué plus tard.

La vérification finale refuse l'installation si la disposition est absente de la
configuration Niri.

### Disques refusés

Les disques inéligibles sont listés avec leur motif plutôt que masqués :

```
   2) [-] /dev/sdb  29 GiB, Ultra Fit, usb — Rejected: Arch live medium
```

La vérification qui compte reste `validate_partition_target_safety`, exécutée
juste avant `wipefs`.

--- système

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
