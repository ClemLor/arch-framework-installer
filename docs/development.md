# Développement

## La contrainte principale

La machine de développement est Windows. La cible est l'ISO Arch Linux.

Aucun test ne peut donc s'exécuter localement : il n'y a pas d'interpréteur
Python sous Windows dans cet environnement, et l'installateur exige un système
live démarré en UEFI avec les droits root.

La solution retenue est la distribution WSL `archlinux`, qui fournit exactement
l'interpréteur de l'ISO (Python 3.14). Cette distribution a `automount` et
`interop` désactivés dans `/etc/wsl.conf`, donc `/mnt/c` n'existe pas : les
sources sont transférées par l'entrée standard.

```powershell
.\tools\sync-to-wsl.ps1 -Setup   # première fois : crée le venv et installe les dépendances
.\tools\sync-to-wsl.ps1          # transfère les sources puis lance pytest
.\tools\sync-to-wsl.ps1 -NoTest  # transfère seulement
```

Deux détails que le script contourne :

- PowerShell ajoute une marque d'ordre des octets (BOM) en début de flux quand
  il redirige vers un exécutable natif ; les trois premiers octets sont donc
  retirés côté Linux.
- `/tmp` ne survit pas entre deux appels à `wsl.exe`, donc le transfert et
  l'extraction se font dans un seul appel.

---

## Développer sans matériel

Trois mécanismes rendent le projet exécutable hors de la machine cible.

### Périphériques enregistrés

La couche de sécurité ne lit jamais les disques directement : elle interroge un
`DeviceSource`. `SystemSource` appelle `lsblk --json` et `findmnt --json` ;
`FixtureSource` lit un fichier de la même forme.

```bash
python -m arch_framework --inspect --devices-from tests/fixtures/framework.json
```

Pour enregistrer un nouveau jeu de données sur une machine réelle :

```bash
lsblk --json --bytes --paths --output-all > disks.json
findmnt --json --list
```

Les contenus binaires (variables EFI) sont stockés sous `files_base64`.

### Rendu de secours

`textual` n'est présent sur l'ISO que parce que `archinstall` en dépend. C'est
une garantie indirecte : archinstall a déjà changé d'interface une fois. Le
rendu texte simple est donc un chemin de première classe, et pas un repli
d'excuse — il est aussi le seul utilisable via une console série, par SSH ou
avec un lecteur d'écran.

```bash
python -m arch_framework --tui --renderer plain
python -m arch_framework --tui --renderer textual
```

### Mode simulation

```bash
python -m arch_framework --install --dry-run --config saved.json
```

Aucune commande destructive n'est exécutée. Les valeurs qui n'existent qu'après
une étape précédente — UUID, décalage de reprise — sont remplacées par des
marqueurs explicites (`<UUID-of-/dev/nvme0n1p2>`), afin que les fichiers générés
restent lisibles et visiblement factices.

---

## Le journal de référence

`tests/golden/install-commands.txt` contient la séquence exacte de commandes
d'une installation complète en mode simulation.

C'est le principal moyen de vérification hors matériel : il fixe l'ordre et les
unités des arguments de `sgdisk`, les options de `cryptsetup`, l'ordre de
création des sous-volumes et l'ordre de montage.

Toute modification des étapes produit un écart sur ce fichier. La procédure est :

1. lire le `diff` ;
2. ne mettre le fichier à jour que si l'écart est voulu.

Sa relecture a déjà mis au jour trois défauts réels : les listes de paquets qui
n'étaient pas lues, le shell par défaut absent des paquets, et un nom de fichier
de clé contenant un identifiant de processus.

---

## Conventions

### Rien ne modifie le système hors de `lib/command.py`

Toute commande passe par `run` ou `run_critical`. Toute écriture de fichier dans
la cible passe par `TargetSystem.write`. Écrire `/mnt/etc/fstab` est aussi
destructeur que `mkfs`, et `--dry-run` ne doit rien créer.

`capture` est réservé aux commandes en lecture seule et s'exécute **toujours**,
y compris en simulation, car sa sortie est consommée comme une valeur.

### Flux de sortie

- `stdout` : uniquement des données qu'un appelant peut capturer.
- `stderr` : journalisation, avertissements, contenu affiché en simulation.

C'est ce qui permet à `--plan-storage > plan.txt` de produire un document
exploitable.

### Secrets

Jamais en argument de commande — la liste des processus est lisible par tous les
utilisateurs. Toujours par l'entrée standard.

Jamais dans la configuration enregistrée : celle-ci doit rester lisible,
relisible et réutilisable. Les secrets vont dans un fichier séparé (`--creds`).

### Modèles

Une nouvelle option se déclare dans `arch_framework/lib/models/`. Les règles qui
portent sur plusieurs champs vont dans `InstallConfig` : l'hibernation exige
`@swap`, TPM2 exige une clé de secours.

Les modèles ne doivent importer aucun module spécifique à Linux, sinon ils
cessent d'être testables hors de la cible.

---

## Ajouter une entrée de menu

1. déclarer la clé dans `ENTRY_KEYS` (`arch_framework/tui/entries.py`) ;
2. ajouter le `MenuEntry` dans `build_registry`, dans le même ordre.

Une assertion vérifie que les deux correspondent : une entrée absente de
`ENTRY_KEYS` serait silencieusement considérée comme non répondue lors du
rechargement d'une configuration enregistrée.

Les deux rendus parcourent le même registre : une entrée ajoutée apparaît dans
les deux.

---

## Tests

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m pytest tests/test_installer.py -v
```

Le `conftest.py` réinitialise la source de périphériques et force le mode
simulation avant chaque test. Un test qui retomberait sur `SystemSource` ne
testerait rien sur un poste de développement, et quelque chose de dangereux sur
une ISO live.

L'installation réelle refuse par ailleurs de démarrer si la source de
périphériques est un enregistrement.
