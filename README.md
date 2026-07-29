# Arch Framework Installer

Installateur Arch Linux reproductible pour Framework Laptop 13, avec GPT,
LUKS2/TPM2, Btrfs, Limine et un bureau Niri + Dank Material Shell.

## Utilisation depuis l'ISO Arch UEFI

### Menu guidé

```bash
python3 -m configurator          # interface plein écran, puis Save ou Install
python3 -m configurator --text   # invites simples, scriptables
python3 -m configurator --show   # état courant et problèmes, sans rien modifier
python3 -m configurator --dry-run  # Install suit la simulation des 15 tâches à l'écran
```

Le menu écrit `config/generated.conf`, que `install.sh` charge après
`config/system.conf`. Les options incompatibles sont affichées verrouillées avec
leur raison — activer l'hibernation verrouille par exemple « pas de swapfile » et
toute taille inférieure à la mémoire installée.

Il n'installe rien lui-même : toute opération destructive reste dans `install.sh`.
Aucune dépendance Python en dehors de la bibliothèque standard.

### Directement

```bash
sudo ./install.sh --inspect
sudo ./install.sh --plan-storage --config config/system.conf
sudo ./install.sh --dry-run --verbose
```

### Après le premier démarrage

```bash
afi-aur-setup
```

Construit `paru`, puis installe les paquets AUR configurés (LibreWolf, Edge,
VS Code, Cursor). Séparé de l'installation parce qu'un PKGBUILD cassé ne doit pas
pouvoir faire échouer un système déjà amorçable. Réexécutable.

Une installation réelle exige aussi `ENABLE_REAL_INSTALLATION=true` dans une
configuration explicitement revue. Le disque complet doit ensuite être saisi
lors des confirmations destructives. Commencer par [la documentation de
l'architecture](docs/architecture.md), de la
[configuration](docs/configuration.md), du [stockage](docs/storage.md) et de la
[récupération](docs/recovery.md).

Les tests unitaires n'utilisent que des mocks :

```bash
for test_file in tests/unit/*.sh; do
    bash "${test_file}"
done
python3 -m unittest discover -s tests/python
```
