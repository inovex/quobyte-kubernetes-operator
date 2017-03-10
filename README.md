# Quobyte Kubernetes Deployer

This is a Python script that deploys [Quobyte](https://www.quobyte.com) on top of Kubernetes. The script deploys the following Quobyte services:

- `Registry`
- `Metadata`
- `Data`
- `Client`
- `API` (and the Web Console)

## Prequesits

- [PyYaml](https://pypi.python.org/pypi/PyYAML)
- [Kubernetes API Client](https://github.com/kubernetes-incubator/client-python)
- Running Kubernetes Cluster

```
pip install pyyaml kubernetes
```

## Usage

### Configuration

Copy the configuration file config.yaml.example to config.yaml

```bash
cp config.yaml.example config.yaml
```

Example Configuration file (if no configuration is specified for an Quobyte service the default values will be used):

```yaml
namespace: quobyte
version: '1.3.14'
kubernetes_files: './quobyte'
registry:
    nodes:
        - 207.154.211.166
        - 207.154.211.247
        - 207.154.215.157
metadata:
    nodes:
        - 207.154.211.166
        - 207.154.211.247
        - 207.154.215.157
client:
    mount_opts: '' # example: '-o user_xattr'
api:
    resources:
        limits:
            memory: 1Gi
            cpu: 500m
        requests:
            memory: 500Mi
            cpu: 250m
default:
    nodes:
        - all
    resources:
        limits:
            memory: 2Gi
            cpu: 1
        requests:
            memory: 1Gi
            cpu: 500m
```

### Deployment

```bash
python3 quobyte-k8s-deployer.py
```

#### Inside Kubernetes

You can also deploy Quobyte from inside the Kubernetes Cluster:

```bash
cp k8s/deployer_config.yaml.example k8s/deployer_config.yaml
```

Adjust the config to your need and then run the deployment

```bash
kubectl create -f k8s
```

## Tested

This script is tested with Python 3 (Python 2 should also work) and Kubernetes 1.5.

## Additional Information

### Multiple Quobyte Data devices

The Quobyte deployer allows to use preformatted Devices (for more information how to format your devices for Quobyte look into the Quobyte [docs](https://support.quobyte.com)). To use a preformatted disk just mount the Disk into `/mnt/data` with an unique Name and execute the [qmkdev](https://github.com/quobyte/quobyte-deploy/blob/master/tools/qmkdev) script with `qmkdev -t DATA -s $(uuidgen) <mountpoint>`. There is some effort to move this step into the deployer (doesn't work at the moment).

# Todos

- See Code
- Add better docs
- Add (unit) Tests
- pep8