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
Le dry-run ne crée ni ne met à jour ce fichier, ce qui évite qu'un état possédé
par root après une installation empêche une simulation lancée sans `sudo`.
`lib/progress.sh` affiche `[n/total]` et la durée. Les journaux horodatés sont
placés sous `logs/`.

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
