#!/usr/bin/env python3

import sys
import yaml

def get_layer_number(master, layer_name):
    for n, layer in enumerate(master['layers']):
        if layer_name == layer['name']:
            return n


with open(sys.argv[1]) as file:
    #master = yaml.load(file, Loader=yaml.FullLoader)
    master = yaml.load(file)
    tweaks = master['layers'][get_layer_number(master, 'maas')]['config']['tweaks']
    tweaks.extend(['nomaasha', 'nopgha', 'nojujuha'])
    del master['layers'][1]['config']['postgresql_vip']
    master['layers'][1]['config']['maas_config']['upstream_dns'] = "10.244.40.1"
    del master['layers'][get_layer_number(master, 'juju_maas_controller')]['config']['ha']
    del master['layers'][get_layer_number(master, 'juju_maas_controller')]['config']['ha_timeout']
    del master['layers'][get_layer_number(master, 'juju_maas_controller_bundle')]
    del master['layers'][get_layer_number(master, 'juju_openstack_controller_bundle')]

with open(sys.argv[2], 'w') as outfile:
    yaml.dump(master, outfile)
