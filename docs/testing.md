# Tests

Les tests unitaires sont écrits en Bash sans framework externe. Ils remplacent
les fonctions système par des mocks et ne manipulent jamais de périphérique
physique. `test_task_engine.sh` couvre le cycle et le rollback ;
`test_storage_task.sh` vérifie les barrières dry-run et confirmation.
La CI découvre tous les fichiers `tests/unit/*.sh` afin qu'un nouveau test ne
puisse pas être oublié dans une liste maintenue manuellement.

```bash
find install.sh lib tasks tests -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
shellcheck install.sh lib/*.sh tasks/*.sh tests/unit/*.sh
bash tests/unit/test_task_engine.sh
bash tests/unit/test_state.sh
bash tests/unit/test_storage_task.sh
bash tests/unit/test_commands.sh
bash tests/unit/test_uefi_detection.sh
bash tests/unit/test_packages.sh
bash tests/unit/test_tpm_detection.sh
bash tests/unit/test_tpm_enrollment.sh
bash tests/unit/test_encryption_modes.sh
bash tests/unit/test_boot_modes.sh
bash tests/unit/test_desktop_session.sh
bash tests/unit/test_zram_configuration.sh
bash tests/unit/test_swap_configuration.sh
bash tests/unit/test_hibernation.sh
bash tests/unit/test_snapshots.sh
bash tests/unit/test_aur_setup.sh
bash tests/unit/test_config_values.sh
bash tests/unit/test_user_configuration.sh
bash tests/unit/test_services.sh
bash tests/unit/test_readiness.sh
bash tests/unit/test_vm_validator.sh
```

Le configurateur Python a sa propre suite, bibliothèque standard uniquement —
l'ISO ne fournit pas pytest, et une suite qui ne peut pas y tourner cesse d'être
exécutée :

```bash
python3 -m unittest discover -s tests/python
```

Les tests d'intégration sur loop device exigent un environnement isolé dédié.
Le scénario complet doit d'abord être validé en VM UEFI avec TPM virtuel, puis
manuellement sur le Framework après sauvegarde vérifiée.

Après le redémarrage de la VM, `tests/vm/validate_installation.sh` vérifie en
lecture seule le montage Btrfs, Limine, le profil LUKS2/TPM2, les paquets et
services, la présence d'un nœud de rendu DRM, la configuration et la session
Niri/DMS, puis la mémoire. Les profils attendus sont fournis
explicitement en arguments afin que le test ne valide pas simplement l'état
qu'il découvre.

Les programmes du système testé, notamment `niri`, ne sont pas des dépendances
du validateur. S'ils manquent, les contrôles des paquets et de la session
échouent, mais les autres diagnostics continuent afin de produire un rapport
complet.

## Mémoire et hibernation

Le validateur exige désormais `--hibernation enabled|disabled` :

```bash
sudo ./tests/vm/validate_installation.sh \
  --user framework --encryption enabled --tpm2 enabled \
  --zram enabled --hibernation enabled
```

Un périphérique zram actif ne prouve pas qu'il est utilisé. Le validateur
contrôle donc séparément :

| Contrôle | Ce qu'il attrape |
| --- | --- |
| `vm.swappiness >= 100` | zram présent mais laissé inutilisé — le symptôme observé |
| `vm.page-cluster == 0` | lecture anticipée inutile sur zram |
| priorité zram > swapfile | pagination courante envoyée sur le disque |
| `resume=` **et** `resume_offset=` | reprise silencieusement remplacée par un démarrage à froid |
| `resume_offset` égal à l'offset réel | swapfile recréé, décalage périmé |
| attribut `C` sur le swapfile | copy-on-write, qui corrompt le swapfile |

## Snapshots

Une configuration snapper présente ne signifie pas qu'un retour arrière est
possible. Le validateur contrôle donc :

| Contrôle | Ce qu'il attrape |
| --- | --- |
| `/.snapshots` est un point de montage | racine contenant ses propres snapshots |
| timers snapper activés | aucun snapshot horaire |
| `/etc/snap-pac.ini` présent | transactions importantes non signalées |
| hooks pacman `snap-pac` installés | fichier de configuration présent mais paquet absent |
| `snapper --config root list` fonctionne | configuration illisible par snapper |

Le contrôle des hooks est distinct de celui du fichier de configuration : le
second peut exister sans le paquet, et c'est le hook qui s'exécute réellement.

Le contrôle du décalage recalcule la valeur avec
`btrfs inspect-internal map-swapfile` et la compare à `/proc/cmdline`, plutôt que
de se contenter de vérifier qu'un paramètre existe.

Le test de readiness reproduit la syntaxe `subvol=/@` émise par `genfstab` et
vérifie aussi le profil historique `subvol=@`. Les autres sous-volumes ne sont
jamais acceptés comme racine.

En dry-run, une commande prospective absente produit un avertissement afin que
le plan complet reste visible. La même absence est toujours bloquante en mode
réel. Aucune fonction de rollback mutatrice n'est appelée après un dry-run.
