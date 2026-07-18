# Récupération

Conserver la phrase LUKS2 hors de la machine et vérifier les sauvegardes avant
l'installation. En cas de remplacement de carte mère, ouvrir le volume avec la
phrase de récupération puis réenrôler TPM2. Les snapshots Snapper facilitent un
retour système mais ne remplacent jamais une sauvegarde.

Le partitionnement, `luksFormat` et `mkfs` sont irréversibles : aucun rollback
automatique ne prétend restaurer les anciennes données.
