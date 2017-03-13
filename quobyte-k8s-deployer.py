#!/usr/bin/env python3

from kubernetes import client, config
from kubernetes.client.rest import ApiException
import yaml
import time
import argparse
import json


def set_mount_opts_in_spec(spec, opts):
    if opts == '':
        return
    for c in spec['spec']['template']['spec']['containers']:
        c['env'].append({'name': 'OPTS', 'value': opts})


def set_resources_in_spec(spec, resources):
    if resources == '':
        return
    for c in spec['spec']['template']['spec']['containers']:
        c['resources'] = resources
        if 'command' in c:
            command = c['command'][len(c['command']) - 1]
            command = command.replace('${MIN_MEM}', resources['requests'][
                                      'memory'].rstrip('i').lower())
            command = command.replace('${MAX_MEM}', resources['limits'][
                                      'memory'].rstrip('i').lower())
            c['command'][len(c['command']) - 1] = command


def get_all_nodes():
    nodes = []
    api_instance = client.CoreV1Api()
    try:
        api_response = api_instance.list_node()
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_node: %s\n" % e)
        return nodes

    # TODO use simple list ?
    for node in api_response.items:
        nodes.append(node.metadata.name)

    return nodes


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

    if api_response is not None and len(api_response.items) > 0:
        print('Node: {} already labeled with {}={}'.format(node, key, value))
        return

    print('Label Node: {} with label {}={}'.format(node, key, value))
    try:
        api_instance.patch_node(node, {"metadata": {"labels": {key: value}}})
    except ApiException as e:
        print("Exception when calling CoreV1Api->patch_node: %s\n" % e)


def load_config(path):
    with open(path, 'r', encoding='utf-8') as config_file:
        config_map = yaml.safe_load(config_file)
    return config_map


def valid_config(config):
    # TODO validate config
    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description='Deploy Quobyte Cluster on top of Kubernetes')
    parser.add_argument('--config_file', default='./config.yaml',
                        help='Path to the config_file')
    return parser.parse_args()


class QuobyteDeployer:

    def __init__(self, quobyte_config):
        self.config_path = quobyte_config['kubernetes_files']
        self.version = quobyte_config['version']
        self.namespace = quobyte_config['namespace']
        self.quobyte_config = quobyte_config

    def deploy(self):
        self.create_namespace()
        for svc in ['registry', 'webconsole', 'api']:
            self.create_svc(svc)

        self.deploy_registries()
        self.deploy_api_webconsole()
        self.deploy_metadata()
        self.deploy_data()
        self.deploy_client()
        self.deploy_qmgmt_pod()

        print('Quobyte Cluster was successfully deployed')
        print('Validate state with:\n kubectl -n quobyte exec -it qmgmt-pod -- qmgmt -u api:7860 service list')

    def create_namespace(self):
        api_instance = client.CoreV1Api()
        api_response = None
        try:
            api_response = api_instance.list_namespace(
                field_selector='metadata.name=quobyte')
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_namespace: %s\n" % e)
            # raise
        except ValueError:
            pass

        if api_response is not None and len(api_response.items) > 0:
            print('Namespace {} already exists'.format(self.namespace))
            return

        print('Create Namespace: {}'.format(self.namespace))
        body = client.V1Namespace()
        body.api_version = 'v1'
        body.kind = 'Namespace'
        metadata = client.V1ObjectMeta()
        metadata.name = self.namespace
        body.metadata = metadata

        try:
            api_instance.create_namespace(body)
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)

    def create_svc(self, name):
        api_instance = client.CoreV1Api()
        api_response = None
        try:
            api_response = api_instance.list_namespaced_service(self.namespace,
                                                                field_selector='metadata.name={}'.format(name))
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)
        except ValueError:
            pass

        if api_response is not None and len(api_response.items) > 0:
            print("Quobyte Service {} already exist".format(name))
            return

        print('Create Quobyte Service {}'.format(name))
        try:
            api_instance.create_namespaced_service(self.namespace,
                                                   self.load_body('{}-svc'.format(name)))
        except ApiException as e:
            print(
                "Exception when calling CoreV1Api->create_namespaced_configmap: %s\n" % e)

    def get_nodes_for_quobyte_service(self, service):
        if service not in self.quobyte_config or self.quobyte_config[service] is None:
            return self.get_nodes_for_quobyte_service('default')

        nodes = self.quobyte_config[service].get('nodes', [])
        if len(nodes) > 0 and nodes[0] == 'all':
            return get_all_nodes()
        if len(nodes) > 0:
            return nodes

        return self.get_nodes_for_quobyte_service('default')

    def deploy_registries(self):
        print('Start Quobyte Registry deployment')
        self.create_daemonset('registry')
        api_instance = client.CoreV1Api()
        nodes = self.get_nodes_for_quobyte_service('registry')
        bootstrap_node = nodes[0]

        if len(bootstrap_node) == 0:
            raise ValueError('No bootstrap Node defined!')

        success = False
        api_response = None
        try:
            api_response = api_instance.list_namespaced_pod(self.namespace,
                                                            label_selector='role=registry')
            if len(api_response.items) > 0 and api_response.items[0].status.phase == 'Running':
                success = True
            else:
                label_node(bootstrap_node, 'quobyte_registry', 'true')
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
        except ValueError:
            pass

        if api_response is None or len(api_response.items) < 1 or (api_response.items[0].status.phase != 'Running'):
            success = self.wait_for_running_pod(
                api_instance, 'role=registry', 'Bootstrap registry')

        if not success:
            raise TimeoutError('Bootstrap Registry didn\'t come up...')

        # TODO check if they are already up
        for leftover in nodes[1::]:
            label_node(leftover, 'quobyte_registry', 'true')

    def wait_for_running_pod(self, api_instance, label_selector, name):
        tries = 0
        # TODO Check why watch didn't worked...
        # TODO remove hardcoded time and hardcoded tries -> move into config
        backoff = 1
        while tries < 20:
            print(
                'Waiting for {} to come up - tries: {} - backoff: {}'.format(name, tries, backoff))
            api_response = None
            try:
                api_response = api_instance.list_namespaced_pod(self.namespace,
                                                                label_selector=label_selector)
            except ApiException as e:
                print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
            except ValueError:
                pass

            if api_response is not None and \
                    api_response.items is not None and \
                    len(api_response.items) > 0 and \
                    api_response.items[0].status.container_statuses is not None:
                count_ready_container = len([cs for cs in api_response.items[
                                            0].status.container_statuses if cs.ready])
                count_spec_container = len(
                    api_response.items[0].spec.containers)
                if api_response.items[0].status.phase == 'Running' and count_ready_container == count_spec_container:
                    return True

            backoff *= 2
            time.sleep(backoff)
            tries += 1

        return False

    def deploy_api_webconsole(self):
        print('Start Quobyte API and Webconsole deployment')
        api_instance = client.ExtensionsV1beta1Api()

        api_response = None
        try:
            api_response = api_instance.list_namespaced_deployment(self.namespace,
                                                                   field_selector='metadata.name=webconsole',
                                                                   label_selector='role=webconsole')
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
        except ValueError:
            pass

        if api_response is not None and len(api_response.items) > 0:
            print('Quobyte Webconsole and API already exist')
            return

        body = self.load_body('webconsole-deployment')
        self.set_version_in_spec(body)

        try:
            api_instance.create_namespaced_deployment(self.namespace, body, )
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespaced_pod: %s\n" % e)

        if not self.wait_for_running_pod(client.CoreV1Api(), 'role=webconsole', "API and Webconsole"):
            raise TimeoutError('API and Webconsole deployment didn\'t come up')

    def deploy_metadata(self):
        print('Start Quobyte Metadata deployment')
        self.create_daemonset('metadata')

        for node in self.get_nodes_for_quobyte_service('metadata'):
            label_node(node, 'quobyte_metadata', 'true')

    def deploy_data(self):
        print('Start Quobyte Data deployment')
        self.create_daemonset('data')

        for node in self.get_nodes_for_quobyte_service('data'):
            label_node(node, 'quobyte_data', 'true')

    def deploy_client(self):
        print('Start Quobyte Client deployment')
        self.create_daemonset('client')

        for node in self.get_nodes_for_quobyte_service('client'):
            label_node(node, 'quobyte_client', 'true')

    def deploy_qmgmt_pod(self):
        print('Start Quobyte Managment Pod')
        api_instance = client.CoreV1Api()

        api_response = None
        try:
            api_response = api_instance.list_namespaced_pod(
                self.namespace, label_selector='role=qmgmt-pod')
        except ApiException as e:
            print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
        except ValueError:
            pass

        if api_response is not None and len(api_response.items) > 0:
            print('qmgmt Pod already exist')
            return
        body = self.load_body('qmgmt-pod')
        self.set_version_in_spec(body)

        try:
            api_instance.create_namespaced_pod(self.namespace, body)
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespaced_pod: %s\n" % e)

    def set_disks_in_spec(self, spec, name):
        if name not in self.quobyte_config or self.quobyte_config[name] is None or 'disks' not in self.quobyte_config[name]:
            return

        c = spec['spec']['template']['metadata']['annotations']['pod.beta.kubernetes.io/init-containers']
        init_containers = json.loads(c)
        init_containers[0]['env'] = [{'name': 'DISKS', 'value': ','.join(self.quobyte_config[name]['disks'])}]
        spec['spec']['template']['metadata']['annotations']['pod.beta.kubernetes.io/init-containers'] = json.dumps(init_containers)

    def set_version_in_spec(self, spec):
        kind = spec['kind']
        if kind == 'Deployment' or kind == 'DaemonSet':
            spec['spec']['template']['metadata']['labels']['version'] = spec['spec']['template']['metadata']['labels'][
                'version'].replace('VERSION', self.version)

            for c in spec['spec']['template']['spec']['containers']:
                c['image'] = c['image'].replace('VERSION', self.version)

        elif kind == 'Pod':
            spec['metadata']['labels']['version'] = spec['metadata']['labels']['version'].replace('VERSION',
                                                                                                  self.version)

            for c in spec['spec']['containers']:
                c['image'] = c['image'].replace('VERSION', self.version)

    def create_daemonset(self, name):
        api_instance = client.ExtensionsV1beta1Api()
        api_response = None
        try:
            # TODO we could here check if specification is consistent (updates)
            api_response = api_instance.list_namespaced_daemon_set(self.namespace,
                                                                   field_selector='metadata.name={}'.format(name))
        except ApiException as e:
            print("Exception when calling CoreV1Api->create_namespace: %s\n" % e)
        except ValueError:
            pass

        if api_response is not None and len(api_response.items) > 0:
            print('Dameonset {} already exists'.format(name))
            return

        print('Create Quobyte DaemonSet {}'.format(name))
        body = self.load_body('{}-ds'.format(name))
        self.set_disks_in_spec(body, name)
        self.set_version_in_spec(body)

        set_resources_in_spec(
            body, self.get_resource_for_quobyte_service(name))
        mount_opts = self.get_mount_opts_for_quobyte_service(name)
        if mount_opts != '':
            set_mount_opts_in_spec(body, mount_opts)
        try:
            api_instance.create_namespaced_daemon_set(self.namespace, body)
        except ApiException as e:
            print(
                "Exception when calling CoreV1Api->create_namespaced_configmap: %s\n" % e)

    def get_mount_opts_for_quobyte_service(self, service):
        if service not in self.quobyte_config or self.quobyte_config[service] is None:
            return ''
        return self.quobyte_config[service].get('mount_opts', '')

    def get_resource_for_quobyte_service(self, service):
        if service not in self.quobyte_config or self.quobyte_config[service] is None:
            return self.quobyte_config['default'].get('resources', {})

        resources = self.quobyte_config[service].get('resources', {})
        if len(resources) == 0:
            return self.quobyte_config['default'].get('resources', {})
        return resources

    def load_body(self, name):
        file_name = '{}/{}.yaml'.format(self.config_path, name)

        with open(file_name, 'r', encoding='utf-8') as content:
            body = yaml.safe_load(content)
        if body is None:
            raise ValueError('Body of file {} is empty'.format(file_name))

        return body


def main():
    opts = parse_args()
    quobyte_config = load_config(opts.config_file)
    if not valid_config(quobyte_config):
        print('Configuration is not valid')
        return

    if 'incluster' in quobyte_config and quobyte_config['incluster']:
        print('Load configuration for in cluster')
        config.load_incluster_config()
    elif 'kubeconfig' in quobyte_config:
        print('Load configuration from {}'.format(
            quobyte_config['kubeconfig']))
        config.new_client_from_config(config_file=quobyte_config['kubeconfig'])
    else:
        print('Load default configuration')
        config.load_kube_config()

    QuobyteDeployer(quobyte_config).deploy()


if __name__ == '__main__':
    main()
