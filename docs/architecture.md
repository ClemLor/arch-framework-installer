# Architecture

## Objectif

Séparer les responsabilités de manière à ce que chaque décision soit vérifiable
sans matériel, et que le seul code capable de détruire des données soit
identifiable et concentré.

---

## Vue d'ensemble

```
arch-framework-installer/
├── arch_framework/          # l'installateur
│   ├── main.py              # point d'entrée, analyse des arguments
│   ├── lib/
│   │   ├── models/          # schéma de configuration (pydantic)
│   │   ├── disk/            # périphériques, sécurité, partitions, LUKS, Btrfs
│   │   ├── bootloader/      # Limine
│   │   ├── command.py       # LA porte pour toute commande système
│   │   ├── target.py        # écriture dans /mnt
│   │   ├── installer.py     # orchestration des étapes
│   │   ├── configure.py     # fichiers de configuration du système cible
│   │   ├── packages.py      # résolution des listes, pacstrap
│   │   ├── users.py         # comptes et sudo
│   │   ├── hardware.py      # micrologiciel, mémoire, environnement live
│   │   └── state.py         # reprise après échec
│   ├── tui/                 # menu guidé : registre + deux rendus
│   ├── scripts/             # flux complets (guided, credentials)
│   └── profiles/            # valeurs par défaut Framework
├── packages/                # listes de paquets, un fichier par groupe
├── tests/
│   └── golden/              # séquence de commandes de référence
├── docs/
├── tools/                   # sync-to-wsl.ps1
├── lib/ + install.sh        # implémentation Bash, conservée en repli
└── PROJECT.md
```

L'arborescence Bash (`lib/`, `install.sh`, `tasks/`, `templates/`) reste présente
sur `main` comme repli tant que le chemin Python n'a pas été validé sur du
matériel réel. Aucune fonctionnalité nouvelle n'y est ajoutée.

---

## La règle centrale

**Rien ne modifie le système en dehors de `lib/command.py` et
`lib/target.py`.**

C'est ce qui rend `--dry-run` fiable. Une commande écrite en direct, ou un
`Path.write_text` vers `/mnt`, contournerait le mode simulation et créerait des
fichiers en prétendant ne rien changer.

Trois opérations, volontairement distinctes :

| Opération | Modifie | En simulation |
| --- | --- | --- |
| `run` | oui | n'exécute pas |
| `capture` | non | **exécute quand même** |
| `derived` | non | renvoie un marqueur explicite |

`capture` s'exécute toujours parce que sa sortie est consommée comme une valeur :
un substitut silencieux corromprait toutes les décisions qui en découlent.

`derived` existe pour les valeurs qui n'existent qu'après une étape antérieure —
UUID, décalage de reprise. En simulation, le système de fichiers n'a pas été
créé : `blkid` ne renvoie rien, et `fstab`, `crypttab` et `limine.conf` seraient
rendus vides, donc invérifiables. Le marqueur `<UUID-of-…>` les garde lisibles et
visiblement factices.

---

## Séparation observation / intention

```
DiskInfo     ← ce que la machine présente
DiskConfig   ← ce que l'utilisateur demande
```

Les faits matériels ne sont jamais lus directement : ils passent par un
`DeviceSource`. `SystemSource` appelle `lsblk` et `findmnt` ; `FixtureSource` lit
un enregistrement de même forme.

C'est ce qui rend la couche de sécurité testable sans aucun disque, et le menu
utilisable hors de la machine cible.

Une installation réelle refuse de démarrer si la source est un enregistrement.

---

## Où se prend la décision de détruire

```
menu               → masque les disques inéligibles, avec le motif
guided.run         → confirmation explicite du nom du disque
partitioning.guard → refuse, juste avant wipefs
```

Les trois existent, mais **seule la troisième compte**. Une configuration peut
être écrite à la main, copiée d'une machine à l'autre, ou rejouée des mois plus
tard. La seule vérification qui vaille est celle prise contre le disque tel qu'il
est au moment d'écrire.

Voir `docs/security.md`.

---

## Configuration

Un document unique, décrit par des modèles pydantic, enregistré en JSON.

Les règles portant sur un seul champ sont sur le champ. Celles qui portent sur
plusieurs sont sur `InstallConfig` : l'hibernation exige `@swap`, TPM2 exige une
clé de secours. Celles qui dépendent du matériel observé sont des méthodes
explicites (`validate_capacity`, `validate_hibernation`), puisqu'elles ont besoin
d'un fait extérieur au document.

La sérialisation est déterministe : deux machines identiques produisent des
fichiers identiques, sans quoi l'enregistrement ne vaudrait rien comme artefact de
reproductibilité.

Les secrets n'y figurent jamais — fichier séparé, `--creds`.

---

## Menu

Les entrées sont des données. Un registre décrit chaque ligne : son libellé,
comment lire sa valeur courante, comment la modifier, si elle est obligatoire.

Deux rendus parcourent le même registre :

| Rendu | Quand |
| --- | --- |
| Textual | terminal interactif, `textual` disponible |
| Texte simple | sinon, et pour console série, SSH, lecteur d'écran |

`textual` n'est présent sur l'ISO que parce que `archinstall` en dépend : c'est
une garantie indirecte. Le rendu simple n'est donc pas un repli d'excuse.

Les modifications passent par `Draft`, qui applique le changement sur une copie,
revalide le document entier, et annule en cas de refus. Modifier champ par champ
contournerait les règles croisées ou laisserait un modèle invalide.

---

## Étapes d'installation

Onze étapes nommées, enregistrées à mesure, ignorées lors d'une reprise.

```
partition → encrypt → recovery_key → filesystem → mount → base_system
→ configure → users → bootloader → tpm2 → cleanup
```

Deux points d'ordre sont des propriétés de sécurité, vérifiées par des tests :

- `recovery_key` avant `tpm2` ;
- la vérification du disque **dans** `partition`, pas avant.

---

## Vérification

`tests/golden/install-commands.txt` contient la séquence exacte d'une
installation complète en simulation. Elle fixe les unités et l'ordre des
arguments, ce qu'aucun autre moyen ne permet sans matériel à détruire.

Voir `docs/testing.md`.

---

## Principes

- une responsabilité par fichier ;
- les commentaires expliquent *pourquoi*, jamais *quoi* ;
- toute opération est idempotente ou reprenable ;
- documentation en français, code et messages en anglais ;
- `stdout` ne contient que des données ; la journalisation va sur `stderr`.
