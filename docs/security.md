# Sécurité

La partition système utilise LUKS2. `cryptsetup luksFormat` demande une phrase
secrète interactivement et celle-ci reste la méthode de récupération. TPM2 peut
être enrôlé ensuite avec `systemd-cryptenroll`; il n'est jamais l'unique moyen
d'accès. Les secrets ne doivent pas apparaître dans les arguments ou journaux.

L'enrôlement est lié au PCR 7, qui représente notamment l'état Secure Boot. Il
est idempotent : un jeton `systemd-tpm2` déjà présent n'est pas dupliqué. Après
l'opération, l'installateur lit les métadonnées JSON LUKS2 avec `cryptsetup` et
les valide avec `jq`; il ne dépend pas de la sortie tabulaire destinée aux
humains. Un changement de firmware ou de politique Secure Boot peut empêcher
le déverrouillage TPM2, auquel cas la passphrase de récupération reste requise.

Le profil installe `fprintd`, `fwupd`, active la maintenance SSD et refuse toute
mutation hors ISO Arch, hors UEFI, en dry-run ou sans activation explicite.

Lorsque `TPM2_ENABLED=true`, `/dev/tpmrm0` ou `/dev/tpm0` doit être disponible.
Cette condition est vérifiée avant le partitionnement. Une VM sans vTPM doit
utiliser `TPM2_ENABLED=false`; elle conservera le déverrouillage par passphrase.

## Profil sans chiffrement

Le chiffrement peut être entièrement désactivé avec :

```bash
LUKS_ENABLED="false"
TPM2_ENABLED="false"
```

Btrfs est alors créé directement sur la partition système et aucune passphrase
n'est demandée. Un mode LUKS « TPM uniquement » sans phrase de récupération
n'est volontairement pas proposé.
