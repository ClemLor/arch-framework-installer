# arch-framework-installer

Installation Arch Linux reproductible pour Framework Laptop : LUKS2, Btrfs avec
sous-volumes, Limine, déverrouillage TPM2, hibernation.

Le système est considéré comme jetable. L'objectif est de reconstruire un
environnement de travail identique en rejouant une configuration enregistrée,
plutôt que de réparer une installation cassée.

La philosophie du projet est dans [PROJECT.md](PROJECT.md), la documentation
technique dans [docs/](docs/).

## État

Fonctionnel et testé hors matériel — 209 tests. **Aucun démarrage réel n'a encore
eu lieu**, ni en machine virtuelle ni sur du matériel. Voir
[docs/testing.md](docs/testing.md).

L'implémentation Bash de la branche `main` est conservée comme repli et n'évolue
plus.

## Prérequis

ISO officielle Arch Linux démarrée en mode UEFI, x86_64, droits root.

L'installation refuse de s'exécuter ailleurs.

## Utilisation

```bash
# menu guidé, comme archinstall
python -m arch_framework --tui

# inspection et plan, sans rien modifier
python -m arch_framework --inspect
python -m arch_framework --plan-storage

# répétition complète, aucune commande destructive
python -m arch_framework --install --dry-run --config framework-install.json

# installation sans menu, depuis une configuration enregistrée
python -m arch_framework --install --config framework-install.json --creds creds.json
```

Options : `--renderer plain|textual`, `--devices-from FIXTURE`, `--verbose`.

## Reproductibilité

Le menu enregistre les réponses dans un fichier JSON. Rejouer ce fichier
reconstruit la même machine — c'est la raison d'être du projet.

Les secrets ne s'y trouvent jamais ; ils vont dans un fichier séparé (`--creds`)
ou sont demandés à l'installation.

**À conserver hors de la machine** : la clé de secours LUKS sur papier, et la
configuration enregistrée. Voir [docs/recovery.md](docs/recovery.md).

## Développement

La machine de développement est Windows et n'a pas de Python ; les tests
s'exécutent dans WSL Arch, qui fournit l'interpréteur de l'ISO.

```powershell
.\tools\sync-to-wsl.ps1 -Setup   # première fois
.\tools\sync-to-wsl.ps1          # transfère et lance les tests
```

Voir [docs/development.md](docs/development.md).

## Licence

Voir [LICENSE](LICENSE).
