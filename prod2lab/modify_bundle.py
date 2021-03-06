#!/usr/bin/env python3

import sys
import yaml
import re
import random
import os

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
    "nova-compute",
    "nova-compute-kvm",
    "mysql-innodb-cluster",
    "ovn-central",
]
special_cases = ["memcached", "vault"]


def get_layer_number(master, layer_name):
    for n, layer in enumerate(master["layers"]):
        if layer_name == layer["name"]:
            return n


def get_layer_bb_feature(master, feature_names, layer_name="openstack"):
    layer = get_layer_number(master, layer_name)
    feature = None
    for name in feature_names:
        feature = next(
            (
                item
                for item in master["layers"][layer]["features"]
                if item["name"] == name
            ),
            None,
        )
        if feature is not None:
            return feature
    return feature


def remove_application_from_machines(bundle, app):
    machines = bundle["machines"]
    to_delete = []
    for machine, data in machines.items():
        if app in data["constraints"]:
            to_delete.append(machine)
    for machine in to_delete:
        print(f"Removing {app} from machine {machine}")
        del machines[machine]


def reduce_machines(bundle, placement, app, bb, number=1):
    to_modify = placement if bb else bundle
    machines = to_modify["machines"]
    app_located_in = []
    for machine, data in machines.items():
        if app in data["constraints"]:
            app_located_in.append(machine)
    for machine in app_located_in[number:]:
        print(f"Removing {app} from machine {machine}")
        del machines[machine]


def remove_application_from_applications(bundle, app):
    if app in bundle["applications"]:
        print(f"Removing application {app} from the bundle")
        del bundle["applications"][app]


def remove_application_from_relations(bundle, app):
    relations = bundle["relations"]
    to_delete = []
    for n, relation in enumerate(relations):
        if re.search(app, relation[0]) or re.search(app, relation[1]):
            to_delete.append(n)
    for relation in reversed(to_delete):
        print(f"Removing relation {relations[relation]}")
        del relations[relation]


def modify_hacluster(bundle, master, bb):
    if bb:
        feature = get_layer_bb_feature(master, ["ha"])
        feature["options"]["ha_count"] = 1
    else:
        apps = bundle["applications"]
        for app, data in apps.items():
            if re.search("hacluster-", app):
                print(f"Modify cluster_count to 1 in {app}")
                data.setdefault("options", {})
                data["options"]["cluster_count"] = 1


def reduce_it(app, data, special):
    print(f"Reducing number of units in {app} to 1")
    num = len(data["to"])
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


def reduce_num_units(bundle, placement, bb, dont_reduce, special):
    to_modify = placement if bb else bundle
    apps = to_modify["applications"]
    for app, data in apps.items():
        if app in dont_reduce:
            continue
        if data.get("num_units", 0) > 1 or bb:
            reduce_it(app, data, special)


def fix_nova_compute(bundle, master, placement, bb, ap, charm="nova-compute-kvm"):
    if bb:
        charm = "nova-compute"
    print(f"Fixing {charm}")
    if bb:
        feature = get_layer_bb_feature(master, ["openstack"])
        if feature is None:
            return
        opts = feature["options"]
        if "reserved-host-memory" in opts:
            del opts["reserved-host-memory"]
        if "cpu-model" in opts:
            del opts["cpu-model"]
        if not ap:
            placement["applications"][charm]["options"] = placement["applications"][
                charm
            ].get("options", {})
            placement["applications"]["nova-compute"]["options"]["cpu-mode"] = "none"
            placement["applications"]["nova-compute"]["options"][
                "reserved-host-memory"
            ] = 0
    else:
        nova = bundle["applications"][charm]["options"]
        if "reserved-host-memory" in nova:
            del nova["reserved-host-memory"]
        if "cpu-model" in nova:
            del nova["cpu-model"]
        if "cpu-mode" in nova:
            del nova["cpu-mode"]


def fix_data_port(bundle, charm="neutron-gateway"):
    print(f"Fixing {charm}")
    if charm not in bundle["applications"]:
        return
    opt = bundle["applications"][charm]["options"]
    if "data-port" in opt:
        opt["data-port"] = "br-data:ens4"


def fix_bridge_interface_mappings(bundle, charm="ovn-chassis"):
    print(f"Fixing {charm}")
    if charm not in bundle["applications"]:
        return
    opt = bundle["applications"][charm]["options"]
    if "bridge-interface-mappings" in opt:
        opt["bridge-interface-mappings"] = "br-data:ens4"


def fix_designate_bind_forwarders(bundle, master, bb, charm="designate-bind"):
    print(f"Fixing {charm}")
    if bb:
        feature = get_layer_bb_feature(master, ["openstack"])
        if feature is not None:
            opts = feature["options"]
            opts["designate-bind_forwarders"] = "10.244.40.30"
    else:
        if charm not in bundle["applications"]:
            return bundle
        opt = bundle["applications"][charm]["options"]
        if "forwarders" in opt:
            opt["forwarders"] = "10.244.40.30"


def fix_cluster_size(placement, charm):
    print(f"Fixing {charm}")
    if charm in placement["applications"]:
        placement["applications"][charm]["options"] = placement["applications"][
            charm
        ].get("options", {})
        placement["applications"][charm]["options"]["min-cluster-size"] = 1


def fix_interface(master):
    print("Fixing network interface for OVS/OVN")
    feature = get_layer_bb_feature(master, ["ovs", "ovn"])
    if feature is None:
        return
    opts = feature["options"]
    opts["data-port"] = "br-data:ens4"


def is_using_bundle_builder(master, layer_name):
    layer = get_layer_number(master, layer_name)
    return master["layers"][layer]["config"].get("build_bundle", False)


def is_using_automatic_placement(master, layer_name):
    if not is_using_bundle_builder(master, layer_name):
        return False
    layer = get_layer_number(master, layer_name)
    return (
        True
        if {"name": "automatic-placement"} in master["layers"][layer]["features"]
        else False
    )


def fix_openstack(bb, ap, master, bundle, placement):
    if bb and ap:
        EXTRA_OVERLAY = "overlay-openstack-prod2lab.yaml"
        output_p2l_overlay_output = os.path.join(
            os.path.dirname(output_master), EXTRA_OVERLAY
        )
        temp = {
            "applications": {
                "nova-compute": {
                    "options": {"cpu-mode": "none", "reserved-host-memory": 0}
                }
            }
        }
        with open(output_p2l_overlay_output, "w") as outfile:
            yaml.dump(temp, outfile, default_flow_style=False)
        openstack = get_layer_number(master, "openstack")
        master["layers"][openstack]["config"]["bundles"].append(EXTRA_OVERLAY)

    if not bb:
        for app in remove_applications:
            remove_application_from_machines(bundle, app)
            remove_application_from_applications(bundle, app)
            remove_application_from_relations(bundle, app)

    if not ap:
        for app in reduce_application_machines:
            reduce_machines(bundle, placement, app, bb)
        reduce_num_units(bundle, placement, bb, dont_reduce_num_units, special_cases)
        if bb:
            fix_cluster_size(placement, "mysql")
            fix_cluster_size(placement, "rabbitmq-server")

    modify_hacluster(bundle, master, bb)
    fix_nova_compute(bundle, master, placement, bb, ap)

    if not bb:
        fix_data_port(bundle)
        fix_bridge_interface_mappings(bundle, charm="ovn-chassis")
        fix_bridge_interface_mappings(bundle, charm="octavia-ovn-chassis")
    else:
        fix_interface(master)

    fix_designate_bind_forwarders(bundle, master, bb, charm="designate-bind")


def fix_kubernetes(master, bundle, placement):
    feature = get_layer_bb_feature(master, ["lma-kubernetes"], layer_name="kubernetes")
    if feature:
        master["layers"][get_layer_number(master, "kubernetes")]["features"].remove(
            feature
        )
    feature = get_layer_bb_feature(master, ["nagios"], layer_name="kubernetes")
    if feature:
        master["layers"][get_layer_number(master, "kubernetes")]["features"].remove(
            feature
        )
    feature = get_layer_bb_feature(master, ["ha"], layer_name="kubernetes")
    if feature:
        feature["options"]["ha_count"] = 1


if __name__ == "__main__":
    k8s = sys.argv[-1] == "k8s"

    input_master = sys.argv[1]
    output_master = sys.argv[2]
    input_bundle = sys.argv[3]
    output_bundle = sys.argv[4]
    input_placement = sys.argv[5]
    output_placement = sys.argv[6]

    master = yaml.load(open(input_master), Loader=yaml.FullLoader)

    bb = is_using_bundle_builder(master, "kubernetes" if k8s else "openstack")
    ap = is_using_automatic_placement(master, "kubernetes" if k8s else "openstack")

    if bb:
        placement = (
            None if ap else yaml.load(open(input_placement), Loader=yaml.FullLoader)
        )
        bundle = None
    else:
        bundle = yaml.load(open(input_bundle), Loader=yaml.FullLoader)
        placement = None

    if k8s:
        if not bb or not ap:
            raise ValueError(
                "Bundle builder and automatic placement required in Kubernetes layer, legacy setup not supported!"
            )
        fix_kubernetes(master, bundle, placement)
    else:
        fix_openstack(bb, ap, master, bundle, placement)

    # write to output files
    if bb:
        with open(output_master, "w") as outfile:
            yaml.dump(master, outfile, default_flow_style=False)
        if not ap:
            with open(output_placement, "w") as outfile:
                yaml.dump(placement, outfile, default_flow_style=False)
    else:
        with open(output_bundle, "w") as outfile:
            yaml.dump(bundle, outfile, default_flow_style=False)
