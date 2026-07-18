# Sécurité

La partition système utilise LUKS2. `cryptsetup luksFormat` demande une phrase
secrète interactivement et celle-ci reste la méthode de récupération. TPM2 peut
être enrôlé ensuite avec `systemd-cryptenroll`; il n'est jamais l'unique moyen
d'accès. Les secrets ne doivent pas apparaître dans les arguments ou journaux.

Le profil installe `fprintd`, `fwupd`, active la maintenance SSD et refuse toute
mutation hors ISO Arch, hors UEFI, en dry-run ou sans activation explicite.
