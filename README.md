# Coredump REST API for Kubernetes

This project implements REST API for accessing coredumps in Kubernetes cluster.

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

Example execution of `koredumpctl`:
```
$ koredumpctl list
- ID: core.foo.0.e36680b3d32e4f4f9899d72d34fe5fb3.207856.1638186984000000.lz4
  Node: ocp-6
  Pod: pod-foo-0
  Container: ctr-foo
- ID: core.storage.9999.0f1f04103e4243a48a415de9631a8490.129258.1639033062000000.lz4
  Node: ocp-6
  Pod: pod-storage-0
  Container: ctr-storage
```

Uninstall:
```bash
helm -n koredump uninstall koredump
rm /usr/local/bin/koredumpctl
```
