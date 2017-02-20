# Quobyte Kubernetes Deployer

This is a Python script that deploys [Quobyte](https://www.quobyte.com) on top of Kubernetes.

## Prequesits

- [Kubernetes API Client](https://github.com/kubernetes-incubator/client-python)
- Running Kubernetes Cluster

## Usage

### Configuration

Copy the configuration file config.yaml.example to config.yaml

```bash
cp config.yaml.example config.yaml
```

Example Configfile:

```yaml
namespace: quobyte
registry:
    - node: 138.68.100.83
      bootstrap: true
    - node: 138.68.104.117
    - node: 138.68.104.130
metadata:
    - node: 138.68.100.83
    - node: 138.68.104.117
    - node: 138.68.104.130
data:
    - node: all
client:
    - node: all
version: '1.3.12'
kubernetes_files:
    path: './quobyte'
```

### Deployment

```bash
python3 quobyte-k8s-deployer.py
```

## Tested

This script is tested with Python 3 (Python 2 should also work) and Kubernetes 1.5.

# Todos

- See Code
- Add better docs
