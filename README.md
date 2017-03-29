# Quobyte Kubernetes Deployer

This is a Python script that deploys [Quobyte](https://www.quobyte.com) on top of Kubernetes. The script deploys the following Quobyte services:

- `Registry`
- `Metadata`
- `Data`
- `Client`
- `API` (and the Web Console)

## Prerequisites

- [PyYaml](https://pypi.python.org/pypi/PyYAML)
- [Kubernetes API Client](https://github.com/kubernetes-incubator/client-python)
- Running Kubernetes Cluster

```
pip install pyyaml kubernetes
```

## Usage

### Configuration

Copy the configuration file `examples/example_config.yaml` to `config.yaml`

```bash
cp examples/example_config.yaml config.yaml
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

## Additional Information

- If no configuration is specified for an Quobyte service the default values will be used

### Multiple Quobyte (Meta)Data devices

The Quobyte deployer allows to use preformatted Devices (for more information how to format your devices for Quobyte look into the Quobyte [docs](https://support.quobyte.com)). To use a preformatted disk just mount the Disk into `/mnt/data` with an unique Name and execute the [qmkdev](https://github.com/quobyte/quobyte-deploy/blob/master/tools/qmkdev) script with `qmkdev -t DATA -s $(uuidgen) <mountpoint>`. There is some effort to move this step into the deployer (doesn't work at the moment).

## Tested

This script is tested with Python 3 (Python 2 should also work) and Kubernetes 1.5.
