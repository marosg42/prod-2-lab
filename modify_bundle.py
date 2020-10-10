#!/usr/bin/env python3

import sys
import yaml
import re
import random

remove_applications = [
    "apache2",
    "apache",
    "mongodb",
    "grafana",
    "nagios",
    "elastic",
    "prometheus",
    "graylog",
    "logrotate",
    "graylog-mongodb",
    "elasticsearch",
    "filebeat",
    "openstack-service-checks",
    "nrpe-host",
    "nrpe-container",
    "landscape-client",
    "prometheus",
    "prometheus-openstack-exporter",
    "telegraf",
    "telegraf-prometheus",
    "lldpd",
    "canonical-livepatch",
    "thruk-agent",
    "prometheus-ceph-exporter",
]

reduce_application_machines = ["vault"]

dont_reduce_num_units = [
    "ceph-mon",
    "ceph-osd",
    "neutron-gateway",
    "nova-compute-kvm",
    "mysql-innodb-cluster",
    "ovn-central",
]
special_cases = ["memcached", "vault"]


def get_layer_number(master, layer_name):
    for n, layer in enumerate(master["layers"]):
        if layer_name == layer["name"]:
            return n


def remove_application_from_machines(bundle, app):
    machines = bundle["machines"]
    to_delete = []
    for machine, data in machines.items():
        if app in data["constraints"]:
            to_delete.append(machine)
    for machine in to_delete:
        print(f"Removing {app} from machine {machine}")
        del machines[machine]
    return bundle


def reduce_machines(bundle, app, number=1):
    machines = bundle["machines"]
    app_located_in = []
    for machine, data in machines.items():
        if app in data["constraints"]:
            app_located_in.append(machine)
    for machine in app_located_in[number:]:
        print(f"Removing {app} from machine {machine}")
        del machines[machine]
    return bundle


def remove_application_from_applications(bundle, app):
    if app in bundle["applications"]:
        print(f"Removing application {app} from the bundle")
        del bundle["applications"][app]
    return bundle


def remove_application_from_relations(bundle, app):
    relations = bundle["relations"]
    to_delete = []
    for n, relation in enumerate(relations):
        if re.search(app, relation[0]) or re.search(app, relation[1]):
            to_delete.append(n)
    for relation in reversed(to_delete):
        print(f"Removing relation {relations[relation]}")
        del relations[relation]
    return bundle


def modify_hacluster(bundle):
    apps = bundle["applications"]
    for app, data in apps.items():
        if re.search("hacluster-", app):
            print(f"Modify cluster_count to 1 in {app}")
            data.setdefault("options", {})
            data["options"]["cluster_count"] = 1
    return bundle


def reduce_num_units(bundle, dont_reduce, special):
    apps = bundle["applications"]
    for app, data in apps.items():
        if app in dont_reduce:
            continue
        if data.get("num_units", 0) > 1:
            print(f"Reducing number of units in {app} to 1")
            num = data["num_units"]
            data["num_units"] = 1
            if app in special:
                data["to"] = [data["to"][0]]
            else:
                rnd = random.randint(0, num - 1)
                data["to"] = [data["to"][rnd]]
            if "options" in data:
                if "min-cluster-size" in data["options"]:
                    print(f"Setting min-cluster-size to 1 for {app}")
                    data["options"]["min-cluster-size"] = 1
    return bundle


def fix_nova_compute(bundle, charm="nova-compute-kvm"):
    print(f"Fixing {charm}")
    nova = bundle["applications"][charm]["options"]
    if "reserved-host-memory" in nova:
        del nova["reserved-host-memory"]
    if "cpu-model" in nova:
        del nova["cpu-model"]
    if "cpu-mode" in nova:
        del nova["cpu-mode"]
    return bundle


def fix_data_port(bundle, charm="neutron-gateway"):
    print(f"Fixing {charm}")
    if charm not in bundle["applications"]:
        return bundle
    opt = bundle["applications"][charm]["options"]
    if "data-port" in opt:
        opt["data-port"] = "br-data:ens4"
    return bundle


def fix_bridge_interface_mappings(bundle, charm="ovn-chassis"):
    print(f"Fixing {charm}")
    if charm not in bundle["applications"]:
        return bundle
    opt = bundle["applications"][charm]["options"]
    if "bridge-interface-mappings" in opt:
        opt["bridge-interface-mappings"] = "br-data:ens4"
    return bundle


def fix_designate_bind_forwarders(bundle, charm="designate-bind"):
    print(f"Fixing {charm}")
    if charm not in bundle["applications"]:
        return bundle
    opt = bundle["applications"][charm]["options"]
    if "forwarders" in opt:
        opt["forwarders"] = "10.244.40.30"
    return bundle


k8s = True if len(sys.argv) == 4 else False
with open(sys.argv[1]) as file:
    # bundle = yaml.load(file, Loader=yaml.FullLoader)
    bundle = yaml.load(file)

    for app in remove_applications:
        bundle = remove_application_from_machines(bundle, app)
        bundle = remove_application_from_applications(bundle, app)
        bundle = remove_application_from_relations(bundle, app)
    for app in reduce_application_machines:
        bundle = reduce_machines(bundle, app)

    bundle = modify_hacluster(bundle)
    bundle = reduce_num_units(bundle, dont_reduce_num_units, special_cases)
    if not k8s:
        bundle = fix_nova_compute(bundle)
    bundle = fix_data_port(bundle)
    bundle = fix_bridge_interface_mappings(bundle, charm="ovn-chassis")
    bundle = fix_bridge_interface_mappings(bundle, charm="octavia-ovn-chassis")
    bundle = fix_designate_bind_forwarders(bundle, charm="designate-bind")

with open(sys.argv[2], "w") as outfile:
    yaml.dump(bundle, outfile, default_flow_style=False)
