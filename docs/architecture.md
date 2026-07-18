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
`lib/progress.sh` affiche `[n/total]` et la durée. Les journaux horodatés sont
placés sous `logs/`.

## Ordre d'installation

Environnement, sélection du disque, GPT, LUKS2, Btrfs, montages, pacstrap,
configuration, paquets/services, utilisateur, Limine, TPM2/sécurité, cleanup et
fin. Les opérations irréversibles exigent le mode réel et une confirmation sur
le périphérique complet.

## Desktop

Le bureau cible est Niri avec Dank Material Shell (`dms-shell-niri`). Les
dotfiles restent dans un dépôt séparé et sont destinés à être appliqués avec
GNU Stow après installation.
