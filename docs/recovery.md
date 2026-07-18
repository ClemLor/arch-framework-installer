# Récupération

Conserver la phrase LUKS2 hors de la machine et vérifier les sauvegardes avant
l'installation. En cas de remplacement de carte mère, ouvrir le volume avec la
phrase de récupération puis réenrôler TPM2. Les snapshots Snapper facilitent un
retour système mais ne remplacent jamais une sauvegarde.

Le partitionnement, `luksFormat` et `mkfs` sont irréversibles : aucun rollback
automatique ne prétend restaurer les anciennes données.

`nano` fait partie des paquets de base installés afin de pouvoir corriger la
configuration, les unités systemd et les fichiers de démarrage directement
depuis un TTY ou un environnement de récupération minimal.
