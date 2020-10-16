#!/usr/bin/env python3

import sys
import yaml


def get_layer_number(master, layer_name):
    for n, layer in enumerate(master["layers"]):
        if layer_name == layer["name"]:
            return n
    return -1


def remove_layer(master, layer_name):
    layer_number = get_layer_number(master, layer_name)
    if layer_number != -1:
        del master["layers"][layer_number]


with open(sys.argv[1]) as file:
    # master = yaml.load(file, Loader=yaml.FullLoader)
    master = yaml.load(file)
    tweaks = master["layers"][get_layer_number(master, "maas")]["config"]["tweaks"]
    tweaks.extend(["nomaasha", "nopgha", "nojujuha"])
    del master["layers"][1]["config"]["postgresql_vip"]
    del master["layers"][get_layer_number(master, "juju_maas_controller")]["config"][
        "ha"
    ]
    del master["layers"][get_layer_number(master, "juju_maas_controller")]["config"][
        "ha_timeout"
    ]
    remove_layer(master, "juju_maas_controller_bundle")
    remove_layer(master, "juju_openstack_controller_bundle")
    remove_layer(master, "lma")
    remove_layer(master, "lmacmr")

with open(sys.argv[2], "w") as outfile:
    yaml.dump(master, outfile, default_flow_style=False)
