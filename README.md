# Arch Framework Installer

Installateur Arch Linux reproductible pour Framework Laptop 13, avec GPT,
LUKS2/TPM2, Btrfs, Limine et un bureau Niri + Dank Material Shell.

## Utilisation depuis l'ISO Arch UEFI

```bash
sudo ./install.sh --inspect
sudo ./install.sh --plan-storage --config config/system.conf
sudo ./install.sh --dry-run --verbose
```

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
```
