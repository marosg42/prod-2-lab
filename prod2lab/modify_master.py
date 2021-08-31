#!/usr/bin/env python3

import sys
import yaml
import os


def get_layer_number(master, layer_name):
    for n, layer in enumerate(master["layers"]):
        if layer_name == layer["name"]:
            return n
    return None


def remove_layer(master, layer_name):
    layer_number = get_layer_number(master, layer_name)
    if layer_number:
        del master["layers"][layer_number]


def get_layer_feature(master, feature_names, layer_name="openstack"):
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


def modify_hacluster(master):
    feature = get_layer_feature(master, ["ha"])
    feature["options"]["ha_count"] = 1


def fix_nova_compute(master):
    feature = get_layer_feature(master, ["openstack"])
    if feature is None:
        return
    opts = feature["options"]
    if "reserved-host-memory" in opts:
        del opts["reserved-host-memory"]
    if "cpu-model" in opts:
        del opts["cpu-model"]


def fix_designate_bind_forwarders(master, charm="designate-bind"):
    feature = get_layer_feature(master, ["openstack"])
    if feature is not None:
        opts = feature["options"]
        opts["designate-bind_forwarders"] = "10.244.40.30"


def fix_interface(master):
    feature = get_layer_feature(master, ["ovs", "ovn"])
    if feature is None:
        return
    opts = feature["options"]
    opts["data-port"] = "br-data:ens4"


def fix_openstack(master):
    openstack = get_layer_number(master, "openstack")
    if not openstack:
        return
    EXTRA_OVERLAY = "overlay-openstack-prod2lab.yaml"
    output_p2l_overlay_output = os.path.join(
        os.path.dirname(output_master), EXTRA_OVERLAY
    )
    temp = {
        "applications": {
            "nova-compute": {"options": {"cpu-mode": "none", "reserved-host-memory": 0}}
        }
    }
    with open(output_p2l_overlay_output, "w") as outfile:
        yaml.dump(temp, outfile, default_flow_style=False)

    master["layers"][openstack]["config"]["bundles"].append(EXTRA_OVERLAY)

    modify_hacluster(master)
    fix_nova_compute(master)
    fix_interface(master)
    fix_designate_bind_forwarders(master)


def fix_kubernetes(master):
    feature = get_layer_feature(master, ["lma-kubernetes"], layer_name="kubernetes")
    if feature:
        master["layers"][get_layer_number(master, "kubernetes")]["features"].remove(
            feature
        )
    feature = get_layer_feature(master, ["nagios"], layer_name="kubernetes")
    if feature:
        master["layers"][get_layer_number(master, "kubernetes")]["features"].remove(
            feature
        )
    feature = get_layer_feature(master, ["ha"], layer_name="kubernetes")
    if feature:
        feature["options"]["ha_count"] = 1
    feature = get_layer_feature(master, ["livepatch"], layer_name="kubernetes")
    if feature:
        master["layers"][get_layer_number(master, "kubernetes")]["features"].remove(
            feature
        )


def fix_other_layers(master):

    maas_layer = get_layer_number(master, "maas")
    if maas_layer:
        tweaks = master["layers"][maas_layer]["config"]["tweaks"]
        tweaks.extend(["nomaasha", "nopgha", "nojujuha"])
        del master["layers"][get_layer_number(master, "maas")]["config"][
            "postgresql_vip"
        ]

    jmc = get_layer_number(master, "juju_maas_controller")
    if jmc:
        del master["layers"][jmc]["config"]["ha"]
        del master["layers"][jmc]["config"]["ha_timeout"]

    joc = get_layer_number(master, "juju_openstack_controller")
    if joc:
        del master["layers"][joc]["config"]["ha"]
        del master["layers"][joc]["config"]["ha_timeout"]

    remove_layer(master, "juju_maas_controller_bundle")
    remove_layer(master, "juju_openstack_controller_bundle")
    remove_layer(master, "lma")
    remove_layer(master, "lmacmr")


if __name__ == "__main__":
    input_master = sys.argv[1]
    output_master = sys.argv[2]

    master = yaml.load(open(input_master), Loader=yaml.FullLoader)

    fix_kubernetes(master)
    fix_openstack(master)
    fix_other_layers(master)

    # write to output files
    with open(output_master, "w") as outfile:
        yaml.dump(master, outfile, default_flow_style=False)
