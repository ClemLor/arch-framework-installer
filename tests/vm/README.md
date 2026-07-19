# Validation VM après installation

Ce contrôle est strictement en lecture seule. Il doit être lancé après le
premier redémarrage de la VM installée, depuis une session Niri ouverte.

Profil LUKS2 avec vTPM2 et zram :

```bash
sudo ./tests/vm/validate_installation.sh \
    --user reaper \
    --encryption enabled \
    --tpm2 enabled \
    --zram enabled
```

La matrice minimale à valider avant le matériel réel est :

1. LUKS2 + vTPM2 + zram ;
2. LUKS2 sans TPM2 + zram ;
3. stockage non chiffré sans TPM2 + zram.

Pour chaque profil, vérifier aussi les entrées Limine `linux-lts` et `linux`,
une déconnexion suivie du greeter DMS, puis un nouveau démarrage. Le script
échoue si UEFI, Btrfs, `/boot`, Limine, les services, le nœud de rendu DRM, la
configuration ou la session Niri/DMS, le profil de sécurité ou zram ne
correspondent pas aux options annoncées. L'absence de `/dev/dri/renderD*`
indique généralement que l'accélération 3D de la VM n'est pas exposée.

Le script ne partitionne et ne formate aucun périphérique. Les tests de stockage
réel restent réservés à une VM jetable ou à un loop device explicitement isolé.
