# platform-cicd

Bootstrap technique de la plateforme applicative du POC : installe ArgoCD,
puis attend que GitLab (déployé déclarativement par ArgoCD depuis
`../platform-gitops`) soit prêt pour configurer ses credentials (PAT
Terraform, SSO Dex, token runner). Les images applicatives sont poussées sur
GHCR, pas sur un registry interne au cluster.

Ce repo se deploie sur le contexte Kubernetes courant. Il ne cree pas de
cluster. La configuration suivie en continu par ArgoCD vit dans le repo frere
`../platform-gitops`.

## Prerequis

- Un cluster Kubernetes deja provisionne par `cluster`.
- Gateway API, Traefik et MetalLB disponibles.
- Les repos freres clones a cote de celui-ci :
  - `../ci-templates`
  - `../helloworld`
  - `../helloworld-iac`
  - `../platform-gitops`

## Usage

```sh
make bootstrap
```

URLs par defaut :

- GitLab : `http://gitlab.192.168.33.100.nip.io`
- ArgoCD : `http://argocd.192.168.33.100.nip.io`
