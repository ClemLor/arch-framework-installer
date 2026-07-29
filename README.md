# arch-framework-installer

Installation Arch Linux reproductible pour Framework Laptop : LUKS2, Btrfs avec
sous-volumes, Limine, déverrouillage TPM2.

Le système est considéré comme jetable. L'objectif est de reconstruire un
environnement de travail identique en lançant les scripts de ce dépôt, plutôt
que de réparer une installation cassée.

La philosophie du projet est décrite dans [PROJECT.md](PROJECT.md), la
documentation technique dans [docs/](docs/).

## État actuel

Le projet est en cours de construction. Seules l'inspection et la planification
du stockage sont implémentées ; aucune opération d'installation n'est encore
exécutée.

## Prérequis

- ISO officielle Arch Linux, démarrée en mode UEFI
- x86_64
- Droits root

Les scripts refusent de s'exécuter en dehors de cet environnement.

## Utilisation

```bash
sudo ./install.sh --inspect        # inspection du matériel et des disques
sudo ./install.sh --plan-storage   # plan de partitionnement, sans rien modifier
```

Options : `--dry-run`, `--verbose`, `--config FICHIER`, `--help`.

`--inspect` et `--plan-storage` ne modifient jamais le système.

## Configuration

`config/system.conf` est la source de vérité. Toute valeur ajoutée doit
également être déclarée dans `validate_config` (`lib/config.sh`).

## Vérification

```bash
shellcheck -x install.sh lib/*.sh
```

## Licence

Voir [LICENSE](LICENSE).
