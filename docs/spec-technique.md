# Spec technique — platform-cicd

## Structure du dépôt

```
argocd/
  root-app.yaml              Application racine ArgoCD (appliquée une fois à la main)
  repo-server-ca-patch.yaml  Patch strategic merge pour le CA corporate
  dex-ca-patch.yaml          Patch strategic merge pour le CA Gateway
scripts/
  platform_inventory.py      Modèle historique d'inventaire apps
  render-argocd-apps.py      Génère les manifests ArgoCD depuis argocd/apps/<app>/app.yaml
  run-bootstrap.py           Exécute la séquence bootstrap avec START_AT/STOP_AFTER
  filter-argocd-install.py   Filtre le manifest ArgoCD (retire notifications)
  gitlab_bootstrap.py        Helpers readiness GitLab ciblée
  gitlab-tf-credentials.py   Crée le PAT/Secret GitLab consommé par Terraform
  gitlab-dex-oauth-app.py    Crée l'app OAuth GitLab pour Dex
  gitlab-runner-token.py     Crée le token runner et le Secret K8s
  init-project.py            Déprécié : onboarding app manuel sous argocd/apps/<app>/
ansible/
  playbook.yml                Étapes ArgoCD/Flux du bootstrap, sélectionnées via --tags
  roles/argocd_trust_ca/      Rôle paramétré, réutilisé par argocd-trust-corporate-ca et argocd-trust-local-gateway-ca
Makefile
requirements.txt             pyyaml
```

## Ressources applicatives

Les ressources propres aux applications sont décrites sous
`platform-gitops/argocd/apps/<app>/app.yaml`. `render-argocd-apps.py` lit ces
descriptions, normalise les conventions via `platform_inventory.py`, puis écrit :

- `platform-gitops/argocd/generated/apps/<app>/app-project.yaml` ;
- `platform-gitops/argocd/generated/apps/<app>/applicationset.yaml` ;
- `platform-gitops/argocd/generated/apps/<app>/repo-creds.yaml` ;
- `platform-gitops/argocd/generated/apps/<app>/kustomization.yaml` ;
- `platform-gitops/argocd/managed/apps-appset.yaml`.

`make check-generated` exécute le générateur en mode comparaison et échoue si
les fichiers committés ne correspondent plus aux descriptions `app.yaml`.

## `filter-argocd-install.py` — filtre ArgoCD

Télécharge ou lit le manifest d'installation ArgoCD et filtre les ressources
`argocd-notifications-*` non utilisées dans ce POC. Accepte une URL ou un
chemin local.

## `run-bootstrap.py` — séquence relançable

`make bootstrap` délègue à `run-bootstrap.py` avec la liste ordonnée des étapes
Makefile. Le script exécute chaque étape une par une via `make <étape>` et
supporte :

- `START_AT=<étape>` pour reprendre après correction à la bonne étape ;
- `STOP_AFTER=<étape>` pour s'arrêter volontairement après une étape ;
- `make bootstrap-from-<étape>` comme raccourci de reprise.

Les étapes `*-wait` globales ne font pas partie de la séquence : les prérequis
sont vérifiés au plus près de l'action qui en dépend.

## `ansible/` — étapes de bootstrap ArgoCD/Flux

Les étapes du bootstrap qui manipulent l'état du cluster (namespace, CA
bundle, ConfigMap, patch, rollout) sont exprimées en tâches Ansible plutôt
qu'en shell brut dans le Makefile — cf. la règle d'ordre de préférence dans
`AGENTS.md` (TF/K8s déclaratif, puis Ansible, Make en dernier recours). Chaque
cible Makefile devenue concernée n'est plus qu'un appel à `ansible-playbook
playbook.yml --tags <étape>` :

- `argocd-install` : namespace ArgoCD + manifest filtré (`server-side apply`).
- `argocd-bootstrap` : attente du CRD `Application` puis application de
  `argocd/root-app.yaml`.
- `argocd-ingress` : bascule `server.insecure=true` et redémarrage conditionnel.
- `flux-sops-age` : vérifie la clé age locale, crée le namespace `flux-system`
  et le Secret `sops-age`.
- `argocd-trust-corporate-ca` / `argocd-trust-local-gateway-ca` : instances du
  rôle `argocd_trust_ca`, paramétrées par le déploiement ciblé
  (`argocd-repo-server` / `argocd-dex-server`), le fichier de patch et la
  commande shell qui produit le certificat additionnel (trousseau macOS pour
  le CA corporate, Secret `nip-io-wildcard-tls` pour le CA de la Gateway
  locale). Le rôle attend le rollout, extrait le bundle CA du pod, fusionne
  avec le certificat additionnel, recrée le ConfigMap, patche le déploiement
  puis attend de nouveau le rollout.

Les étapes GitLab (`gitlab-tf-credentials`, `gitlab-dex-oauth-app`,
`gitlab-runner-token`) restent des scripts Python : elles gèrent déjà leur
propre polling/idempotence contre l'API GitLab et n'ont pas été migrées.

## `gitlab-dex-oauth-app.py` — OAuth GitLab → Dex

1. Vérifie l'idempotence : `argocd-secret` contient-il déjà `dex.gitlab.clientID` ?
2. Attend la readiness API GitLab via `/-/readiness`.
3. Récupère le mot de passe root GitLab depuis le Secret K8s.
4. S'authentifie via l'API GitLab (password grant OAuth2).
5. Crée l'application OAuth avec `trusted: true` et `confidential: true`.
6. Patch `argocd-secret` avec `dex.gitlab.clientID` et `dex.gitlab.clientSecret`.

## `gitlab-tf-credentials.py` — token Terraform GitLab

1. Vérifie si `flux-system/gitlab-tf-credentials` existe avec un token encore
   valide contre l'API GitLab.
2. Attend la readiness API GitLab via `/-/readiness`.
3. Si absent ou invalide, récupère le mot de passe root GitLab depuis le Secret
   K8s `gitlab-gitlab-initial-root-password`.
4. S'authentifie via l'API GitLab (password grant OAuth2).
5. Crée/rotate un PAT `terraform-controller` avec les scopes `api`,
   `read_repository`, `write_repository`.
6. Applique le Secret K8s `gitlab-tf-credentials` dans `flux-system`, consommé
   par `Terraform/gitlab-iac`.

## `gitlab-runner-token.py` — token runner

1. Vérifie l'idempotence : le Secret `gitlab-gitlab-runner-secret` existe-t-il avec un token ?
2. Attend la readiness API GitLab via `/-/readiness`.
3. S'authentifie via l'API GitLab.
4. Crée un runner d'instance via `/api/v4/user/runners`.
5. Applique un Secret K8s via `kubectl apply` (dry-run + pipe).

## Dépendances

- `kubectl` avec kubeconfig valide (cluster-admin pour le bootstrap).
- `python3` avec `pyyaml` (`pip install -r requirements.txt`).
- `ansible-playbook` (collection `ansible.builtin` uniquement, aucune
  collection externe requise).
- `security` (macOS) pour extraire le CA Zscaler du trousseau système, appelé
  depuis le rôle Ansible `argocd_trust_ca`.
- Accès réseau au cluster Kubernetes.
