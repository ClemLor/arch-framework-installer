# Sécurité

## Accès administrateur

L'installateur **ne définit jamais de mot de passe root**. Après `pacstrap`, le
compte root reste verrouillé : aucune connexion root n'est possible.

`sudo` via le groupe `wheel` est donc le **seul** accès administrateur de la
machine.

| Élément | Où |
| --- | --- |
| Paquet `sudo` | `packages/base.list` |
| `%wheel ALL=(ALL:ALL) ALL` | `/etc/sudoers.d/10-wheel`, mode `0440` |
| Appartenance au groupe | `USER_GROUPS` doit contenir `wheel` |

Un fichier `sudoers` accordant `%wheel` et un compte appartenant à `wheel` sont
deux faits **indépendants**. Chacun paraît correct isolément, et seuls les deux
ensemble accordent quelque chose.

Une configuration où `USER_GROUPS` omet `wheel` produisait donc une machine que
personne ne pouvait administrer, alors que chaque vérification passait :
format valide, groupes réels, `useradd` réussi, fichier `sudoers` écrit et validé
par `visudo`. Le résultat était irrécupérable sans réinstaller, et
`afi-aur-setup` échouait au premier démarrage.

Trois contrôles couvrent désormais ce cas :

- `validate_config` refuse une configuration dont `USER_GROUPS` n'inclut pas
  `wheel`, en expliquant pourquoi ;
- la vérification finale interroge `id --name --groups` puis `sudo --list`, donc
  demande à `sudo` ce qu'il accorde réellement plutôt que de supposer qu'un
  fichier syntaxiquement valide accorde ce qu'il semble accorder ;
- le validateur post-démarrage refait le contrôle, car à ce stade l'ISO n'est
  plus là et perdre l'accès signifie réinstaller.

La correspondance est exacte : un groupe nommé `wheelless` ne compte pas.

Un mot de passe est demandé interactivement pour le compte utilisateur pendant
l'installation. Il n'est jamais stocké dans la configuration.

---

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
