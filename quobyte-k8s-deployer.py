#!/usr/bin/env python3

from __future__ import print_function

from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import time
import argparse


def load_body(body_file):
    with open(body_file, 'r', encoding='utf-8') as content:
        body = yaml.safe_load(content)
    if body is None:
        raise ValueError('Body of file {} is empty'.format(body_file))

    return body


def create_namespace(namespace):
    api_instance = client.CoreV1Api()
    api_response = None
    try:
        api_response = api_instance.list_namespace(field_selector='metadata.name=quobyte')
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespace: %s\n" % e)
        # raise
    except ValueError:
        pass

    if api_response is not None:
        return

    print('Create Namespace: {}'.format(namespace))
    body = client.V1Namespace()
    body.api_version = 'v1'
    body.kind = 'Namespace'
    metadata = client.V1ObjectMeta()
    metadata.name = namespace
    body.metadata = metadata

    try:
        api_instance.create_namespace(body)
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)


def create_configmap(namespace, config_path):
    api_instance = client.CoreV1Api()
    api_response = None
    try:
        api_response = api_instance.list_namespaced_config_map(namespace, field_selector='metadata.name=quobyte-config')
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_config_map: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return

    print('Create Quobyte Config Map')
    try:
        api_instance.create_namespaced_config_map(namespace, load_body(config_path + '/config.yaml'))
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_configmap: %s\n" % e)


def create_svc(namespace, config_path, name):
    api_instance = client.CoreV1Api()
    api_response = None
    try:
        api_response = api_instance.list_namespaced_service(namespace, field_selector='metadata.name={}'.format(name))
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return

    print('Create Quobyte Service {}'.format(name))
    try:
        api_instance.create_namespaced_service(namespace, load_body('{}/{}-svc.yaml'.format(config_path, name)))
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_configmap: %s\n" % e)


def set_version_in_spec(spec, version):
    kind = spec['kind']
    if kind == 'Deployment' or kind == 'DaemonSet':
        spec['spec']['template']['metadata']['labels']['version'] = spec['spec']['template']['metadata']['labels'][
            'version'].replace('VERSION', version)

        for c in spec['spec']['template']['spec']['containers']:
            c['image'] = c['image'].replace('VERSION', version)

    elif kind == 'Pod':
        spec['metadata']['labels']['version'] = spec['metadata']['labels']['version'].replace('VERSION', version)

        for c in spec['spec']['containers']:
            c['image'] = c['image'].replace('VERSION', version)


def create_daemonset(namespace, config_path, name, version):
    api_instance = client.ExtensionsV1beta1Api()
    api_response = None
    try:
        api_response = api_instance.list_namespaced_daemon_set(namespace,
                                                               field_selector='metadata.name={}'.format(name))
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return

    print('Create Quobyte DaemonSet {}'.format(name))
    body = load_body('{}/{}-ds.yaml'.format(config_path, name))
    set_version_in_spec(body, version)
    try:
        api_instance.create_namespaced_daemon_set(namespace, body)
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_configmap: %s\n" % e)


def label_node(node, key, value):
    api_instance = client.CoreV1Api()
    api_response = None
    try:
        api_response = api_instance.list_node(field_selector='metadata.name={}'.format(node),
                                              label_selector='{}={}'.format(key, value))
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_node: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return

    print('Label Node: {} with label {}={}'.format(node, key, value))
    body = [{"op": "add",
             "path": "/metadata/labels/{}".format(key),
             "value": value}]

    try:
        api_instance.patch_node(node, body)
    except ApiException as e:
        print("Exception when calling CoreV1Api->patch_node: %s\n" % e)


def load_config(path):
    with open(path, 'r', encoding='utf-8') as config_file:
        config_map = yaml.safe_load(config_file)
    return config_map


def deploy_registries(namespace, registries):
    print('Start Quobyte Registry deployment')
    api_instance = client.CoreV1Api()
    # TODO could fail as long we don't validate the config
    bootstrap_nodes = [reg for reg in registries if 'bootstrap' in reg]
    leftovers = [reg for reg in registries if 'bootstrap' not in reg]

    if len(bootstrap_nodes) == 0:
        raise ValueError('No bootstrap Node defined!')

    bootstrap_node = bootstrap_nodes[0]['node']

    success = False
    api_response = None
    try:
        api_response = api_instance.list_namespaced_pod(namespace,
                                                        label_selector='role=registry')
        if api_response.items[0].status.phase == 'Running':
            success = True
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
    except ValueError:
        # There is no Bootstrap node
        label_node(bootstrap_node, 'quobyte_registry', 'true')
        pass

    if (api_response is None) or (api_response.items[0].status.phase != 'Running'):
        success = wait_for_running_pod(api_instance, namespace, 'role=registry', 'Bootstrap registry')

    if not success:
        raise TimeoutError('Bootstrap Registry didn\'t come up...')

    # TODO check if they are already up
    for leftover in leftovers:
        label_node(leftover['node'], 'quobyte_registry', 'true')


def wait_for_running_pod(api_instance, namespace, label_selector, name):
    tries = 0
    # TODO Check why watch didn't worked...
    # TODO remove hardcoded time and hardcoded tries -> move into config
    while tries < 20:
        print('Waiting for {} to come up - tries: {}'.format(name, tries))
        api_response = None
        try:
            api_response = api_instance.list_namespaced_pod(namespace,
                                                            label_selector=label_selector)
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
        except ValueError:
            pass

        if api_response is not None and \
           api_response.items is not None and \
           api_response.items[0].status.container_statuses is not None:
            count_ready_container = len([cs for cs in api_response.items[0].status.container_statuses if cs.ready])
            count_spec_container = len(api_response.items[0].spec.containers)
            if api_response.items[0].status.phase == 'Running' and count_ready_container == count_spec_container:
                return True

        time.sleep(15)
        tries += 1

    return False


def deploy_api_webconsole(namespace, config_path, version):
    print('Start Quobyte API and Webconsole deployment')
    api_instance = client.ExtensionsV1beta1Api()

    api_response = None
    try:
        api_response = api_instance.list_namespaced_deployment(namespace,
                                                               field_selector='metadata.name=webconsole',
                                                               label_selector='role=webconsole')
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return

    body = load_body('{}/webconsole-deployment.yaml'.format(config_path))
    set_version_in_spec(body, version)

    try:
        api_instance.create_namespaced_deployment(namespace, body, )
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_pod: %s\n" % e)

    if not wait_for_running_pod(client.CoreV1Api(), namespace, 'role=webconsole', "API and Webconsole"):
        raise TimeoutError('API and Webconsole deployment didn\'t come up')


def deploy_metadata(namespace, config_path, nodes, version):
    print('Start Quobyte Metadata deployment')
    create_daemonset(namespace, config_path, 'metadata', version)

    for node in nodes:
        label_node(node['node'], 'quobyte_metadata', 'true')


def deploy_data(namespace, config_path, nodes, version):
    print('Start Quobyte Data deployment')
    create_daemonset(namespace, config_path, 'data', version)

    if nodes[0]['node'] == 'all':
        api_instance = client.CoreV1Api()
        api_response = None
        try:
            api_response = api_instance.list_node()
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_node: %s\n" % e)

        for node in api_response.items:
            label_node(node.metadata.name, 'quobyte_data', 'true')
        return

    for node in nodes:
        label_node(node['node'], 'quobyte_metadata', 'true')


def deploy_client(namespace, config_path, nodes, version):
    print('Start Quobyte Client deployment')
    create_daemonset(namespace, config_path, 'client', version)

    if nodes[0]['node'] == 'all':
        api_instance = client.CoreV1Api()
        api_response = None
        try:
            api_response = api_instance.list_node()
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_node: %s\n" % e)

        for node in api_response.items:
            label_node(node.metadata.name, 'quobyte_client', 'true')
        return

    for node in nodes:
        label_node(node['node'], 'quobyte_client', 'true')


def deploy_qmgmt_pod(namespace, config_path, version):
    print('Start Quobyte Managment Pod')
    api_instance = client.CoreV1Api()

    api_response = None
    try:
        api_response = api_instance.list_namespaced_pod(namespace, label_selector='role=qmgmt-pod')
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
    except ValueError:
        pass

    if api_response is not None:
        return
    body = load_body('{}/qmgmt-pod.yaml'.format(config_path))
    set_version_in_spec(body, version)

    try:
        api_instance.create_namespaced_pod(namespace, body)
    except ApiException as e:
        print("Exception when calling CoreV1Api->create_namespaced_pod: %s\n" % e)


def validate_config(config):
    # TODO validate config
    return


def parse_args():
    # TODO remove hardcoded path (add args)
    parser = argparse.ArgumentParser(description='Deploy Quobyte Cluster on top of Kubernetes')
    parser.add_argument('--config_file', default='./config.yaml', help='Path to the config_file')
    return parser.parse_args()


def main():
    opts = parse_args()
    quobyte_config = load_config(opts.config_file)
    validate_config(quobyte_config)

    config.load_kube_config()
    config_path = quobyte_config['kubernetes_files']['path']
    version = quobyte_config['version']
    namespace = quobyte_config['namespace']

    create_namespace(namespace)
    create_configmap(namespace, config_path)
    for svc in ['registry', 'webconsole', 'api']:
        create_svc(namespace, config_path, svc)

    create_daemonset(namespace, config_path, 'registry', version)
    deploy_registries(namespace, quobyte_config.get('registry', []))
    deploy_api_webconsole(namespace, config_path, version)
    deploy_metadata(namespace, config_path, quobyte_config.get('metadata', []), version)
    deploy_data(namespace, config_path, quobyte_config.get('data', []), version)
    deploy_client(namespace, config_path, quobyte_config.get('client', []), version)
    deploy_qmgmt_pod(namespace, config_path, version)

    print('Quobyte Cluster was successfully deployed')
    print('Validate state with:\n kubectl -n quobyte exec -it qmgmt-pod -- qmgmt -u api:7860 service list')


if __name__ == '__main__':
    main()
