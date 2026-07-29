# Tests

## Le problème

L'installateur détruit un disque, exige d'être root, et ne fonctionne que depuis
une ISO live. Tester naïvement voudrait dire une machine sacrifiable par
exécution.

La stratégie du projet est de rendre chaque décision vérifiable sans matériel, et
de réserver le matériel à ce qui ne peut être vérifié autrement : est-ce que ça
démarre.

---

## Quatre niveaux

### 1. Modèles et validateurs

Aucune dépendance au système. Formats de taille, jeux de sous-volumes, capacité,
règles croisées.

```bash
pytest tests/test_size.py tests/test_config.py
```

Ce niveau attrape les erreurs de configuration : une taille en `GB` au lieu de
`GiB`, un disque de 64 GiB avec 32 GiB d'échange qui ne laisse rien à la racine,
TPM2 activé sans clé de secours.

### 2. Couche de sécurité, sur périphériques enregistrés

```bash
pytest tests/test_device_handler.py
```

Chaque motif de refus est vérifié **séparément** : support live, transport USB,
périphérique amovible, partition au lieu d'un disque entier. Les gardes sont
indépendants dans le code ; un test unique « la clé USB est refusée » passerait
alors que trois d'entre eux seraient cassés.

C'est ce qui s'est produit à l'écriture de ces tests : le jeu de données ne
déclarait pas `/run/archiso/bootmnt`, la détection du support live renvoyait
`None`, et seul le garde USB faisait le travail.

### 3. Séquence de commandes de référence

```bash
pytest tests/test_installer.py
```

Une simulation complète produit la liste des commandes, comparée à
`tests/golden/install-commands.txt`.

Ce fichier est la vérification la plus utile du projet. Il fixe :

- les unités de `sgdisk` (`1M`, jamais `1MiB`, que `sgdisk` rejette) ;
- les options de `cryptsetup luksFormat` ;
- l'ordre de création des sous-volumes ;
- l'ordre de montage, `@` en premier puisque tout le reste se monte dedans ;
- la position de l'enrôlement TPM2, après la clé de secours.

Sont également vérifiées les propriétés d'ordre elles-mêmes, indépendamment du
fichier : le conteneur avant le système de fichiers, les paquets avant le
chargeur de démarrage, la clé de secours avant TPM2.

### 4. Machine virtuelle, puis matériel

Ce que les niveaux précédents ne peuvent pas dire : est-ce que le résultat
démarre.

---

## Procédure en machine virtuelle

QEMU avec micrologiciel UEFI, ISO Arch à jour, disque virtuel vierge.

```bash
# 1. simulation, revue de la sortie
python -m arch_framework --install --dry-run --config saved.json

# 2. installation réelle
python -m arch_framework --install --config saved.json --creds creds.json
```

À vérifier après redémarrage :

| Vérification | Commande |
| --- | --- |
| Menu Limine présent | visuel |
| Déverrouillage LUKS | visuel |
| Sous-volumes montés | `btrfs subvolume list /` |
| Options de montage | `findmnt -t btrfs` |
| Échange actif | `swapon --show` |
| Hibernation | `systemctl hibernate` puis reprise |
| Compte utilisateur | connexion, `sudo -v` |
| Root verrouillé | `sudo passwd -S root` |

À vérifier aussi : pointer la configuration sur le disque de l'ISO elle-même
doit être refusé.

```bash
python -m arch_framework --plan-storage --config attack.json
```

TPM2 ne peut pas être vérifié en machine virtuelle sans TPM émulé
(`swtpm`). Sans lui, l'étape est passée et l'installation reste utilisable avec
la phrase de passe.

---

## Sur le matériel, en dernier

Dans cet ordre, et pas un autre :

1. sauvegarde externe vérifiée — pas seulement effectuée ;
2. installation complète ;
3. clé de secours notée sur papier avant de valider l'enrôlement TPM2 ;
4. redémarrage, vérifications du tableau ci-dessus ;
5. **réinstallation depuis la même configuration enregistrée**.

La cinquième étape est celle qui compte. Elle prouve que l'artefact reproduit la
machine, ce qui est l'objectif du projet ; les quatre premières prouvent
seulement qu'une installation a réussi une fois.

---

## Ce qui n'est pas testé

- aucun démarrage réel n'a encore eu lieu : ni machine virtuelle, ni matériel ;
- l'enrôlement TPM2 n'a jamais été exécuté ;
- la reprise après hibernation n'a jamais été exécutée ;
- les listes de paquets `desktop`, `hyprland`, `fonts`, `multimedia`,
  `development` et `optional` sont vides ;
- aucune vérification automatique n'existe pour l'existence réelle des paquets
  dans les dépôts.
