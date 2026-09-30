# Deploying MyFriends (plan step 1: walking skeleton)

Plain YAML, namespace `factory`. Two Deployments + Services:

- `api-deployment.yaml` — `myfriends-api`, port 8000, serves `/healthz` and
  `/profiles/me`.
- `web-deployment.yaml` — `myfriends-web`, port 80, serves the built static
  assets and proxies `/healthz` and `/profiles/` to `myfriends-api:8000`
  (see `app/web/nginx.conf`).

No database, no auth, no Ingress — those land in later plan steps. There is
no ingress controller in this cluster; the only route in is the cloudflared
tunnel, so publishing the app is a ConfigMap entry, not a Kubernetes
resource in this repo.

## Applying

```sh
kubectl apply -f deploy/api-deployment.yaml
kubectl apply -f deploy/web-deployment.yaml
kubectl -n factory rollout status deployment/myfriends-api
kubectl -n factory rollout status deployment/myfriends-web
```

Images are referenced as `myfriends-api:latest` / `myfriends-web:latest`;
point them at whatever registry/tag the deploy lane pushes to.

## cloudflared ingress entry (not applied by this change)

The tunnel's ConfigMap already routes 11 hostnames on `freundcloud.org.uk`.
Add this entry — ahead of the catch-all `http_status:404` rule — to route
the new hostname to the `myfriends-web` Service:

```yaml
- hostname: myfriends.freundcloud.org.uk
  service: http://myfriends-web.factory.svc.cluster.local:80
```

This repository does not touch the live ConfigMap; apply it by hand
alongside the Deployments above.
