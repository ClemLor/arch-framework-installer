# Architecture

`install.sh` est l'unique point d'entrée. Il charge la configuration, applique
les surcharges CLI, initialise le journal puis délègue au moteur de tâches.
Les modes `--inspect` et `--plan-storage` restent strictement en lecture seule ;
`--partition` arrête le moteur après le stockage.

## Couches

```text
install.sh
  ├─ config/system.conf
  ├─ lib/        fonctions de domaine et orchestration
  └─ tasks/      unités ordonnées et vérifiables

configurator/            configuration seulement, jamais destructif
  ├─ menu.py             ce qui est demandé (éditeurs + contraintes)
  ├─ prompts.py          comment c'est demandé (invites texte)
  ├─ tui/                interface plein écran (curses)
  ├─ events.py           lecture du protocole de progression
  └─ runner.py           suit `install.sh --dry-run`
```

L'inspection matérielle appartient à `lib/system.sh` et `lib/disk.sh`. La
construction et la vérification GPT appartiennent à `lib/partition.sh`. Toutes
les mutations passent par `run_command`, qui applique le dry-run et journalise
commande, durée et statut.

## Moteur de tâches

`lib/task.sh` découvre `tasks/[0-9][0-9]_*.sh` avec un tri déterministe. Chaque
tâche expose `name`, `validate`, `execute`, `verify`, `cleanup` et `rollback`.
Le cycle normal est `validate → execute → verify → cleanup`. Un échec déclenche
le cleanup, le rollback prudent de la tâche partielle, puis les rollbacks des
tâches terminées dans l'ordre inverse. INT et TERM empruntent le même chemin.

`lib/state.sh` conserve la tâche et la phase courantes ainsi que la pile des
tâches réussies dans `state/install.state`. Ce fichier sert au diagnostic : les
tâches destructives ne sont jamais sautées automatiquement lors d'une reprise.
Le dry-run ne crée ni ne met à jour ce fichier, ce qui évite qu'un état possédé
par root après une installation empêche une simulation lancée sans `sudo`.
`lib/progress.sh` affiche `[n/total]` et la durée. Les journaux horodatés sont
placés sous `logs/`.

## Flux d'événements

`lib/events.sh` émet une copie lisible par une machine de ce que fait
l'installateur : le plan complet avant la première tâche, chaque changement de
phase, les fins, les échecs avec la phase fautive, les rollbacks, l'interruption
et le statut final. Format : `AFI1<TAB>kind<TAB>clé=valeur…`, une ligne par
événement, tabulations et retours à la ligne des valeurs remplacés par des
espaces — une valeur avec des espaces n'a donc rien à protéger.

L'émission est **coupée** tant que `AFI_EVENT_FD` ne désigne pas un descripteur
inscriptible, et `lib/progress.sh` n'est pas modifié : la sortie destinée à un
humain reste identique octet pour octet. Le descripteur est transmis par le
lecteur (`configurator/runner.py`) ; un tube donne une vraie fin de fichier quand
l'installateur et ses enfants ont terminé, ce qu'un fichier ne donne pas.

Trois propriétés valent d'être signalées, chacune étant sinon un vrai défaut :

- l'échappement des valeurs se fait par expansion de paramètre, sans sous-shell :
  `log_message` émet un événement par commande exécutée, et un fork par champ
  coûterait des milliers de forks par installation ;
- `trap 'EVENTS_ENABLED=false' PIPE` est un gestionnaire, pas `trap '' PIPE` :
  `SIG_IGN` serait hérité par tous les enfants, et plusieurs helpers reposent sur
  `SIGPIPE` pour arrêter un producteur dans un `… | grep -q`. Un lecteur disparu
  coûte les événements, jamais l'installation ;
- `event_emit` retourne toujours 0 : `install.sh` tourne sous `set -Eeuo
  pipefail`, et une télémétrie capable d'interrompre une installation serait pire
  que pas de télémétrie.

Les modules instrumentés (`logging.sh`, `state.sh`, `task.sh`) définissent des
stubs vides *si et seulement si* `lib/events.sh` n'est pas chargé, ce qui laisse
les tests unitaires sourcer un module isolé sans rien savoir des événements.

La configuration mémoire respecte `ZRAM_ENABLED`. Lorsqu'il est actif,
`zram-generator` crée un périphérique compressé en Zstd limité à la moitié de la
RAM. Lorsqu'il est désactivé, seul le fichier de configuration géré par
l'installateur dans la cible est retiré.

## Ordre d'installation

Environnement, sélection du disque, GPT, LUKS2 optionnel, Btrfs, montages,
pacstrap, configuration, paquets/services, utilisateur, Limine, TPM2/sécurité,
vérification finale, cleanup et fin. Avant le démontage, la tâche de readiness
revalide les montages, la configuration, tous les paquets et services, le compte
utilisateur, le bureau, zram, Limine et le profil LUKS/TPM2. Les opérations
irréversibles exigent le mode réel et une confirmation sur le périphérique
complet.

## Desktop

Le bureau cible est Niri avec Dank Material Shell (`dms-shell-niri`). Les
dotfiles restent dans un dépôt séparé et sont destinés à être appliqués avec
GNU Stow après installation. `greetd` ouvre la session Niri en auto-login ;
`niri.service` entraîne ensuite l'unité utilisateur officielle `dms.service`,
puis une unité dédiée verrouille la session dès que l'IPC DMS est prêt. La
configuration refuse l'auto-login lorsque ce verrouillage initial est désactivé.
Après une déconnexion, `greetd` exécute le greeter graphique fourni par DMS ;
`agreety` n'est pas utilisé par la configuration du projet.
