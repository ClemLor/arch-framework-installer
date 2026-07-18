# Développement

Respecter `AGENTS.md`, garder les tâches petites et retourner les erreurs sans
appeler `exit`. Toute mutation passe par les helpers communs et possède un
comportement dry-run. Une fonctionnalité comprend code, validation, vérification,
tests et documentation. Aucun commit n'est créé sans demande explicite.

Les dotfiles restent séparés de l'installateur. Dank et les applications AUR ou
propriétaires non disponibles dans les dépôts officiels ne doivent pas être
téléchargés via un pipeline distant non vérifié pendant l'installation.
