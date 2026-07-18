# Récupération

Conserver la phrase LUKS2 hors de la machine et vérifier les sauvegardes avant
l'installation. En cas de remplacement de carte mère, ouvrir le volume avec la
phrase de récupération puis réenrôler TPM2. Les snapshots Snapper facilitent un
retour système mais ne remplacent jamais une sauvegarde.

L'enrôlement TPM2 est lié au PCR 7. Après un changement de firmware, de carte
mère ou d'état Secure Boot, démarrer avec la passphrase puis supprimer et
réenrôler uniquement le jeton TPM2. L'installateur ne supprime jamais ce jeton
automatiquement pendant un rollback.

Le partitionnement, `luksFormat` et `mkfs` sont irréversibles : aucun rollback
automatique ne prétend restaurer les anciennes données.

`nano` fait partie des paquets de base installés afin de pouvoir corriger la
configuration, les unités systemd et les fichiers de démarrage directement
depuis un TTY ou un environnement de récupération minimal.
