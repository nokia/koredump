# Coredump REST API for Kubernetes

This project implements REST API for accessing coredumps in Kubernetes cluster.

## Design

- In-cluster `http://koreapi.koredump.svc.cluster.local:80` REST API (Kubernetes Service).
  One container per cluster, application listening port 5000.
- One REST API server per node in k8s cluster (Kubernetes DaemonSet), listening port 5001.
- No changes to platform `core_pattern` kernel config, use default `systemd-coredump` in OCP.
- Access coredump files from `/var/lib/systemd/coredump`, and (optionally) read journal logs for full coredump metadata written by `systemd-coredump`.
- `DAC_OVERRIDE` capability is used in container to access core dump files and journal logs.
- Command line utility `koredumpctl` that uses the REST API. Automatically installed in OCP to `/usr/local/bin/koredumpctl` with Kubernetes init container.
- Note that in OCP core dumps are deleted by default after 3 days (see `systemd-tmpfiles --cat-config | grep core`).
- Collect all coredumps in cluster by default. Limit to predefined namespaces by setting `filter.namespaceRegex` variable when installing with Helm charts.
- Token authentication for REST API. Server uses [TokenReview](https://kubernetes.io/docs/reference/access-authn-authz/authentication/) to verify the token.

## Limitations

- Red Hat OCP `privileged` [Security Context Constraint (SCC)](https://docs.openshift.com/container-platform/4.9/authentication/managing-security-context-constraints.html) is needed.
- In-cluster traffic is unencrypted HTTP.
- Simple implementation with python3.
- Hard requirement on systemd-coredump, core files are processed from `/var/lib/systemd/coredump` directory only.
  Note that if `core_pattern` is set e.g. to `/tmp/core` or similar, the cores are written to container filesystem, and not visible via this tool.
- Core file deletion not (yet) possible. (Host paths are read-only mounted into containers)
- REST API can return errors during installation and upgrade, when the koredump PODs are being terminated or created.
- systemd-coredump by default limits core size to maximum 2GB, larger core files are truncated. Increase the limit by setting for example `ExternalSizeMax=32G` in /etc/systemd/coredump.conf (or add conf file in `/etc/systemd/coredump.conf.d/`)

## API Documentation

#### `GET /apiv1/cores`

JSON list of cores (metadata) available in cluster.

<details>
<summary>Example</summary>
<pre>
bash-5.1$ curl -fsS -H "Authorization: Bearer $token" koreapi/apiv1/cores | jq
[
  {
    "ARCH": "x86_64",
    "COREDUMP_CMDLINE": "/usr/bin/example -a -b -c",
    "COREDUMP_COMM": "example",
    ...
    "COREDUMP_SIGNAL": 24,
    "COREDUMP_SIGNAL_NAME": "SIGXCPU",
    "container": "ctr-ns1-example",
    "id": "core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4",
    "node": "ocp-example",
    "pod": "pod-ns1-example-86b5c54447-lrbz2"
  },
  {
    ...
  }
]
</pre>
</details>

#### `GET /apiv1/cores/metadata/<node>/<core_id>`

JSON metadata of single core file, identified by kubernetes node name, and core file ID.

<details>
<summary>Example</summary>
<pre>
bash-5.1$ curl -fsS -H "Authorization: Bearer $token" koreapi/apiv1/cores/metadata/ocp-example/core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4 | jq
{
  "ARCH": "x86_64
  "COREDUMP_CMDLINE": "/usr/bin/example -a -b -c",
  "COREDUMP_COMM": "example",
  ...
  "COREDUMP_SIGNAL": 24,
  "COREDUMP_SIGNAL_NAME": "SIGXCPU",
  "container": "ctr-ns1-example",
  "id": "core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4",
  "node": "ocp-example",
  "pod": "pod-ns1-example-86b5c54447-lrbz2"
}
</pre>
</details>

#### `GET /apiv1/cores/download/<node>/<core_id>`

Download core file, identified by kubernetes node name, and core file ID.

<details>
<summary>Example</summary>
<pre>
bash-5.1$ curl -fvsS -O -H "Authorization: Bearer $token" koreapi/apiv1/cores/download/ocp-example/core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4
* Connected to koreapi (172.30.199.84) port 80 (#0)
> GET /apiv1/cores/download/ocp-example/core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4 HTTP/1.1
> Host: koreapi
> User-Agent: curl/7.79.1
> Accept: */*
> 
* Mark bundle as not supporting multiuse
< HTTP/1.1 200 OK
< Server: gunicorn
< Date: Fri, 14 Jan 2022 05:48:11 GMT
< Connection: close
< Content-Disposition: attachment; filename=core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4
< Content-Type: application/octet-stream
< Content-Length: 279816
< Last-Modified: Thu, 13 Jan 2022 12:29:50 GMT
< Cache-Control: no-cache
< 
* Closing connection 0
</pre>
</details>

## Install and run in Red Hat OCP

Generate coredump (should be then visible in `coredumpctl` output):
```bash
kubectl run -it segfaulter --image=quay.io/icdh/segfaulter --restart=Never
```

Install (in Red Hat OCP as `core` user):
```bash
oc new-project koredump
helm repo add koredump https://nokia.github.io/koredump/
helm repo update
helm install -n koredump koredump koredump/koredump
watch kubectl -n koredump get all
```

Upgrade:
```bash
helm repo update
helm upgrade -n koredump koredump koredump/koredump
watch kubectl -n koredump get all
```

Test with `koredumpctl`:
```bash
koredumpctl status
koredumpctl list
```

Example `koredumpctl list` output:
```
$ koredumpctl list
- ID: core.prog.0.e36680b3d32e4f4f9899d72d34fe5fb3.207856.1638186984000000.lz4
  Node: ocp-6
  Pod: po-prog-oam-0
  Container: ctr-prog
  Namespace: demo
  Image: image-registry.openshift-image-registry.svc:5000/demo/prog:1.2.0
  Signal: SIGXCPU (24)
  Timestamp: 2022-02-23T08:23:16Z
- ID: core.stunnel.9999.29162cb2ca0d4e1eb67a4ffb549ed670.2354652.1645604596000000.lz4
  Node: ocp-6
  Pod: po-cran1-stunnel-d897f48fd-8q68m
  Container: ctr-cran1-stunnel
  Namespace: demo
  Image: image-registry.openshift-image-registry.svc:5000/demo/stunnel:2.4.0
  Signal: SIGXCPU (24)
  Timestamp: 2022-02-23T08:23:16Z
```

Uninstall:
```bash
helm uninstall koredump
rm /usr/local/bin/koredumpctl
```

## Development Notes

Install from git repository:
```bash
git clone https://github.com/nokia/koredump.git
cd koredump
oc new-project koredump
helm install koredump charts/koredump/
watch kubectl get all
```

Run API servers locally without Kubernetes, for example in Fedora:
```bash
NO_TOKENS=1 FLASK_DEBUG=1 PORT=5001 DAEMONSET=1 FAKE_K8S=1 gunicorn --access-logfile=- app
NO_TOKENS=1 FLASK_DEBUG=1 PORT=5000 KOREDUMP_DAEMONSET_PORT=5001 DAEMONSET=0 FAKE_K8S=1 gunicorn --access-logfile=- app
```

## Links

- https://github.com/IBM/core-dump-handler/
- https://github.com/aspekt112/segwatcher
