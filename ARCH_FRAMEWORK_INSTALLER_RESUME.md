Oui. Le plus simple est de faire travailler Codex directement dans le dossier du dépôt, par étapes contrôlées.

1. Ouvre le bon dossier dans VS Code

Dans VS Code :

File → Open Folder

Sélectionne :

arch-framework-installer

Codex utilisera le workspace ouvert comme contexte et pourra lire les fichiers, proposer des modifications et exécuter des commandes dans le terminal selon les autorisations accordées. L’extension permet aussi d’ajouter les fichiers ouverts ou une sélection au prompt et de revoir les changements directement dans l’éditeur.

Vérifie d’abord l’état Git :

git status
git branch --show-current

Puis crée une branche de travail :

git switch -c feature/task-engine
2. Ajoute un fichier AGENTS.md

Ce fichier donnera à Codex les règles permanentes du projet. Crée à la racine :

# AGENTS.md

## Project

This repository contains a robust, reproducible Arch Linux installer designed
primarily for a Framework Laptop 13.

The installer runs from the official Arch Linux live ISO in UEFI mode.

## Main goals

- Reproducible installation
- Modular task-based architecture
- Idempotent operations whenever possible
- Full dry-run support
- Strict validation before destructive operations
- Verification after every operation
- Clear logs and actionable errors
- LUKS2 encryption with TPM2 support
- Btrfs with subvolumes and snapshots
- Limine bootloader
- Framework Laptop optimizations
- Hyprland desktop environment

## Coding rules

- Use Bash.
- Start executable scripts with `#!/usr/bin/env bash`.
- Use `set -Eeuo pipefail` in entry points.
- Quote all variable expansions unless intentional.
- Prefer `local` variables inside functions.
- Do not parse human-readable command output when a machine-readable format exists.
- Use `lsblk --json` or explicit columns where appropriate.
- Never silently ignore an error.
- Never execute destructive commands without validation and explicit confirmation.
- Every destructive operation must support dry-run.
- Hardware inspection must remain isolated in the appropriate library modules.
- Do not duplicate helpers already available in `lib/`.
- Keep tasks small and independently verifiable.
- Do not introduce dependencies without documenting them.

## Task API

Each task must expose:

- `task_<name>_name`
- `task_<name>_validate`
- `task_<name>_execute`
- `task_<name>_verify`
- `task_<name>_cleanup`
- `task_<name>_rollback`

Tasks must not call `exit`. They must return an error code and let the
orchestrator decide how to proceed.

## Safety

Never run real destructive storage commands during development or tests.

Commands such as the following must only run:

- from the official Arch live environment;
- against a validated installation target;
- outside dry-run mode;
- after explicit confirmation.

Examples:

- `wipefs`
- `sgdisk --zap-all`
- `cryptsetup luksFormat`
- `mkfs`
- `mkfs.btrfs`

Tests must use mocks, loop devices in an isolated integration environment, or
command capture. They must never target a physical disk.

## Testing

Before considering work complete, run when available:

```bash
bash -n install.sh
bash -n lib/*.sh
bash -n tasks/*.sh
shellcheck install.sh lib/*.sh tasks/*.sh tests/**/*.sh

Add tests for new behavior.

Documentation

Update the relevant file under docs/ whenever architecture, configuration,
storage, boot, security, recovery, or testing behavior changes.

Git
Make focused changes.
Do not rewrite unrelated files.
Do not delete existing functionality without explaining why.
Do not commit unless explicitly requested.
Show a summary of changed files and test results at the end.

## 3. Commence par une tâche d’analyse

Dans le panneau Codex, donne-lui d’abord ce prompt :

```text
Analyse entièrement ce dépôt sans modifier aucun fichier.

Objectifs :
1. comprendre l’architecture actuelle ;
2. identifier les fonctions existantes réutilisables ;
3. relever les incohérences entre install.sh, lib/, config/ et docs/ ;
4. proposer un plan précis pour introduire un moteur de tâches ;
5. identifier les risques de sécurité liés aux commandes destructives.

Ne modifie rien.
Ne lance aucune commande destructive.
Tu peux exécuter uniquement des commandes de lecture et des validations comme
git status, find, bash -n et shellcheck.

Présente ensuite :
- l’état actuel du projet ;
- les problèmes détectés ;
- les fichiers à créer ;
- les fichiers à modifier ;
- l’ordre recommandé d’implémentation.

Cette première étape évite que Codex reconstruise des fonctions que nous avons déjà.

4. Fais-lui implémenter le moteur de tâches

Une fois son analyse terminée, utilise ce prompt :

Implémente la première phase du projet : le moteur de tâches.

Lis et respecte AGENTS.md.

Crée une architecture simple et robuste, sans sur-ingénierie.

Fonctionnalités attendues :
- découverte ordonnée des fichiers dans tasks/ ;
- registre des tâches ;
- exécution validate → execute → verify ;
- cleanup après chaque tâche ;
- rollback des tâches déjà exécutées en cas d’échec ;
- chronométrage ;
- progression [n/total] ;
- support complet du dry-run ;
- journal d’exécution ;
- aucun exit depuis les tâches ;
- reprise propre des signaux INT et TERM.

Crée au minimum :
- lib/task.sh
- lib/state.sh
- lib/progress.sh
- tasks/00_environment.sh
- tests/unit/test_task_engine.sh
- docs/architecture.md ou sa mise à jour

Adapte install.sh pour utiliser le moteur tout en conservant :
- --inspect
- --plan-storage
- --dry-run
- --verbose
- --config

Contraintes :
- ne lance aucune commande destructive ;
- ne modifie pas encore réellement le stockage ;
- conserve la compatibilité avec les modules existants ;
- évite les frameworks de test externes pour le moment ;
- utilise uniquement Bash pour les tests.

À la fin :
1. exécute bash -n sur tous les scripts ;
2. exécute shellcheck s’il est installé ;
3. exécute les tests ;
4. affiche la liste des fichiers modifiés ;
5. explique les choix importants ;
6. ne crée aucun commit.
5. Revois systématiquement ses changements

Avant d’accepter :

git status
git diff --stat
git diff

Puis :

bash -n install.sh
find lib tasks tests -type f -name '*.sh' -print0 |
    xargs -0 -n1 bash -n

Avec ShellCheck :

shellcheck install.sh lib/*.sh tasks/*.sh tests/unit/*.sh

Puis les tests :

bash tests/unit/test_task_engine.sh
6. Deuxième tâche : vrai partitionnement

Quand le moteur sera validé, donne-lui :

Implémente maintenant la tâche de partitionnement réel dans tasks/10_storage.sh.

Respecte AGENTS.md et réutilise lib/disk.sh et lib/partition.sh.

La tâche doit :
- valider que l’environnement est l’ISO Arch officielle en mode UEFI ;
- valider que TARGET_DISK est un disque complet ;
- refuser le support live ;
- refuser USB et removable ;
- vérifier les montages ;
- vérifier la capacité ;
- afficher le plan exact ;
- exiger une confirmation explicite contenant le chemin complet du disque ;
- exécuter wipefs et sgdisk uniquement hors dry-run ;
- attendre l’apparition des partitions ;
- appeler partprobe et udevadm settle ;
- vérifier GPT, nombre de partitions, types GPT, tailles et alignement ;
- effectuer un cleanup sûr en cas d’erreur ;
- ne jamais tenter de restaurer automatiquement les anciennes données ;
- journaliser toutes les commandes.

Ajoute des tests unitaires basés sur des mocks.
Ne lance jamais les commandes destructives sur un disque physique pendant les tests.
Ne crée aucun commit.
Workflow conseillé

Une phase Codex doit toujours suivre ce cycle :

Analyse
→ implémentation
→ tests automatiques
→ revue du diff
→ test manuel en dry-run
→ commit Git

Après validation :

git add .
git commit -m "feat: add task execution engine"

Codex dans VS Code est adapté aux refactorisations et fonctionnalités complètes, et peut travailler localement avec le dépôt ouvert.

Le meilleur prochain geste est donc de créer AGENTS.md, ouvrir le panneau Codex, puis lui envoyer le prompt d’analyse ci-dessus.

il manque des informations ou des fichiers sont vide pour codex

Oui, probablement. La structure proposée contient beaucoup de fichiers destinés aux étapes futures, donc certains peuvent être vides ou absents. Ce n’est pas bloquant pour Codex, mais il faut lui demander de faire l’inventaire avant d’implémenter et de ne pas supposer que chaque fichier contient déjà du code.

Codex lit le dépôt ouvert et les instructions de AGENTS.md avant de travailler. Il peut donc repérer les fichiers vides, comprendre les modules existants et compléter uniquement ce qui est nécessaire.

Donne-lui d’abord ce prompt :

Analyse le dépôt complet avant toute modification.

Important :
- certains fichiers de l’architecture peuvent être absents ;
- certains fichiers peuvent être vides ou contenir seulement un squelette ;
- ne considère pas un fichier vide comme une implémentation existante ;
- ne supprime aucune fonctionnalité déjà opérationnelle ;
- ne lance aucune commande destructive.

Commence par produire un inventaire contenant :

1. tous les fichiers présents ;
2. les fichiers vides ;
3. les fichiers contenant uniquement des commentaires ou des fonctions factices ;
4. les fichiers mentionnés dans la documentation mais absents ;
5. les fonctions appelées mais non définies ;
6. les modules chargés par install.sh ;
7. les tests existants et leur état ;
8. les incohérences entre config/, lib/, tasks/, docs/ et install.sh.

Exécute uniquement des commandes sûres :
- git status
- find
- grep
- bash -n
- shellcheck si disponible

Ne modifie encore aucun fichier.

À la fin, propose :
- les fichiers réellement nécessaires pour le moteur de tâches ;
- les fichiers à conserver ;
- les fichiers à compléter ;
- les fichiers inutiles à ne pas créer pour l’instant ;
- un ordre d’implémentation précis.

Tu peux aussi effectuer toi-même un inventaire rapide avant de lancer Codex :

find . -type f -empty -print

Pour trouver les scripts qui ne contiennent pratiquement rien :

find . -type f -name '*.sh' -exec sh -c '
    for file do
        lines=$(grep -Ev "^[[:space:]]*$|^[[:space:]]*#" "$file" | wc -l)
        if [ "$lines" -eq 0 ]; then
            printf "%s\n" "$file"
        fi
    done
' sh {} +

Pour repérer les fichiers déjà référencés :

grep -RInE 'source |tasks/|lib/' install.sh lib tasks 2>/dev/null

Après son analyse, utilise ce second prompt :

Implémente uniquement la première phase validée dans ton analyse.

Priorité :
1. conserver les fonctions existantes et opérationnelles ;
2. créer seulement les fichiers nécessaires ;
3. compléter les fichiers vides utiles ;
4. ne pas créer tous les modules futurs sous forme de fichiers vides ;
5. adapter install.sh sans casser --inspect et --plan-storage ;
6. ajouter les tests du moteur de tâches ;
7. mettre à jour AGENTS.md et docs/architecture.md si nécessaire.

Le moteur doit fournir :
- registre ordonné des tâches ;
- validate, execute, verify, cleanup et rollback ;
- progression ;
- logs ;
- gestion INT et TERM ;
- dry-run ;
- aucun exit dans les tâches.

N’implémente pas encore le partitionnement réel.
Ne lance aucune commande destructive.
Ne crée aucun commit.

À la fin, exécute les validations et affiche :
- fichiers créés ;
- fichiers modifiés ;
- fichiers laissés volontairement vides ;
- résultats des tests ;
- limitations restantes.

Je déconseille surtout de créer maintenant cinquante fichiers vides. Ils donnent une fausse impression d’avancement et peuvent perturber Codex. Il vaut mieux avoir :

lib/task.sh
lib/state.sh
lib/progress.sh
tasks/00_environment.sh
tests/unit/test_task_engine.sh

réellement implémentés, puis ajouter les autres modules au moment où leur fonctionnalité est développée. OpenAI recommande également un AGENTS.md pratique et précis plutôt qu’un long ensemble d’instructions vagues.

Fait un résumer de tout notre conversation dans un md sans oublier aucuns points importants et a la fin rajoute une section objectif précis à atteindre 

J'ai préparé un premier document Markdown récapitulatif.

Tu peux le télécharger ici :

📄 
ARCH_FRAMEWORK_INSTALLER_RESUME.md

En revanche, je pense qu'on peut faire beaucoup mieux pour un projet de cette ampleur. Ce document est un résumé, alors que nous avons déjà pris énormément de décisions d'architecture.

Je te proposerais plutôt un document de 20 à 40 pages servant de véritable référence du projet, comprenant notamment :

la vision et les objectifs ;
toutes les décisions d'architecture prises jusqu'à présent ;
l'arborescence complète du dépôt ;
le rôle de chaque dossier et de chaque module ;
les conventions de code Bash ;
les règles de sécurité ;
la stratégie de validation et de rollback ;
le fonctionnement du moteur de tâches ;
le système de logs ;
la gestion de l'état (state) ;
le workflow avec Codex ;
les conventions Git ;
la feuille de route détaillée jusqu'à la version 1.0.

Ce document deviendrait le guide officiel du projet et servirait à la fois à toi, à Codex et à toute personne qui contribuerait au dépôt. Il remplacerait avantageusement un simple résumé et donnerait à Codex tout le contexte nécessaire pour travailler de façon autonome et cohérente. 

il me semble le fichier n'est pas bon il parle d'hyprland mais dans le project c'est niri et dank normalement
Analyzed
from textwrap import dedent

content = dedent("""\
# Arch Framework Installer — Résumé complet du projet

## 1. Vision générale

Le projet consiste à créer un installeur Arch Linux :

- reproductible ;
- modulaire ;
- maintenable ;
- documenté ;
- testable ;
- sécurisé ;
- conçu en priorité pour un Framework Laptop 13 avec processeur Intel Core Ultra 5 ;
- suffisamment générique pour pouvoir être adapté à d'autres machines plus tard.

L'objectif n'est pas de créer une distribution Linux personnelle, mais un installeur Arch Linux propre, transparent et réutilisable.

L'installeur est prévu pour être exécuté depuis l'image ISO officielle d'Arch Linux, démarrée en mode UEFI.

---

## 2. Environnement cible

### Matériel principal

- Framework Laptop 13
- Intel Core Ultra 5 125H
- 32 Go de RAM
- SSD NVMe
- lecteur d'empreintes digitales Framework
- prise en charge du firmware Framework via `fwupd`

### Environnement graphique retenu

Le projet utilise :

- **Niri** comme compositeur Wayland ;
- **Dank** comme couche d'environnement, interface et intégration utilisateur ;
- un environnement moderne, fluide et stable ;
- une configuration utilisable sans dépendre exclusivement du tiling strict.

Hyprland ne fait pas partie de l'objectif actuel du projet.

### Logiciels et usages prévus

Le système doit notamment pouvoir accueillir :

- VS Code ou VSCodium ;
- Cursor ;
- KiCad ;
- Kitty ou Ghostty ;
- Fish ;
- Dolphin ;
- Yazi ;
- LibreWolf ;
- Microsoft Edge ;
- outils de développement ;
- outils Framework ;
- synchronisation OneDrive temporaire ;
- migration future vers un NAS.

---

## 3. Principes du projet

Le projet doit respecter les principes suivants :

- configuration centralisée ;
- aucune valeur importante codée en dur ;
- support du dry-run sur toutes les opérations pertinentes ;
- validations strictes avant les actions destructives ;
- vérifications après chaque étape ;
- journalisation détaillée ;
- architecture modulaire ;
- idempotence autant que possible ;
- documentation synchronisée avec le comportement réel ;
- tests automatisés ;
- reprise propre après interruption ;
- rollback lorsqu'il est techniquement sûr ;
- aucune commande destructive exécutée pendant les tests ;
- séparation entre l'installeur et les dotfiles.

---

## 4. Préférence de travail importante

Lorsqu'un fichier doit être créé ou modifié :

**Toujours fournir le fichier complet. Ne jamais fournir un patch ou un diff.**

Cette règle s'applique aux échanges avec ChatGPT comme aux instructions données à Codex lorsque cela est pertinent.

---

## 5. Structure générale du dépôt

Nom du projet :

```text
arch-framework-installer

Structure générale retenue :

arch-framework-installer/
├── .github/
│   └── workflows/
├── assets/
├── cache/
├── config/
├── docs/
├── hooks/
│   ├── post-install/
│   ├── post-task/
│   ├── pre-install/
│   └── pre-task/
├── lib/
├── logs/
├── overlays/
│   ├── etc/
│   ├── home/
│   └── usr/
├── packages/
├── services/
├── state/
├── tasks/
├── templates/
├── tests/
│   ├── integration/
│   ├── unit/
│   └── vm/
├── .gitignore
├── AGENTS.md
├── install.sh
├── LICENSE
├── PROJECT.md
└── README.md

Il ne faut pas créer des dizaines de fichiers vides uniquement pour remplir cette structure.

Les fichiers doivent être ajoutés au moment où leur rôle devient réel et nécessaire.

6. Documentation

Documents principaux :

docs/
├── architecture.md
├── boot.md
├── desktop.md
├── development.md
├── packages.md
├── recovery.md
├── security.md
├── storage.md
├── testing.md
└── update.md
Rôle des documents
architecture.md : architecture générale et moteur de tâches ;
storage.md : partitionnement, LUKS2, Btrfs, sous-volumes et montages ;
security.md : TPM2, phrase de récupération, empreinte et sécurité ;
boot.md : Limine, initramfs, noyaux et démarrage ;
desktop.md : Niri, Dank et environnement utilisateur ;
packages.md : organisation des listes de paquets ;
recovery.md : récupération, dépannage et restauration ;
update.md : stratégie de mise à jour ;
development.md : conventions de contribution ;
testing.md : tests unitaires, intégration et machines virtuelles.

PROJECT.md doit rester court et présenter l'intention générale du projet.

7. Architecture de stockage

Architecture retenue :

UEFI
  ↓
LUKS2
  ↓
Btrfs
Partition EFI
format FAT32 ;
taille de 1 Gio ;
utilisée par Limine ;
partition GPT dédiée.
Partition système
partition occupant le reste du disque ;
chiffrement LUKS2 ;
Btrfs à l'intérieur du conteneur chiffré.
Sous-volumes Btrfs
@
@home
@snapshots
@cache
@log
Options principales
compression zstd ;
snapshots avec snapper ;
pas de swapfile ;
swap assuré par zram.
Déverrouillage
prise en charge de TPM2 ;
phrase de récupération toujours disponible ;
le TPM2 ne doit jamais être l'unique moyen de récupération.
8. Configuration centralisée

Fichier principal :

config/system.conf

Variables importantes déjà prévues :

HOSTNAME
TARGET_DISK
EFI_SIZE
FILESYSTEM
BOOTLOADER
DEFAULT_KERNEL
TPM2_ENABLED
LUKS_ENABLED
EFI_PARTITION_LABEL
SYSTEM_PARTITION_LABEL
MINIMUM_DISK_SIZE
SWAP_SIZE
HIBERNATION_ENABLED

Le comportement de l'installeur doit venir de la configuration, pas de valeurs dispersées dans les scripts.

Les arguments CLI doivent pouvoir surcharger les valeurs de configuration.

Un problème déjà identifié concernait l'écrasement des options CLI par le chargement de la configuration.

La solution retenue utilise notamment :

CLI_DRY_RUN
CLI_VERBOSE

Ordre attendu :

lire les arguments CLI ;
charger la configuration ;
appliquer les surcharges CLI.
9. Modes de fonctionnement existants ou prévus
Inspection
sudo ./install.sh --inspect

Doit afficher :

informations système ;
firmware ;
CPU ;
mémoire ;
mode de démarrage ;
disque cible ;
support Live ;
disques candidats ;
configuration ;
état de préparation.
Planification du stockage
sudo ./install.sh --plan-storage

Doit afficher :

la table de partitions actuelle ;
la disposition future ;
les partitions prévues ;
les commandes qui seraient exécutées ;
les validations de capacité et de sécurité.

Cette commande ne doit jamais modifier le disque.

Dry-run
sudo ./install.sh --dry-run

Le dry-run doit être pris en charge dans toutes les étapes concernées.

Verbose
sudo ./install.sh --verbose

Permet d'afficher davantage d'informations de diagnostic.

Partitionnement réel futur
sudo ./install.sh --partition

Cette commande devra exécuter le partitionnement réel uniquement après toutes les validations et une confirmation destructive explicite.

10. Validation de l'environnement

L'installeur doit vérifier :

qu'il est exécuté depuis l'environnement Live officiel d'Arch Linux ;
que la machine a démarré en mode UEFI ;
que le disque cible existe ;
que la cible est un disque complet et non une partition ;
que le support Live n'est jamais choisi ;
que les périphériques amovibles sont refusés ;
que le disque a une capacité suffisante ;
que les partitions montées sont détectées ;
que les dépendances nécessaires sont disponibles ;
que le réseau fonctionne lorsque l'étape en a besoin.
Validation réseau

Ordre de repli retenu :

curl
wget
ping
Cas d'un disque monté
installation réelle : erreur fatale ;
dry-run ou planification : avertissement seulement.
11. Isolation de l'inspection matérielle

Modules prévus :

lib/system.sh
lib/disk.sh

Seuls ces modules doivent inspecter directement le matériel.

Les autres modules ne doivent pas appeler directement des commandes comme :

lsblk

Ils doivent utiliser l'API fournie par les modules d'inspection.

12. Planification du partitionnement

Module prévu :

lib/partition.sh

Fonctions déjà définies conceptuellement :

size_to_mib
size_to_bytes
get_partition_path
get_efi_partition_path
get_system_partition_path
get_efi_end_mib
validate_partition_dependencies
validate_target_disk_capacity
validate_efi_partition_size
validate_partition_target_safety
validate_storage_plan
show_existing_partition_layout
show_planned_partition_layout
show_partition_commands
show_storage_plan

Le plan actuel produit notamment :

une partition EFI commençant à 1 MiB ;
une partition système commençant après l'EFI ;
une table GPT ;
des commandes wipefs, sgdisk, partprobe et udevadm prévues.

Un test en dry-run et mode verbose a déjà permis de confirmer le bon fonctionnement de la planification.

13. Architecture des bibliothèques

Modules principaux prévus :

lib/
├── bootloader.sh
├── btrfs.sh
├── chroot.sh
├── commands.sh
├── common.sh
├── config.sh
├── disk.sh
├── hooks.sh
├── logging.sh
├── luks.sh
├── mount.sh
├── packages.sh
├── pacstrap.sh
├── partition.sh
├── progress.sh
├── rollback.sh
├── services.sh
├── snapshots.sh
├── state.sh
├── system.sh
├── task.sh
├── ui.sh
├── users.sh
├── validation.sh
└── verify.sh

Tous ces fichiers ne doivent pas être créés vides dès le départ.

Responsabilités importantes
logging.sh

Fonctions prévues :

info
warn
success
error
fatal
commands.sh

Fonctions prévues :

run_command
run_critical
config.sh

Fonction principale :

load_config
validation.sh

Regroupe les validations communes.

ui.sh

Regroupe les interactions utilisateur.

task.sh

Contient le moteur d'orchestration des tâches.

state.sh

Gère l'état d'exécution et la reprise.

progress.sh

Affiche l'avancement.

14. Architecture par tâches

Organisation prévue :

tasks/
├── 00_environment.sh
├── 05_disk_selection.sh
├── 10_storage.sh
├── 20_encryption.sh
├── 30_filesystem.sh
├── 40_mount.sh
├── 50_base_system.sh
├── 60_configuration.sh
├── 70_packages.sh
├── 80_users.sh
├── 90_bootloader.sh
├── 95_security.sh
├── 98_cleanup.sh
└── 99_finish.sh
API commune

Chaque tâche doit exposer une API cohérente :

task_<name>_name
task_<name>_validate
task_<name>_execute
task_<name>_verify
task_<name>_cleanup
task_<name>_rollback
Règles
une tâche ne doit jamais appeler exit ;
elle retourne un code d'erreur ;
l'orchestrateur décide de poursuivre, nettoyer ou annuler ;
les tâches doivent rester petites ;
les tâches doivent être vérifiables indépendamment ;
les commandes destructives doivent toujours passer par les helpers communs.
15. Moteur de tâches

Le moteur doit gérer :

la découverte ordonnée des tâches ;
l'enregistrement des tâches ;
la validation ;
l'exécution ;
la vérification ;
le nettoyage ;
le rollback ;
la progression ;
le chronométrage ;
les journaux ;
le dry-run ;
les interruptions SIGINT et SIGTERM ;
l'état global ;
la reprise contrôlée lorsque cela est possible.

Séquence type :

validate
  ↓
execute
  ↓
verify
  ↓
cleanup

En cas d'échec :

failure
  ↓
cleanup
  ↓
rollback
  ↓
controlled stop
16. Journalisation

Les journaux doivent être enregistrés dans :

logs/

Exemple :

logs/2026-07-18-08-31-42-install.log

Chaque commande critique doit enregistrer :

l'heure ;
la commande ;
sa durée ;
son code de retour ;
le contexte ;
les erreurs éventuelles.

Les journaux doivent permettre de retrouver rapidement l'étape fautive.

17. Gestion des erreurs et rollback

Le projet doit éviter les arrêts désordonnés.

Principes :

nettoyer les montages temporaires ;
fermer les mappings LUKS ouverts par l'installeur ;
ne jamais prétendre restaurer les anciennes données après un repartitionnement ;
ne jamais masquer une erreur ;
effectuer uniquement des rollbacks techniquement sûrs ;
signaler clairement les opérations irréversibles.

Le rollback n'est pas synonyme de récupération des données détruites.

18. Vérifications systématiques

Chaque tâche doit prouver qu'elle a réussi.

Stockage

Vérifier :

table GPT ;
nombre de partitions ;
types GPT ;
tailles ;
alignement ;
présence des périphériques ;
labels ;
UUID si applicable.
LUKS2

Vérifier :

format LUKS2 ;
UUID ;
mapping ouvert ;
configuration TPM2 ;
phrase de récupération disponible.
Btrfs

Vérifier :

type de système de fichiers ;
label ;
sous-volumes ;
options de montage ;
compression ;
snapshots.
Boot

Vérifier :

présence de Limine ;
configuration générée ;
fichiers du noyau ;
initramfs ;
entrées de démarrage.
Desktop

Vérifier :

Niri installé ;
Dank installé ;
session disponible ;
services utilisateur nécessaires ;
configuration copiée ;
aucun conflit évident avec l'environnement.
19. Barre de progression

Exemple prévu :

[01/13] Environment       ✔
[02/13] Disk selection    ✔
[03/13] Storage           …
[04/13] Encryption

Une barre de progression peut aussi être affichée, mais elle ne doit jamais masquer les informations utiles des logs.

20. Tests

Organisation prévue :

tests/
├── integration/
├── unit/
└── vm/
Vérifications minimales
bash -n install.sh
bash -n lib/*.sh
bash -n tasks/*.sh
shellcheck install.sh lib/*.sh tasks/*.sh tests/**/*.sh
Règles de sécurité

Les tests ne doivent jamais cibler un disque physique.

Ils doivent utiliser :

mocks ;
capture de commandes ;
périphériques loop dans un environnement isolé ;
machines virtuelles pour les tests complets.
21. Stratégie de développement

La stratégie retenue consiste à développer une fonctionnalité complète avant de passer à la suivante.

Chaque fonctionnalité doit inclure :

sa documentation ;
sa configuration ;
ses validations ;
son implémentation ;
ses vérifications ;
ses tests.

Il faut éviter de créer toute l'architecture sous forme de fichiers vides.

22. Rôle de Codex

Codex est installé dans VS Code et travaille directement dans le dépôt ouvert.

Codex peut gérer
inventaire du dépôt ;
analyse des fichiers ;
implémentation ;
refactoring ;
création et modification des fichiers ;
exécution de bash -n ;
exécution de ShellCheck ;
exécution des tests ;
synthèse des fichiers modifiés.
ChatGPT reste utile pour
architecture ;
choix techniques ;
arbitrages ;
rédaction des spécifications ;
revues de conception ;
analyse des risques ;
planification des étapes.
23. AGENTS.md

Un fichier AGENTS.md doit être présent à la racine du dépôt.

Il doit préciser :

le but du projet ;
l'environnement cible ;
les conventions Bash ;
les règles de sécurité ;
l'API des tâches ;
le comportement du dry-run ;
les règles de test ;
les règles Git ;
l'interdiction des commandes destructives pendant le développement ;
l'obligation de ne pas créer de commit sans demande explicite ;
l'obligation de résumer les changements et résultats des tests.
24. Workflow avec Codex

Cycle recommandé :

Analyse
  ↓
Inventaire
  ↓
Plan
  ↓
Implémentation d'une phase
  ↓
Tests
  ↓
Revue Git
  ↓
Test manuel en dry-run
  ↓
Commit
Première analyse

Codex doit repérer :

fichiers présents ;
fichiers vides ;
fichiers factices ;
fichiers absents mais documentés ;
fonctions appelées mais non définies ;
modules chargés par install.sh ;
tests existants ;
incohérences entre config/, lib/, tasks/, docs/ et install.sh.
Règles de modification
ne pas supprimer une fonctionnalité existante sans justification ;
ne pas réécrire des fichiers sans rapport ;
ne pas lancer de commande destructive ;
ne pas créer de commit sans demande ;
conserver --inspect, --plan-storage, --dry-run, --verbose et --config.
25. Ordre de réalisation retenu
Phase 1 — Socle d'exécution

Créer ou compléter :

lib/task.sh
lib/state.sh
lib/progress.sh
tasks/00_environment.sh
tests/unit/test_task_engine.sh
docs/architecture.md

Objectifs :

registre ordonné ;
validate → execute → verify ;
cleanup ;
rollback ;
chronométrage ;
progression ;
dry-run ;
logs ;
gestion des signaux ;
tests.
Phase 2 — Stockage réel

Implémenter :

tasks/10_storage.sh

Fonctions attendues :

validations strictes ;
confirmation destructive avec le chemin complet du disque ;
wipefs ;
sgdisk --zap-all ;
création GPT ;
création EFI ;
création système ;
partprobe ;
udevadm settle ;
attente de l'apparition des partitions ;
vérification complète ;
tests par mocks.
Phase 3 — Chiffrement et Btrfs

Implémenter :

LUKS2 ;
phrase de récupération ;
TPM2 ;
Btrfs ;
sous-volumes ;
options de montage ;
zram ;
snapper.
Phase 4 — Installation Arch

Implémenter :

pacstrap ;
génération de fstab ;
configuration chroot ;
locale ;
clavier suisse français sans touches mortes ;
fuseau horaire ;
hostname ;
réseau ;
utilisateurs ;
sudo.
Phase 5 — Boot et sécurité

Implémenter :

Limine ;
noyau principal ;
noyau LTS prioritaire ou disponible en secours selon la configuration retenue ;
initramfs ;
TPM2 ;
fprintd ;
fwupd ;
préparation Secure Boot ;
récupération.
Phase 6 — Desktop

Implémenter :

Niri ;
Dank ;
Fish ;
terminal choisi ;
outils de fichiers ;
applications principales ;
services utilisateur ;
dotfiles séparés via Stow ;
intégration Framework.
Phase 7 — Qualité finale

Implémenter :

GitHub Actions ;
ShellCheck ;
tests unitaires ;
tests d'intégration ;
tests VM ;
documentation finale ;
procédure de récupération ;
validation complète sur Framework Laptop.
Objectif précis à atteindre

L'objectif final est de disposer d'un dépôt Git capable d'installer automatiquement, depuis l'ISO officielle d'Arch Linux, un système complet et reproductible sur un Framework Laptop 13.

Le résultat attendu doit inclure :

une inspection fiable du matériel et de l'environnement Live ;
une configuration centralisée et surchargeable par la ligne de commande ;
un moteur de tâches robuste avec logs, état, progression, vérification, cleanup et rollback ;
un partitionnement GPT sécurisé ;
une partition EFI de 1 Gio ;
un système chiffré en LUKS2 ;
un déverrouillage TPM2 avec phrase de récupération ;
un système Btrfs avec @, @home, @snapshots, @cache et @log ;
la compression zstd ;
zram sans swapfile ;
Snapper pour les snapshots ;
l'installation complète d'Arch Linux ;
Limine comme bootloader ;
un noyau principal avec une stratégie LTS de secours ou prioritaire selon la configuration finale ;
la prise en charge de fwupd et fprintd ;
un bureau Wayland basé sur Niri et Dank ;
Fish et les outils utilisateur retenus ;
une configuration de clavier suisse français sans touches mortes ;
une architecture séparant clairement l'installeur des dotfiles ;
une suite de tests empêchant toute commande destructive sur un disque physique ;
une documentation suffisante pour que Codex ou un autre contributeur puisse poursuivre le projet sans perdre les décisions prises ;
une installation complète validée en dry-run, en machine virtuelle, puis sur le Framework Laptop réel.

Le projet sera considéré comme abouti lorsqu'une installation complète pourra être lancée de manière contrôlée, vérifiée et reproductible, sans étape manuelle non documentée, tout en conservant une méthode de récupération claire en cas de problème.
""")

path = "/mnt/data/ARCH_FRAMEWORK_INSTALLER_RESUME_CORRIGE.md"
with open(path, "w", encoding="utf-8") as f:
f.write(content)

print(path)

STDOUT/STDERR
/mnt/data/ARCH_FRAMEWORK_INSTALLER_RESUME_CORRIGE.md


Tu avais raison : Hyprland était une erreur. Le projet cible bien Niri + Dank.

J’ai corrigé le document et remplacé l’ancien résumé par une version beaucoup plus complète et fidèle à toutes les décisions prises :

ARCH_FRAMEWORK_INSTALLER_RESUME_CORRIGE.md 

Library
/
Linux
/
ARCH_FRAMEWORK_INSTALLER_RESUME_CORRIGE.md
# Arch Framework Installer — Résumé complet du projet

## 1. Vision générale

Le projet consiste à créer un installeur Arch Linux :

- reproductible ;
- modulaire ;
- maintenable ;
- documenté ;
- testable ;
- sécurisé ;
- conçu en priorité pour un Framework Laptop 13 avec processeur Intel Core Ultra 5 ;
- suffisamment générique pour pouvoir être adapté à d'autres machines plus tard.

L'objectif n'est pas de créer une distribution Linux personnelle, mais un installeur Arch Linux propre, transparent et réutilisable.

L'installeur est prévu pour être exécuté depuis l'image ISO officielle d'Arch Linux, démarrée en mode UEFI.

---

## 2. Environnement cible

### Matériel principal

- Framework Laptop 13
- Intel Core Ultra 5 125H
- 32 Go de RAM
- SSD NVMe
- lecteur d'empreintes digitales Framework
- prise en charge du firmware Framework via `fwupd`

### Environnement graphique retenu

Le projet utilise :

- **Niri** comme compositeur Wayland ;
- **Dank** comme couche d'environnement, interface et intégration utilisateur ;
- un environnement moderne, fluide et stable ;
- une configuration utilisable sans dépendre exclusivement du tiling strict.

Hyprland ne fait pas partie de l'objectif actuel du projet.

### Logiciels et usages prévus

Le système doit notamment pouvoir accueillir :

- VS Code ou VSCodium ;
- Cursor ;
- KiCad ;
- Kitty ou Ghostty ;
- Fish ;
- Dolphin ;
- Yazi ;
- LibreWolf ;
- Microsoft Edge ;
- outils de développement ;
- outils Framework ;
- synchronisation OneDrive temporaire ;
- migration future vers un NAS.

---

## 3. Principes du projet

Le projet doit respecter les principes suivants :

- configuration centralisée ;
- aucune valeur importante codée en dur ;
- support du dry-run sur toutes les opérations pertinentes ;
- validations strictes avant les actions destructives ;
- vérifications après chaque étape ;
- journalisation détaillée ;
- architecture modulaire ;
- idempotence autant que possible ;
- documentation synchronisée avec le comportement réel ;
- tests automatisés ;
- reprise propre après interruption ;
- rollback lorsqu'il est techniquement sûr ;
- aucune commande destructive exécutée pendant les tests ;
- séparation entre l'installeur et les dotfiles.

---

## 4. Préférence de travail importante

Lorsqu'un fichier doit être créé ou modifié :

**Toujours fournir le fichier complet. Ne jamais fournir un patch ou un diff.**

Cette règle s'applique aux échanges avec ChatGPT comme aux instructions données à Codex lorsque cela est pertinent.

---

## 5. Structure générale du dépôt

Nom du projet :

```text
arch-framework-installer
```

Structure générale retenue :

```text
arch-framework-installer/
├── .github/
│   └── workflows/
├── assets/
├── cache/
├── config/
├── docs/
├── hooks/
│   ├── post-install/
│   ├── post-task/
│   ├── pre-install/
│   └── pre-task/
├── lib/
├── logs/
├── overlays/
│   ├── etc/
│   ├── home/
│   └── usr/
├── packages/
├── services/
├── state/
├── tasks/
├── templates/
├── tests/
│   ├── integration/
│   ├── unit/
│   └── vm/
├── .gitignore
├── AGENTS.md
├── install.sh
├── LICENSE
├── PROJECT.md
└── README.md
```

Il ne faut pas créer des dizaines de fichiers vides uniquement pour remplir cette structure.

Les fichiers doivent être ajoutés au moment où leur rôle devient réel et nécessaire.

---

## 6. Documentation

Documents principaux :

```text
docs/
├── architecture.md
├── boot.md
├── desktop.md
├── development.md
├── packages.md
├── recovery.md
├── security.md
├── storage.md
├── testing.md
└── update.md
```

### Rôle des documents

- `architecture.md` : architecture générale et moteur de tâches ;
- `storage.md` : partitionnement, LUKS2, Btrfs, sous-volumes et montages ;
- `security.md` : TPM2, phrase de récupération, empreinte et sécurité ;
- `boot.md` : Limine, initramfs, noyaux et démarrage ;
- `desktop.md` : Niri, Dank et environnement utilisateur ;
- `packages.md` : organisation des listes de paquets ;
- `recovery.md` : récupération, dépannage et restauration ;
- `update.md` : stratégie de mise à jour ;
- `development.md` : conventions de contribution ;
- `testing.md` : tests unitaires, intégration et machines virtuelles.

`PROJECT.md` doit rester court et présenter l'intention générale du projet.

---

## 7. Architecture de stockage

Architecture retenue :

```text
UEFI
  ↓
LUKS2
  ↓
Btrfs
```

### Partition EFI

- format FAT32 ;
- taille de 1 Gio ;
- utilisée par Limine ;
- partition GPT dédiée.

### Partition système

- partition occupant le reste du disque ;
- chiffrement LUKS2 ;
- Btrfs à l'intérieur du conteneur chiffré.

### Sous-volumes Btrfs

```text
@
@home
@snapshots
@cache
@log
```

### Options principales

- compression `zstd` ;
- snapshots avec `snapper` ;
- pas de swapfile ;
- swap assuré par `zram`.

### Déverrouillage

- prise en charge de TPM2 ;
- phrase de récupération toujours disponible ;
- le TPM2 ne doit jamais être l'unique moyen de récupération.

---

## 8. Configuration centralisée

Fichier principal :

```text
config/system.conf
```

Variables importantes déjà prévues :

```text
HOSTNAME
TARGET_DISK
EFI_SIZE
FILESYSTEM
BOOTLOADER
DEFAULT_KERNEL
TPM2_ENABLED
LUKS_ENABLED
EFI_PARTITION_LABEL
SYSTEM_PARTITION_LABEL
MINIMUM_DISK_SIZE
SWAP_SIZE
HIBERNATION_ENABLED
```

Le comportement de l'installeur doit venir de la configuration, pas de valeurs dispersées dans les scripts.

Les arguments CLI doivent pouvoir surcharger les valeurs de configuration.

Un problème déjà identifié concernait l'écrasement des options CLI par le chargement de la configuration.

La solution retenue utilise notamment :

```text
CLI_DRY_RUN
CLI_VERBOSE
```

Ordre attendu :

1. lire les arguments CLI ;
2. charger la configuration ;
3. appliquer les surcharges CLI.

---

## 9. Modes de fonctionnement existants ou prévus

### Inspection

```bash
sudo ./install.sh --inspect
```

Doit afficher :

- informations système ;
- firmware ;
- CPU ;
- mémoire ;
- mode de démarrage ;
- disque cible ;
- support Live ;
- disques candidats ;
- configuration ;
- état de préparation.

### Planification du stockage

```bash
sudo ./install.sh --plan-storage
```

Doit afficher :

- la table de partitions actuelle ;
- la disposition future ;
- les partitions prévues ;
- les commandes qui seraient exécutées ;
- les validations de capacité et de sécurité.

Cette commande ne doit jamais modifier le disque.

### Dry-run

```bash
sudo ./install.sh --dry-run
```

Le dry-run doit être pris en charge dans toutes les étapes concernées.

### Verbose

```bash
sudo ./install.sh --verbose
```

Permet d'afficher davantage d'informations de diagnostic.

### Partitionnement réel futur

```bash
sudo ./install.sh --partition
```

Cette commande devra exécuter le partitionnement réel uniquement après toutes les validations et une confirmation destructive explicite.

---

## 10. Validation de l'environnement

L'installeur doit vérifier :

- qu'il est exécuté depuis l'environnement Live officiel d'Arch Linux ;
- que la machine a démarré en mode UEFI ;
- que le disque cible existe ;
- que la cible est un disque complet et non une partition ;
- que le support Live n'est jamais choisi ;
- que les périphériques amovibles sont refusés ;
- que le disque a une capacité suffisante ;
- que les partitions montées sont détectées ;
- que les dépendances nécessaires sont disponibles ;
- que le réseau fonctionne lorsque l'étape en a besoin.

### Validation réseau

Ordre de repli retenu :

1. `curl`
2. `wget`
3. `ping`

### Cas d'un disque monté

- installation réelle : erreur fatale ;
- dry-run ou planification : avertissement seulement.

---

## 11. Isolation de l'inspection matérielle

Modules prévus :

```text
lib/system.sh
lib/disk.sh
```

Seuls ces modules doivent inspecter directement le matériel.

Les autres modules ne doivent pas appeler directement des commandes comme :

```bash
lsblk
```

Ils doivent utiliser l'API fournie par les modules d'inspection.

---

## 12. Planification du partitionnement

Module prévu :

```text
lib/partition.sh
```

Fonctions déjà définies conceptuellement :

```text
size_to_mib
size_to_bytes
get_partition_path
get_efi_partition_path
get_system_partition_path
get_efi_end_mib
validate_partition_dependencies
validate_target_disk_capacity
validate_efi_partition_size
validate_partition_target_safety
validate_storage_plan
show_existing_partition_layout
show_planned_partition_layout
show_partition_commands
show_storage_plan
```

Le plan actuel produit notamment :

- une partition EFI commençant à 1 MiB ;
- une partition système commençant après l'EFI ;
- une table GPT ;
- des commandes `wipefs`, `sgdisk`, `partprobe` et `udevadm` prévues.

Un test en dry-run et mode verbose a déjà permis de confirmer le bon fonctionnement de la planification.

---

## 13. Architecture des bibliothèques

Modules principaux prévus :

```text
lib/
├── bootloader.sh
├── btrfs.sh
├── chroot.sh
├── commands.sh
├── common.sh
├── config.sh
├── disk.sh
├── hooks.sh
├── logging.sh
├── luks.sh
├── mount.sh
├── packages.sh
├── pacstrap.sh
├── partition.sh
├── progress.sh
├── rollback.sh
├── services.sh
├── snapshots.sh
├── state.sh
├── system.sh
├── task.sh
├── ui.sh
├── users.sh
├── validation.sh
└── verify.sh
```

Tous ces fichiers ne doivent pas être créés vides dès le départ.

### Responsabilités importantes

#### `logging.sh`

Fonctions prévues :

```text
info
warn
success
error
fatal
```

#### `commands.sh`

Fonctions prévues :

```text
run_command
run_critical
```

#### `config.sh`

Fonction principale :

```text
load_config
```

#### `validation.sh`

Regroupe les validations communes.

#### `ui.sh`

Regroupe les interactions utilisateur.

#### `task.sh`

Contient le moteur d'orchestration des tâches.

#### `state.sh`

Gère l'état d'exécution et la reprise.

#### `progress.sh`

Affiche l'avancement.

---

## 14. Architecture par tâches

Organisation prévue :

```text
tasks/
├── 00_environment.sh
├── 05_disk_selection.sh
├── 10_storage.sh
├── 20_encryption.sh
├── 30_filesystem.sh
├── 40_mount.sh
├── 50_base_system.sh
├── 60_configuration.sh
├── 70_packages.sh
├── 80_users.sh
├── 90_bootloader.sh
├── 95_security.sh
├── 98_cleanup.sh
└── 99_finish.sh
```

### API commune

Chaque tâche doit exposer une API cohérente :

```text
task_<name>_name
task_<name>_validate
task_<name>_execute
task_<name>_verify
task_<name>_cleanup
task_<name>_rollback
```

### Règles

- une tâche ne doit jamais appeler `exit` ;
- elle retourne un code d'erreur ;
- l'orchestrateur décide de poursuivre, nettoyer ou annuler ;
- les tâches doivent rester petites ;
- les tâches doivent être vérifiables indépendamment ;
- les commandes destructives doivent toujours passer par les helpers communs.

---

## 15. Moteur de tâches

Le moteur doit gérer :

- la découverte ordonnée des tâches ;
- l'enregistrement des tâches ;
- la validation ;
- l'exécution ;
- la vérification ;
- le nettoyage ;
- le rollback ;
- la progression ;
- le chronométrage ;
- les journaux ;
- le dry-run ;
- les interruptions `SIGINT` et `SIGTERM` ;
- l'état global ;
- la reprise contrôlée lorsque cela est possible.

Séquence type :

```text
validate
  ↓
execute
  ↓
verify
  ↓
cleanup
```

En cas d'échec :

```text
failure
  ↓
cleanup
  ↓
rollback
  ↓
controlled stop
```

---

## 16. Journalisation

Les journaux doivent être enregistrés dans :

```text
logs/
```

Exemple :

```text
logs/2026-07-18-08-31-42-install.log
```

Chaque commande critique doit enregistrer :

- l'heure ;
- la commande ;
- sa durée ;
- son code de retour ;
- le contexte ;
- les erreurs éventuelles.

Les journaux doivent permettre de retrouver rapidement l'étape fautive.

---

## 17. Gestion des erreurs et rollback

Le projet doit éviter les arrêts désordonnés.

Principes :

- nettoyer les montages temporaires ;
- fermer les mappings LUKS ouverts par l'installeur ;
- ne jamais prétendre restaurer les anciennes données après un repartitionnement ;
- ne jamais masquer une erreur ;
- effectuer uniquement des rollbacks techniquement sûrs ;
- signaler clairement les opérations irréversibles.

Le rollback n'est pas synonyme de récupération des données détruites.

---

## 18. Vérifications systématiques

Chaque tâche doit prouver qu'elle a réussi.

### Stockage

Vérifier :

- table GPT ;
- nombre de partitions ;
- types GPT ;
- tailles ;
- alignement ;
- présence des périphériques ;
- labels ;
- UUID si applicable.

### LUKS2

Vérifier :

- format LUKS2 ;
- UUID ;
- mapping ouvert ;
- configuration TPM2 ;
- phrase de récupération disponible.

### Btrfs

Vérifier :

- type de système de fichiers ;
- label ;
- sous-volumes ;
- options de montage ;
- compression ;
- snapshots.

### Boot

Vérifier :

- présence de Limine ;
- configuration générée ;
- fichiers du noyau ;
- initramfs ;
- entrées de démarrage.

### Desktop

Vérifier :

- Niri installé ;
- Dank installé ;
- session disponible ;
- services utilisateur nécessaires ;
- configuration copiée ;
- aucun conflit évident avec l'environnement.

---

## 19. Barre de progression

Exemple prévu :

```text
[01/13] Environment       ✔
[02/13] Disk selection    ✔
[03/13] Storage           …
[04/13] Encryption
```

Une barre de progression peut aussi être affichée, mais elle ne doit jamais masquer les informations utiles des logs.

---

## 20. Tests

Organisation prévue :

```text
tests/
├── integration/
├── unit/
└── vm/
```

### Vérifications minimales

```bash
bash -n install.sh
bash -n lib/*.sh
bash -n tasks/*.sh
shellcheck install.sh lib/*.sh tasks/*.sh tests/**/*.sh
```

### Règles de sécurité

Les tests ne doivent jamais cibler un disque physique.

Ils doivent utiliser :

- mocks ;
- capture de commandes ;
- périphériques loop dans un environnement isolé ;
- machines virtuelles pour les tests complets.

---

## 21. Stratégie de développement

La stratégie retenue consiste à développer une fonctionnalité complète avant de passer à la suivante.

Chaque fonctionnalité doit inclure :

- sa documentation ;
- sa configuration ;
- ses validations ;
- son implémentation ;
- ses vérifications ;
- ses tests.

Il faut éviter de créer toute l'architecture sous forme de fichiers vides.

---

## 22. Rôle de Codex

Codex est installé dans VS Code et travaille directement dans le dépôt ouvert.

### Codex peut gérer

- inventaire du dépôt ;
- analyse des fichiers ;
- implémentation ;
- refactoring ;
- création et modification des fichiers ;
- exécution de `bash -n` ;
- exécution de ShellCheck ;
- exécution des tests ;
- synthèse des fichiers modifiés.

### ChatGPT reste utile pour

- architecture ;
- choix techniques ;
- arbitrages ;
- rédaction des spécifications ;
- revues de conception ;
- analyse des risques ;
- planification des étapes.

---

## 23. AGENTS.md

Un fichier `AGENTS.md` doit être présent à la racine du dépôt.

Il doit préciser :

- le but du projet ;
- l'environnement cible ;
- les conventions Bash ;
- les règles de sécurité ;
- l'API des tâches ;
- le comportement du dry-run ;
- les règles de test ;
- les règles Git ;
- l'interdiction des commandes destructives pendant le développement ;
- l'obligation de ne pas créer de commit sans demande explicite ;
- l'obligation de résumer les changements et résultats des tests.

---

## 24. Workflow avec Codex

Cycle recommandé :

```text
Analyse
  ↓
Inventaire
  ↓
Plan
  ↓
Implémentation d'une phase
  ↓
Tests
  ↓
Revue Git
  ↓
Test manuel en dry-run
  ↓
Commit
```

### Première analyse

Codex doit repérer :

- fichiers présents ;
- fichiers vides ;
- fichiers factices ;
- fichiers absents mais documentés ;
- fonctions appelées mais non définies ;
- modules chargés par `install.sh` ;
- tests existants ;
- incohérences entre `config/`, `lib/`, `tasks/`, `docs/` et `install.sh`.

### Règles de modification

- ne pas supprimer une fonctionnalité existante sans justification ;
- ne pas réécrire des fichiers sans rapport ;
- ne pas lancer de commande destructive ;
- ne pas créer de commit sans demande ;
- conserver `--inspect`, `--plan-storage`, `--dry-run`, `--verbose` et `--config`.

---

## 25. Ordre de réalisation retenu

### Phase 1 — Socle d'exécution

Créer ou compléter :

```text
lib/task.sh
lib/state.sh
lib/progress.sh
tasks/00_environment.sh
tests/unit/test_task_engine.sh
docs/architecture.md
```

Objectifs :

- registre ordonné ;
- `validate → execute → verify` ;
- cleanup ;
- rollback ;
- chronométrage ;
- progression ;
- dry-run ;
- logs ;
- gestion des signaux ;
- tests.

### Phase 2 — Stockage réel

Implémenter :

```text
tasks/10_storage.sh
```

Fonctions attendues :

- validations strictes ;
- confirmation destructive avec le chemin complet du disque ;
- `wipefs` ;
- `sgdisk --zap-all` ;
- création GPT ;
- création EFI ;
- création système ;
- `partprobe` ;
- `udevadm settle` ;
- attente de l'apparition des partitions ;
- vérification complète ;
- tests par mocks.

### Phase 3 — Chiffrement et Btrfs

Implémenter :

- LUKS2 ;
- phrase de récupération ;
- TPM2 ;
- Btrfs ;
- sous-volumes ;
- options de montage ;
- zram ;
- snapper.

### Phase 4 — Installation Arch

Implémenter :

- `pacstrap` ;
- génération de `fstab` ;
- configuration `chroot` ;
- locale ;
- clavier suisse français sans touches mortes ;
- fuseau horaire ;
- hostname ;
- réseau ;
- utilisateurs ;
- sudo.

### Phase 5 — Boot et sécurité

Implémenter :

- Limine ;
- noyau principal ;
- noyau LTS prioritaire ou disponible en secours selon la configuration retenue ;
- initramfs ;
- TPM2 ;
- `fprintd` ;
- `fwupd` ;
- préparation Secure Boot ;
- récupération.

### Phase 6 — Desktop

Implémenter :

- Niri ;
- Dank ;
- Fish ;
- terminal choisi ;
- outils de fichiers ;
- applications principales ;
- services utilisateur ;
- dotfiles séparés via Stow ;
- intégration Framework.

### Phase 7 — Qualité finale

Implémenter :

- GitHub Actions ;
- ShellCheck ;
- tests unitaires ;
- tests d'intégration ;
- tests VM ;
- documentation finale ;
- procédure de récupération ;
- validation complète sur Framework Laptop.

---

# Objectif précis à atteindre

L'objectif final est de disposer d'un dépôt Git capable d'installer automatiquement, depuis l'ISO officielle d'Arch Linux, un système complet et reproductible sur un Framework Laptop 13.

Le résultat attendu doit inclure :

1. une inspection fiable du matériel et de l'environnement Live ;
2. une configuration centralisée et surchargeable par la ligne de commande ;
3. un moteur de tâches robuste avec logs, état, progression, vérification, cleanup et rollback ;
4. un partitionnement GPT sécurisé ;
5. une partition EFI de 1 Gio ;
6. un système chiffré en LUKS2 ;
7. un déverrouillage TPM2 avec phrase de récupération ;
8. un système Btrfs avec `@`, `@home`, `@snapshots`, `@cache` et `@log` ;
9. la compression `zstd` ;
10. `zram` sans swapfile ;
11. Snapper pour les snapshots ;
12. l'installation complète d'Arch Linux ;
13. Limine comme bootloader ;
14. un noyau principal avec une stratégie LTS de secours ou prioritaire selon la configuration finale ;
15. la prise en charge de `fwupd` et `fprintd` ;
16. un bureau Wayland basé sur **Niri et Dank** ;
17. Fish et les outils utilisateur retenus ;
18. une configuration de clavier suisse français sans touches mortes ;
19. une architecture séparant clairement l'installeur des dotfiles ;
20. une suite de tests empêchant toute commande destructive sur un disque physique ;
21. une documentation suffisante pour que Codex ou un autre contributeur puisse poursuivre le projet sans perdre les décisions prises ;
22. une installation complète validée en dry-run, en machine virtuelle, puis sur le Framework Laptop réel.

Le projet sera considéré comme abouti lorsqu'une installation complète pourra être lancée de manière contrôlée, vérifiée et reproductible, sans étape manuelle non documentée, tout en conservant une méthode de récupération claire en cas de problème.

Library
/
Linux
/
ARCH_FRAMEWORK_INSTALLER_RESUME_CORRIGE.md
# Arch Framework Installer — Résumé complet du projet

## 1. Vision générale

Le projet consiste à créer un installeur Arch Linux :

- reproductible ;
- modulaire ;
- maintenable ;
- documenté ;
- testable ;
- sécurisé ;
- conçu en priorité pour un Framework Laptop 13 avec processeur Intel Core Ultra 5 ;
- suffisamment générique pour pouvoir être adapté à d'autres machines plus tard.

L'objectif n'est pas de créer une distribution Linux personnelle, mais un installeur Arch Linux propre, transparent et réutilisable.

L'installeur est prévu pour être exécuté depuis l'image ISO officielle d'Arch Linux, démarrée en mode UEFI.

---

## 2. Environnement cible

### Matériel principal

- Framework Laptop 13
- Intel Core Ultra 5 125H
- 32 Go de RAM
- SSD NVMe
- lecteur d'empreintes digitales Framework
- prise en charge du firmware Framework via `fwupd`

### Environnement graphique retenu

Le projet utilise :

- **Niri** comme compositeur Wayland ;
- **Dank** comme couche d'environnement, interface et intégration utilisateur ;
- un environnement moderne, fluide et stable ;
- une configuration utilisable sans dépendre exclusivement du tiling strict.

Hyprland ne fait pas partie de l'objectif actuel du projet.

### Logiciels et usages prévus

Le système doit notamment pouvoir accueillir :

- VS Code ou VSCodium ;
- Cursor ;
- KiCad ;
- Kitty ou Ghostty ;
- Fish ;
- Dolphin ;
- Yazi ;
- LibreWolf ;
- Microsoft Edge ;
- outils de développement ;
- outils Framework ;
- synchronisation OneDrive temporaire ;
- migration future vers un NAS.

---

## 3. Principes du projet

Le projet doit respecter les principes suivants :

- configuration centralisée ;
- aucune valeur importante codée en dur ;
- support du dry-run sur toutes les opérations pertinentes ;
- validations strictes avant les actions destructives ;
- vérifications après chaque étape ;
- journalisation détaillée ;
- architecture modulaire ;
- idempotence autant que possible ;
- documentation synchronisée avec le comportement réel ;
- tests automatisés ;
- reprise propre après interruption ;
- rollback lorsqu'il est techniquement sûr ;
- aucune commande destructive exécutée pendant les tests ;
- séparation entre l'installeur et les dotfiles.

---

## 4. Préférence de travail importante

Lorsqu'un fichier doit être créé ou modifié :

**Toujours fournir le fichier complet. Ne jamais fournir un patch ou un diff.**

Cette règle s'applique aux échanges avec ChatGPT comme aux instructions données à Codex lorsque cela est pertinent.

---

## 5. Structure générale du dépôt

Nom du projet :

```text
arch-framework-installer
```

Structure générale retenue :

```text
arch-framework-installer/
├── .github/
│   └── workflows/
├── assets/
├── cache/
├── config/
├── docs/
├── hooks/
│   ├── post-install/
│   ├── post-task/
│   ├── pre-install/
│   └── pre-task/
├── lib/
├── logs/
├── overlays/
│   ├── etc/
│   ├── home/
│   └── usr/
├── packages/
├── services/
├── state/
├── tasks/
├── templates/
├── tests/
│   ├── integration/
│   ├── unit/
│   └── vm/
├── .gitignore
├── AGENTS.md
├── install.sh
├── LICENSE
├── PROJECT.md
└── README.md
```

Il ne faut pas créer des dizaines de fichiers vides uniquement pour remplir cette structure.

Les fichiers doivent être ajoutés au moment où leur rôle devient réel et nécessaire.

---

## 6. Documentation

Documents principaux :

```text
docs/
├── architecture.md
├── boot.md
├── desktop.md
├── development.md
├── packages.md
├── recovery.md
├── security.md
├── storage.md
├── testing.md
└── update.md
```

### Rôle des documents

- `architecture.md` : architecture générale et moteur de tâches ;
- `storage.md` : partitionnement, LUKS2, Btrfs, sous-volumes et montages ;
- `security.md` : TPM2, phrase de récupération, empreinte et sécurité ;
- `boot.md` : Limine, initramfs, noyaux et démarrage ;
- `desktop.md` : Niri, Dank et environnement utilisateur ;
- `packages.md` : organisation des listes de paquets ;
- `recovery.md` : récupération, dépannage et restauration ;
- `update.md` : stratégie de mise à jour ;
- `development.md` : conventions de contribution ;
- `testing.md` : tests unitaires, intégration et machines virtuelles.

`PROJECT.md` doit rester court et présenter l'intention générale du projet.

---

## 7. Architecture de stockage

Architecture retenue :

```text
UEFI
  ↓
LUKS2
  ↓
Btrfs
```

### Partition EFI

- format FAT32 ;
- taille de 1 Gio ;
- utilisée par Limine ;
- partition GPT dédiée.

### Partition système

- partition occupant le reste du disque ;
- chiffrement LUKS2 ;
- Btrfs à l'intérieur du conteneur chiffré.

### Sous-volumes Btrfs

```text
@
@home
@snapshots
@cache
@log
```

### Options principales

- compression `zstd` ;
- snapshots avec `snapper` ;
- pas de swapfile ;
- swap assuré par `zram`.

### Déverrouillage

- prise en charge de TPM2 ;
- phrase de récupération toujours disponible ;
- le TPM2 ne doit jamais être l'unique moyen de récupération.

---

## 8. Configuration centralisée

Fichier principal :

```text
config/system.conf
```

Variables importantes déjà prévues :

```text
HOSTNAME
TARGET_DISK
EFI_SIZE
FILESYSTEM
BOOTLOADER
DEFAULT_KERNEL
TPM2_ENABLED
LUKS_ENABLED
EFI_PARTITION_LABEL
SYSTEM_PARTITION_LABEL
MINIMUM_DISK_SIZE
SWAP_SIZE
HIBERNATION_ENABLED
```

Le comportement de l'installeur doit venir de la configuration, pas de valeurs dispersées dans les scripts.

Les arguments CLI doivent pouvoir surcharger les valeurs de configuration.

Un problème déjà identifié concernait l'écrasement des options CLI par le chargement de la configuration.

La solution retenue utilise notamment :

```text
CLI_DRY_RUN
CLI_VERBOSE
```

Ordre attendu :

1. lire les arguments CLI ;
2. charger la configuration ;
3. appliquer les surcharges CLI.

---

## 9. Modes de fonctionnement existants ou prévus

### Inspection

```bash
sudo ./install.sh --inspect
```

Doit afficher :

- informations système ;
- firmware ;
- CPU ;
- mémoire ;
- mode de démarrage ;
- disque cible ;
- support Live ;
- disques candidats ;
- configuration ;
- état de préparation.

### Planification du stockage

```bash
sudo ./install.sh --plan-storage
```

Doit afficher :

- la table de partitions actuelle ;
- la disposition future ;
- les partitions prévues ;
- les commandes qui seraient exécutées ;
- les validations de capacité et de sécurité.

Cette commande ne doit jamais modifier le disque.

### Dry-run

```bash
sudo ./install.sh --dry-run
```

Le dry-run doit être pris en charge dans toutes les étapes concernées.

### Verbose

```bash
sudo ./install.sh --verbose
```

Permet d'afficher davantage d'informations de diagnostic.

### Partitionnement réel futur

```bash
sudo ./install.sh --partition
```

Cette commande devra exécuter le partitionnement réel uniquement après toutes les validations et une confirmation destructive explicite.

---

## 10. Validation de l'environnement

L'installeur doit vérifier :

- qu'il est exécuté depuis l'environnement Live officiel d'Arch Linux ;
- que la machine a démarré en mode UEFI ;
- que le disque cible existe ;
- que la cible est un disque complet et non une partition ;
- que le support Live n'est jamais choisi ;
- que les périphériques amovibles sont refusés ;
- que le disque a une capacité suffisante ;
- que les partitions montées sont détectées ;
- que les dépendances nécessaires sont disponibles ;
- que le réseau fonctionne lorsque l'étape en a besoin.

### Validation réseau

Ordre de repli retenu :

1. `curl`
2. `wget`
3. `ping`

### Cas d'un disque monté

- installation réelle : erreur fatale ;
- dry-run ou planification : avertissement seulement.

---

## 11. Isolation de l'inspection matérielle

Modules prévus :

```text
lib/system.sh
lib/disk.sh
```

Seuls ces modules doivent inspecter directement le matériel.

Les autres modules ne doivent pas appeler directement des commandes comme :

```bash
lsblk
```

Ils doivent utiliser l'API fournie par les modules d'inspection.

---

## 12. Planification du partitionnement

Module prévu :

```text
lib/partition.sh
```

Fonctions déjà définies conceptuellement :

```text
size_to_mib
size_to_bytes
get_partition_path
get_efi_partition_path
get_system_partition_path
get_efi_end_mib
validate_partition_dependencies
validate_target_disk_capacity
validate_efi_partition_size
validate_partition_target_safety
validate_storage_plan
show_existing_partition_layout
show_planned_partition_layout
show_partition_commands
show_storage_plan
```

Le plan actuel produit notamment :

- une partition EFI commençant à 1 MiB ;
- une partition système commençant après l'EFI ;
- une table GPT ;
- des commandes `wipefs`, `sgdisk`, `partprobe` et `udevadm` prévues.

Un test en dry-run et mode verbose a déjà permis de confirmer le bon fonctionnement de la planification.

---

## 13. Architecture des bibliothèques

Modules principaux prévus :

```text
lib/
├── bootloader.sh
├── btrfs.sh
├── chroot.sh
├── commands.sh
├── common.sh
├── config.sh
├── disk.sh
├── hooks.sh
├── logging.sh
├── luks.sh
├── mount.sh
├── packages.sh
├── pacstrap.sh
├── partition.sh
├── progress.sh
├── rollback.sh
├── services.sh
├── snapshots.sh
├── state.sh
├── system.sh
├── task.sh
├── ui.sh
├── users.sh
├── validation.sh
└── verify.sh
```

Tous ces fichiers ne doivent pas être créés vides dès le départ.

### Responsabilités importantes

#### `logging.sh`

Fonctions prévues :

```text
info
warn
success
error
fatal
```

#### `commands.sh`

Fonctions prévues :

```text
run_command
run_critical
```

#### `config.sh`

Fonction principale :

```text
load_config
```

#### `validation.sh`

Regroupe les validations communes.

#### `ui.sh`

Regroupe les interactions utilisateur.

#### `task.sh`

Contient le moteur d'orchestration des tâches.

#### `state.sh`

Gère l'état d'exécution et la reprise.

#### `progress.sh`

Affiche l'avancement.

---

## 14. Architecture par tâches

Organisation prévue :

```text
tasks/
├── 00_environment.sh
├── 05_disk_selection.sh
├── 10_storage.sh
├── 20_encryption.sh
├── 30_filesystem.sh
├── 40_mount.sh
├── 50_base_system.sh
├── 60_configuration.sh
├── 70_packages.sh
├── 80_users.sh
├── 90_bootloader.sh
├── 95_security.sh
├── 98_cleanup.sh
└── 99_finish.sh
```

### API commune

Chaque tâche doit exposer une API cohérente :

```text
task_<name>_name
task_<name>_validate
task_<name>_execute
task_<name>_verify
task_<name>_cleanup
task_<name>_rollback
```

### Règles

- une tâche ne doit jamais appeler `exit` ;
- elle retourne un code d'erreur ;
- l'orchestrateur décide de poursuivre, nettoyer ou annuler ;
- les tâches doivent rester petites ;
- les tâches doivent être vérifiables indépendamment ;
- les commandes destructives doivent toujours passer par les helpers communs.

---

## 15. Moteur de tâches

Le moteur doit gérer :

- la découverte ordonnée des tâches ;
- l'enregistrement des tâches ;
- la validation ;
- l'exécution ;
- la vérification ;
- le nettoyage ;
- le rollback ;
- la progression ;
- le chronométrage ;
- les journaux ;
- le dry-run ;
- les interruptions `SIGINT` et `SIGTERM` ;
- l'état global ;
- la reprise contrôlée lorsque cela est possible.

Séquence type :

```text
validate
  ↓
execute
  ↓
verify
  ↓
cleanup
```

En cas d'échec :

```text
failure
  ↓
cleanup
  ↓
rollback
  ↓
controlled stop
```

---

## 16. Journalisation

Les journaux doivent être enregistrés dans :

```text
logs/
```

Exemple :

```text
logs/2026-07-18-08-31-42-install.log
```

Chaque commande critique doit enregistrer :

- l'heure ;
- la commande ;
- sa durée ;
- son code de retour ;
- le contexte ;
- les erreurs éventuelles.

Les journaux doivent permettre de retrouver rapidement l'étape fautive.

---

## 17. Gestion des erreurs et rollback

Le projet doit éviter les arrêts désordonnés.

Principes :

- nettoyer les montages temporaires ;
- fermer les mappings LUKS ouverts par l'installeur ;
- ne jamais prétendre restaurer les anciennes données après un repartitionnement ;
- ne jamais masquer une erreur ;
- effectuer uniquement des rollbacks techniquement sûrs ;
- signaler clairement les opérations irréversibles.

Le rollback n'est pas synonyme de récupération des données détruites.

---

## 18. Vérifications systématiques

Chaque tâche doit prouver qu'elle a réussi.

### Stockage

Vérifier :

- table GPT ;
- nombre de partitions ;
- types GPT ;
- tailles ;
- alignement ;
- présence des périphériques ;
- labels ;
- UUID si applicable.

### LUKS2

Vérifier :

- format LUKS2 ;
- UUID ;
- mapping ouvert ;
- configuration TPM2 ;
- phrase de récupération disponible.

### Btrfs

Vérifier :

- type de système de fichiers ;
- label ;
- sous-volumes ;
- options de montage ;
- compression ;
- snapshots.

### Boot

Vérifier :

- présence de Limine ;
- configuration générée ;
- fichiers du noyau ;
- initramfs ;
- entrées de démarrage.

### Desktop

Vérifier :

- Niri installé ;
- Dank installé ;
- session disponible ;
- services utilisateur nécessaires ;
- configuration copiée ;
- aucun conflit évident avec l'environnement.

---

## 19. Barre de progression

Exemple prévu :

```text
[01/13] Environment       ✔
[02/13] Disk selection    ✔
[03/13] Storage           …
[04/13] Encryption
```

Une barre de progression peut aussi être affichée, mais elle ne doit jamais masquer les informations utiles des logs.

---

## 20. Tests

Organisation prévue :

```text
tests/
├── integration/
├── unit/
└── vm/
```

### Vérifications minimales

```bash
bash -n install.sh
bash -n lib/*.sh
bash -n tasks/*.sh
shellcheck install.sh lib/*.sh tasks/*.sh tests/**/*.sh
```

### Règles de sécurité

Les tests ne doivent jamais cibler un disque physique.

Ils doivent utiliser :

- mocks ;
- capture de commandes ;
- périphériques loop dans un environnement isolé ;
- machines virtuelles pour les tests complets.

---

## 21. Stratégie de développement

La stratégie retenue consiste à développer une fonctionnalité complète avant de passer à la suivante.

Chaque fonctionnalité doit inclure :

- sa documentation ;
- sa configuration ;
- ses validations ;
- son implémentation ;
- ses vérifications ;
- ses tests.

Il faut éviter de créer toute l'architecture sous forme de fichiers vides.

---

## 22. Rôle de Codex

Codex est installé dans VS Code et travaille directement dans le dépôt ouvert.

### Codex peut gérer

- inventaire du dépôt ;
- analyse des fichiers ;
- implémentation ;
- refactoring ;
- création et modification des fichiers ;
- exécution de `bash -n` ;
- exécution de ShellCheck ;
- exécution des tests ;
- synthèse des fichiers modifiés.

### ChatGPT reste utile pour

- architecture ;
- choix techniques ;
- arbitrages ;
- rédaction des spécifications ;
- revues de conception ;
- analyse des risques ;
- planification des étapes.

---

## 23. AGENTS.md

Un fichier `AGENTS.md` doit être présent à la racine du dépôt.

Il doit préciser :

- le but du projet ;
- l'environnement cible ;
- les conventions Bash ;
- les règles de sécurité ;
- l'API des tâches ;
- le comportement du dry-run ;
- les règles de test ;
- les règles Git ;
- l'interdiction des commandes destructives pendant le développement ;
- l'obligation de ne pas créer de commit sans demande explicite ;
- l'obligation de résumer les changements et résultats des tests.

---

## 24. Workflow avec Codex

Cycle recommandé :

```text
Analyse
  ↓
Inventaire
  ↓
Plan
  ↓
Implémentation d'une phase
  ↓
Tests
  ↓
Revue Git
  ↓
Test manuel en dry-run
  ↓
Commit
```

### Première analyse

Codex doit repérer :

- fichiers présents ;
- fichiers vides ;
- fichiers factices ;
- fichiers absents mais documentés ;
- fonctions appelées mais non définies ;
- modules chargés par `install.sh` ;
- tests existants ;
- incohérences entre `config/`, `lib/`, `tasks/`, `docs/` et `install.sh`.

### Règles de modification

- ne pas supprimer une fonctionnalité existante sans justification ;
- ne pas réécrire des fichiers sans rapport ;
- ne pas lancer de commande destructive ;
- ne pas créer de commit sans demande ;
- conserver `--inspect`, `--plan-storage`, `--dry-run`, `--verbose` et `--config`.

---

## 25. Ordre de réalisation retenu

### Phase 1 — Socle d'exécution

Créer ou compléter :

```text
lib/task.sh
lib/state.sh
lib/progress.sh
tasks/00_environment.sh
tests/unit/test_task_engine.sh
docs/architecture.md
```

Objectifs :

- registre ordonné ;
- `validate → execute → verify` ;
- cleanup ;
- rollback ;
- chronométrage ;
- progression ;
- dry-run ;
- logs ;
- gestion des signaux ;
- tests.

### Phase 2 — Stockage réel

Implémenter :

```text
tasks/10_storage.sh
```

Fonctions attendues :

- validations strictes ;
- confirmation destructive avec le chemin complet du disque ;
- `wipefs` ;
- `sgdisk --zap-all` ;
- création GPT ;
- création EFI ;
- création système ;
- `partprobe` ;
- `udevadm settle` ;
- attente de l'apparition des partitions ;
- vérification complète ;
- tests par mocks.

### Phase 3 — Chiffrement et Btrfs

Implémenter :

- LUKS2 ;
- phrase de récupération ;
- TPM2 ;
- Btrfs ;
- sous-volumes ;
- options de montage ;
- zram ;
- snapper.

### Phase 4 — Installation Arch

Implémenter :

- `pacstrap` ;
- génération de `fstab` ;
- configuration `chroot` ;
- locale ;
- clavier suisse français sans touches mortes ;
- fuseau horaire ;
- hostname ;
- réseau ;
- utilisateurs ;
- sudo.

### Phase 5 — Boot et sécurité

Implémenter :

- Limine ;
- noyau principal ;
- noyau LTS prioritaire ou disponible en secours selon la configuration retenue ;
- initramfs ;
- TPM2 ;
- `fprintd` ;
- `fwupd` ;
- préparation Secure Boot ;
- récupération.

### Phase 6 — Desktop

Implémenter :

- Niri ;
- Dank ;
- Fish ;
- terminal choisi ;
- outils de fichiers ;
- applications principales ;
- services utilisateur ;
- dotfiles séparés via Stow ;
- intégration Framework.

### Phase 7 — Qualité finale

Implémenter :

- GitHub Actions ;
- ShellCheck ;
- tests unitaires ;
- tests d'intégration ;
- tests VM ;
- documentation finale ;
- procédure de récupération ;
- validation complète sur Framework Laptop.

---

# Objectif précis à atteindre

L'objectif final est de disposer d'un dépôt Git capable d'installer automatiquement, depuis l'ISO officielle d'Arch Linux, un système complet et reproductible sur un Framework Laptop 13.

Le résultat attendu doit inclure :

1. une inspection fiable du matériel et de l'environnement Live ;
2. une configuration centralisée et surchargeable par la ligne de commande ;
3. un moteur de tâches robuste avec logs, état, progression, vérification, cleanup et rollback ;
4. un partitionnement GPT sécurisé ;
5. une partition EFI de 1 Gio ;
6. un système chiffré en LUKS2 ;
7. un déverrouillage TPM2 avec phrase de récupération ;
8. un système Btrfs avec `@`, `@home`, `@snapshots`, `@cache` et `@log` ;
9. la compression `zstd` ;
10. `zram` sans swapfile ;
11. Snapper pour les snapshots ;
12. l'installation complète d'Arch Linux ;
13. Limine comme bootloader ;
14. un noyau principal avec une stratégie LTS de secours ou prioritaire selon la configuration finale ;
15. la prise en charge de `fwupd` et `fprintd` ;
16. un bureau Wayland basé sur **Niri et Dank** ;
17. Fish et les outils utilisateur retenus ;
18. une configuration de clavier suisse français sans touches mortes ;
19. une architecture séparant clairement l'installeur des dotfiles ;
20. une suite de tests empêchant toute commande destructive sur un disque physique ;
21. une documentation suffisante pour que Codex ou un autre contributeur puisse poursuivre le projet sans perdre les décisions prises ;
22. une installation complète validée en dry-run, en machine virtuelle, puis sur le Framework Laptop réel.

Le projet sera considéré comme abouti lorsqu'une installation complète pourra être lancée de manière contrôlée, vérifiée et reproductible, sans étape manuelle non documentée, tout en conservant une méthode de récupération claire en cas de problème.