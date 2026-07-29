# Paquets

## Format

Un fichier par groupe dans `packages/`, un paquet par ligne, extension `.list`.
Les commentaires (`#`) et les lignes vides sont ignorés.

Le format est délibérément pauvre : c'est ce qui rend une décision sur le contenu
de la machine lisible dans un `diff`.

---

## Groupes

| Groupe | État | Contenu |
| --- | --- | --- |
| `base` | rempli | Système minimal, outils de réparation, réseau |
| `firmware` | rempli | Micrologiciels et microcode |
| `framework` | rempli | Spécifique Framework : TPM2, énergie, capteurs |
| `desktop` | **vide** | Session Wayland, portails, audio |
| `hyprland` | **vide** | Compositeur et outils immédiats |
| `fonts` | **vide** | Polices |
| `multimedia` | **vide** | Codecs, lecteurs |
| `development` | **vide** | Chaînes de compilation, exécutions |
| `optional` | **vide** | Le reste |

Les trois premiers sont obligatoires : le menu ne permet pas de les retirer, car
sans eux le résultat ne démarre pas ou ne peut pas être réparé.

Les six autres sont vides pour l'instant. Sélectionner un groupe vide produit un
avertissement explicite plutôt qu'un silence.

---

## Ce qui n'est pas dans les listes

Certains paquets découlent de la configuration et sont ajoutés automatiquement.
Les inscrire aussi dans une liste créerait deux sources de vérité susceptibles de
divorcer.

| Origine | Paquets |
| --- | --- |
| Noyaux choisis | `linux-lts`, `linux`, et leurs `-headers` |
| Chiffrement activé | `cryptsetup` |
| TPM2 activé | `tpm2-tss`, `tpm2-tools` |
| zram activé | `zram-generator` |
| Chargeur de démarrage | `limine` |

---

## Justifications notables

### `fish`

C'est le shell de connexion par défaut du profil. `useradd` accepte un shell qui
n'existe pas, et le compte est alors créé sans pouvoir se connecter.

Une vérification explicite refuse l'installation si le shell configuré est absent
de la cible — l'erreur est réparable à ce moment-là, beaucoup moins après un
redémarrage.

### `amd-ucode` et `intel-ucode`

Les deux sont installés. La même configuration sert les modèles Framework Intel
et AMD, et le microcode inutile n'est simplement pas chargé.

Le microcode corrige des errata processeur avant le démarrage du noyau ; son
absence produit des instabilités qui ressemblent à des bogues logiciels.

### `btrfs-progs`, `cryptsetup`, `vim`, `less`

Présents dans le système installé et pas seulement dans l'ISO. Un démarrage cassé
ne peut pas être réparé depuis son propre shell si les outils n'y sont pas.

### `iwd` plutôt que `wpa_supplicant`, et pas de `dhcpcd`

Moins de pièces mobiles pour un portable qui ne rejoint que des réseaux
WPA2/WPA3.

Le partage des rôles est explicite :

| Composant | Rôle |
| --- | --- |
| `iwd` | authentification sans fil uniquement |
| `systemd-networkd` | adresses et DHCP, filaire et sans fil |
| `systemd-resolved` | résolution DNS |

`iwd` sait faire son propre DHCP, et `dhcpcd` aussi. Les activer en plus de
`systemd-networkd` mettrait deux clients en concurrence sur la même interface, et
le comportement réseau du premier démarrage dépendrait de celui qui gagne.

`EnableNetworkConfiguration=false` est écrit explicitement dans
`/etc/iwd/main.conf` plutôt que de s'appuyer sur la valeur par défaut, pour que la
répartition reste visible.

Le métrique de route est plus élevé sur le sans-fil que sur le filaire : une
machine sur station d'accueil préfère le câble.

### `snapper`

Installé dès le début, alors qu'aucune configuration n'est encore appliquée. La
possibilité de retour arrière dépend de sa présence, et l'ajouter après coup
signifie que les premières semaines ne sont pas couvertes.

---

## AUR

Aucun paquet AUR n'est installé pendant l'installation : l'ISO n'a ni assistant
AUR ni environnement de compilation.

`limine-mkinitcpio-hook` est dans ce cas. L'installateur le signale à la fin et le
laisse pour après le premier démarrage. Le système doit pouvoir démarrer sans
lui — c'est la contrainte qui rend ce report acceptable.

---

## Ajouter un paquet

1. l'ajouter au fichier du groupe concerné, avec un commentaire expliquant
   *pourquoi* ;
2. lancer les tests : la séquence de commandes de référence change, ce qui rend
   l'ajout visible en revue.

Rien ne vérifie automatiquement qu'un paquet existe dans les dépôts. Une faute de
frappe n'est découverte qu'au `pacstrap`.
