# Sécurité

## Modèle de menace

Ce que le projet cherche à empêcher : qu'un ordinateur portable perdu ou volé
livre son contenu.

Ce qu'il ne cherche pas à empêcher : un attaquant disposant d'un accès physique
répété et discret à la machine. S'en défendre demande un démarrage sécurisé avec
des clés personnelles et une image noyau unifiée signée, ce que le projet ne fait
pas encore.

---

## Chiffrement

LUKS2 sur la partition système entière. Seule la partition EFI reste en clair,
parce que le micrologiciel doit pouvoir la lire.

Les paramètres sont explicites plutôt que laissés aux valeurs par défaut :

```
--type luks2 --pbkdf argon2id --cipher aes-xts-plain64 --key-size 512 --hash sha512
```

La raison est la reproductibilité : un système installé aujourd'hui et un système
réinstallé dans deux ans doivent être identiques, ce qui n'est pas le cas si les
paramètres suivent les valeurs par défaut de `cryptsetup` du moment.

---

## Trois façons d'ouvrir le disque

Par ordre d'usage :

1. **TPM2** — automatique, scellé sur les PCR 0 et 7.
2. **Phrase de passe** — celle saisie à l'installation. Jamais supprimée.
3. **Clé de secours** — générée à l'installation, affichée une seule fois.

Le point important est qu'il y en ait trois. Le scellement TPM2 est lié à l'état
du micrologiciel et du démarrage sécurisé : une mise à jour du BIOS peut suffire
à ce qu'il ne s'ouvre plus. Ce n'est pas une panne rare, c'est un événement
attendu.

### Choix des PCR

- **PCR 0** : micrologiciel.
- **PCR 7** : état du démarrage sécurisé.

Sceller sur davantage de PCR est plus strict et casse plus souvent. Sceller sur
moins signifie qu'une chaîne de démarrage altérée peut encore desceller la clé.

### Ordre imposé

La clé de secours est ajoutée, affichée, et l'utilisateur doit confirmer
explicitement l'avoir notée **avant** l'enrôlement TPM2.

Cet ordre est vérifié par un test. L'inverse laisserait une fenêtre pendant
laquelle le seul accès serait un scellement qu'une mise à jour peut invalider.

La confirmation est bloquante et exige de taper `CONFIRMED`. Une clé affichée
dans un journal qui défile est une clé que personne n'a notée.

### Format de la clé de secours

Huit groupes de cinq caractères, alphabet sans `I`, `O`, `0` ni `1`. Le format est
dicté par le fait qu'elle sera recopiée à la main sur du papier.

---

## Refus de destruction

Quatre gardes indépendants, chacun capable de refuser seul :

| Garde | Raison |
| --- | --- |
| Disque entier | Installer sur une partition ne produit pas la disposition attendue |
| Pas le support live | Effacer l'ISO en cours d'exécution |
| Pas d'USB | Presque jamais la cible voulue |
| Pas d'amovible | Idem |

Un disque monté est refusé pour l'écriture, mais accepté en inspection et en
génération de plan.

### Où la vérification a lieu

**Immédiatement avant `wipefs`**, pas dans le menu.

Le menu vérifie aussi, et masque les disques inéligibles. Mais une configuration
peut être écrite à la main, copiée d'une machine à l'autre, ou rejouée des mois
plus tard sur un matériel différent. La seule vérification qui vaille est celle
prise contre le disque tel qu'il est au moment d'écrire.

Elle lève une exception, elle n'avertit pas. Et elle s'applique aussi en mode
simulation : répéter une opération qui serait refusée n'a pas de sens.

### Périphériques enregistrés

Une installation réelle refuse de démarrer si les informations de disque
proviennent d'un enregistrement. Partitionner un disque réel d'après des faits
lus dans un fichier n'est jamais correct.

---

## Secrets

Ils ne sont jamais :

- passés en argument de commande — la liste des processus est lisible par tous
  les utilisateurs de la machine ;
- écrits dans la configuration enregistrée — celle-ci doit rester partageable,
  relisible et versionnable, ce qu'un mot de passe lui interdirait ;
- écrits dans le système cible.

Ils transitent par l'entrée standard. La clé de secours est le seul secret écrit
temporairement dans un fichier, sur `tmpfs`, en `0600`, supprimé immédiatement —
parce que `cryptsetup luksAddKey` exige un fichier.

Le fichier de secrets (`--creds`) est séparé et exclu du dépôt par `.gitignore`.

---

## Comptes

Le compte root est verrouillé dès qu'un utilisateur `sudo` existe. Deux mots de
passe à protéger au lieu d'un n'apporte rien.

`sudo` est accordé par un fichier dans `/etc/sudoers.d/` plutôt qu'en modifiant
`/etc/sudoers` : une mise à jour du paquet ne peut pas entrer en conflit avec le
fichier, et l'origine de la règle reste évidente.

Ce fichier est écrit **avant** la création du premier compte, pour qu'un échec en
cours de route ne laisse pas un compte qui se croit administrateur sans l'être.

---

## Ce qui n'est pas fait

- **Démarrage sécurisé avec clés personnelles.** Sans lui, PCR 7 mesure l'état du
  démarrage sécurisé du fabricant, pas une chaîne dont on contrôle la signature.
- **Image noyau unifiée signée.** Le noyau et l'initramfs ne sont pas signés,
  donc leur remplacement n'est pas détecté.
- **Chiffrement de `/boot`.** La partition EFI est lisible et modifiable par
  quiconque a accès au disque.
- **Vérification du micrologiciel.** `fwupd` est installé mais aucune politique
  n'est appliquée.

Ces limites sont cohérentes avec le modèle de menace : elles protègent contre le
vol, pas contre un accès physique répété.
