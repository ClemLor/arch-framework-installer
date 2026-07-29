# Développement

Respecter `AGENTS.md`, garder les tâches petites et retourner les erreurs sans
appeler `exit`. Toute mutation passe par les helpers communs et possède un
comportement dry-run. Une fonctionnalité comprend code, validation, vérification,
tests et documentation. Aucun commit n'est créé sans demande explicite.

## Configurateur

Deux règles à respecter dans `configurator/` :

- `menu.py` décide **ce qui** est demandé, `prompts.py` **comment**. Un éditeur
  n'appelle jamais `input()` ni `curses` : il passe par `prompts.current()`, sinon
  la logique de contraintes finit dupliquée par interface.
- aucun `import curses` au niveau module en dehors de `tui/term.py`,
  `tui/screen.py`, `tui/app.py` et `tui/install.py`. `_curses` manque sur un
  interpréteur qui ne l'a pas — toute build Windows, toute build minimale — et
  `unittest discover` importe tous les modules de test : un import mal placé casse
  la suite entière et `--show`. Les couches curses se construisent sous WSL ou en
  VM.

Ce qui se calcule sans terminal — lignes, troncature, défilement, champ de
saisie — appartient à `tui/layout.py`, qui est testé directement. Le reste ne
dessine que ce que ces fonctions ont décidé.

Les dotfiles restent séparés de l'installateur. Dank et les applications AUR ou
propriétaires non disponibles dans les dépôts officiels ne doivent pas être
téléchargés via un pipeline distant non vérifié pendant l'installation.
