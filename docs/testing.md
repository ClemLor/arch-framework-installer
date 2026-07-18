# Tests

Les tests unitaires sont écrits en Bash sans framework externe. Ils remplacent
les fonctions système par des mocks et ne manipulent jamais de périphérique
physique. `test_task_engine.sh` couvre le cycle et le rollback ;
`test_storage_task.sh` vérifie les barrières dry-run et confirmation.

```bash
find install.sh lib tasks tests -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
shellcheck install.sh lib/*.sh tasks/*.sh tests/unit/*.sh
bash tests/unit/test_task_engine.sh
bash tests/unit/test_storage_task.sh
bash tests/unit/test_commands.sh
bash tests/unit/test_uefi_detection.sh
```

Les tests d'intégration sur loop device exigent un environnement isolé dédié.
Le scénario complet doit d'abord être validé en VM UEFI avec TPM virtuel, puis
manuellement sur le Framework après sauvegarde vérifiée.

En dry-run, une commande prospective absente produit un avertissement afin que
le plan complet reste visible. La même absence est toujours bloquante en mode
réel. Aucune fonction de rollback mutatrice n'est appelée après un dry-run.
