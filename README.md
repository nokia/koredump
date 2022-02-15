# Coredump REST API for Kubernetes

This project implements REST API for accessing coredumps in Kubernetes cluster.

## Design

- In-cluster `http://koreapi.koredump.svc.cluster.local:80` REST API (Kubernetes Service).
  One container per cluster, application listening port 5000.
- One REST API server per node in k8s cluster (Kubernetes DaemonSet), listening port 5001.
- No changes to platform config (`core_pattern`), use default `systemd-coredump` in OCP.
- Access coredump files from `/var/lib/systemd/coredump`, and (optionally) read journal logs for full coredump metadata written by `systemd-coredump`.
- `DAC_OVERRIDE` capability is used in container to access core dump files and journal logs.
- Command line utility `koredumpctl` that uses the REST API. Automatically installed in OCP to `/usr/local/bin/koredumpctl` with Kubernetes init container.
- Note that in OCP core dumps are deleted by default after 3 days (see `systemd-tmpfiles --cat-config | grep core`).

## Limitations

- OCP `privileged` [Security Context Constraint (SCC)](https://docs.openshift.com/container-platform/4.9/authentication/managing-security-context-constraints.html) is needed.
- Collects all coredumps in cluster (should limit to Nokia coredumps only).
- Optional hardcoded token authentication (`adminToken` in `values.yaml`).
- In-cluster traffic is unencrypted HTTP.
- Simple implementation with python3.
- Hardcoded `/var/lib/systemd/coredump` directory for core files.
  Note that if `core_pattern` is set e.g. to `/tmp/core` or similar, the cores are written to container filesystem, and not visible via this tool.
- Core file deletion not (yet) possible. (Host paths are read-only mounted into container)
- REST API can return errors during installation and upgrade, when the koredump PODs are being terminated or created.

## API Documentation

#### `GET /apiv1/cores`

JSON list of cores (metadata) available in cluster.

<details>
<summary>Example</summary>
<pre>
bash-5.1$ curl -fsS koreapi/apiv1/cores | jq
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
bash-5.1$ curl -fsS koreapi/apiv1/cores/metadata/ocp-example/core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4 | jq
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
bash-5.1$ curl -fvsS -O koreapi/apiv1/cores/download/ocp-example/core.example.9999.f1c1b6957ac9436d9113a86c8c905508.141241.1642081018000000.lz4
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

## Install and run in OCP

Generate coredump (should be then visible in `coredumpctl` output):
```bash
kubectl run -it segfaulter --image=quay.io/icdh/segfaulter --restart=Never
```

Install (in OCP as `core` user):
```bash
oc new-project koredump
helm repo add koredump ...
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

Example in-cluster execution of `koredumpctl`:
```
$ kubectl exec $(kubectl get pods -l koredump.service=1 -o jsonpath='{ .items[0].metadata.name }') -- koredumpctl --token="$(grep -m1 adminToken values.yaml | cut -d: -f2-)" list
- ID: core.certcmnmsactiva.0.e36680b3d32e4f4f9899d72d34fe5fb3.207856.1638186984000000.lz4
  Node: ocp-vdu-6
  Pod: po-cran1-oam-0
  Container: ctr-cran1-oam
- ID: core.stunnel.9999.0f1f04103e4243a48a415de9631a8490.129258.1639033062000000.lz4
  Node: ocp-vdu-6
  Pod: po-cran1-securestorage-0
  Container: ctr-cran1-stunnel
```

Example from Fedora 34 + Docker + k8s environment:
```
$ ./koredumpctl list
- ID: core.segfaulter.1000.017e7b9be1db42099f82681390bc9894.1150585.1639032219000000.zst
  Node: laptop
  Pod: segfaulter
  Container:
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
helm install koredump .
watch kubectl get all
```

Run API servers locally, for example in Fedora:
```bash
USE_TOKENS=0 FLASK_DEBUG=1 FLASK_RUN_PORT=5001 DAEMONSET=1 flask run
USE_TOKENS=0 FLASK_DEBUG=1 FLASK_RUN_PORT=5000 KOREDUMP_DAEMONSET_PORT=5001 DAEMONSET=0 FAKE_K8S=1 flask run
```

## Links

- https://github.com/IBM/core-dump-handler/
- https://github.com/aspekt112/segwatcher
