from mock import call, patch, Mock, ANY

import unittest

import prod2lab.modify_bundle as mb


class TestModifyBundle(unittest.TestCase):
    def _get_layer_number(self, master, layer_name):
        for n, layer in enumerate(master["layers"]):
            if layer_name == layer["name"]:
                return n

    def _get_layer_bb_feature_number(
        self, master, feature_names, layer_name="openstack"
    ):
        layer = self._get_layer_number(master, layer_name)
        feature = None
        for name in feature_names:
            for i, feature in enumerate(master["layers"][layer]["features"]):
                if feature["name"] == name:
                    return i
        return None

    def _get_layer_bb_feature(self, master, feature_names, layer_name="openstack"):
        layer = self._get_layer_number(master, layer_name)
        feature = None
        for name in feature_names:
            for i, feature in enumerate(master["layers"][layer]["features"]):
                if feature["name"] == name:
                    return feature
        return None

    def test_get_layer_number_none(self):
        ret = mb.get_layer_number(self.master_bb, "wrong_layer")
        self.assertEqual(None, ret)

    def test_get_layer_number_existing(self):
        ret = mb.get_layer_number(self.master_bb, "openstack")
        self.assertEqual(3, ret)

    def test_get_layer_bb_feature_none(self):
        ret = mb.get_layer_bb_feature(self.master_bb, ["oxvn"])
        self.assertEqual(ret, None)

    def test_get_layer_bb_feature(self):
        ret = mb.get_layer_bb_feature(self.master_bb, ["ovn"])
        self.assertEqual(ret, {"name": "ovn", "options": {"data-port": "br-data:eth1"}})

    @patch("prod2lab.modify_bundle.get_layer_bb_feature")
    def test_fix_interface(self, mock_gf):
        master = self.master_bb
        mock_gf.return_value = self._get_layer_bb_feature(master, ["ovn"])
        self.assertEqual(
            mock_gf.return_value,
            {"name": "ovn", "options": {"data-port": "br-data:eth1"}},
        )
        ret = self._get_layer_bb_feature(mb.fix_interface(master), ["ovn"])
        self.assertEqual(ret, {"name": "ovn", "options": {"data-port": "br-data:ens4"}})

    def test_reduce_machines_bb(self):
        orig = len(self.placement_bb["machines"])
        _, ret = mb.reduce_machines({}, self.placement_bb, "vault", True)
        self.assertEqual(len(ret["machines"]), orig - 2)

    @patch("prod2lab.modify_bundle.get_layer_bb_feature")
    def test_modify_hacluster_bb(self, mock_gf):
        master = self.master_bb
        mock_gf.return_value = self._get_layer_bb_feature(master, ["ha"])
        _, ret = mb.modify_hacluster({}, master, True)
        ret = self._get_layer_bb_feature(ret, ["ha"])
        self.assertEqual(ret, {"name": "ha", "options": {"ha_count": 1}})

    def test_reduce_it_bb(self):
        special_cases = ["memcached", "vault"]
        apps = self.placement_bb["applications"]
        # for app, data in apps.items():
        ret = mb.reduce_it("rabbitmq-server", apps["rabbitmq-server"], special_cases)
        self.assertEqual(ret["num_units"], 1)
        ret = mb.reduce_it("vault", apps["vault"], special_cases)
        self.assertEqual(ret, {"num_units": 1, "to": [15]})

    def test_is_using_bundle_builder(self):
        ret = mb.is_using_bundle_builder(self.master_bb)
        self.assertEqual(ret, True)
        ret = mb.is_using_bundle_builder(self.master_not_bb)
        self.assertEqual(ret, False)

    @patch("prod2lab.modify_bundle.is_using_bundle_builder")
    def test_is_using_automatic_placement(self, mock_bb):
        mock_bb.return_value = True
        ret = mb.is_using_automatic_placement(self.master_bb)
        self.assertEqual(ret, False)
        mock_bb.return_value = True
        ret = mb.is_using_automatic_placement(self.master_bb_ap)
        self.assertEqual(ret, True)
        mock_bb.return_value = False
        ret = mb.is_using_automatic_placement(self.master_bb)
        self.assertEqual(ret, False)

    @property
    def master_bb(self):
        return {
            "project": {},
            "layers": [
                {"name": "baremetal"},
                {
                    "name": "maas",
                    "type": "maas",
                    "parent": "baremetal",
                    "config": {
                        "tweaks": ["nobond", "nobridge"],
                        "maas_vip": "1.2.3.4",
                        "postgresql_vip": "1.2.3.5",
                        "maas_config": {
                            "dnssec_validation": "no",
                            "upstream_dns": "1.2.3.6",
                        },
                    },
                },
                {
                    "name": "juju_maas_controller",
                },
                {
                    "name": "openstack",
                    "type": "openstack",
                    "parent": "juju_maas_controller",
                    "features": [
                        {
                            "name": "openstack",
                            "options": {
                                "designate-bind_forwarders": "1.2.3.7",
                            },
                        },
                        {"name": "ha", "options": {"ha_count": 3}},
                        {"name": "ovn", "options": {"data-port": "br-data:eth1"}},
                    ],
                    "config": {
                        "build_bundle": True,
                    },
                },
                {"name": "lma"},
                {"name": "lmacmr"},
                {
                    "name": "juju_openstack_controller",
                },
                {"name": "kubernetes"},
            ],
        }

    @property
    def placement_bb(self):
        return {
            "machines": {
                "15": {"constraints": "tags=vault zones=zone1"},
                "16": {"constraints": "tags=vault zones=zone2"},
                "17": {"constraints": "tags=vault zones=zone3"},
                "1000": {"constraints": "tags=fn zones=zone1"},
                "1001": {"constraints": "tags=fn zones=zone2"},
                "1002": {"constraints": "tags=fn zones=zone3"},
                "1003": {"constraints": "tags=fn zones=zone1"},
                "1004": {"constraints": "tags=fn zones=zone2"},
                "1005": {"constraints": "tags=fn zones=zone3"},
            },
            "applications": {
                "ceph-mon": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "ceph-osd": {
                    "num_units": 6,
                    "to": ["1000", "1001", "1002", "1003", "1004", "1005"],
                },
                "ceph-radosgw": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "aodh": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "barbican": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "gnocchi": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "cinder": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "glance": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "keystone": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "mysql-innodb-cluster": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "ovn-central": {
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "neutron-api": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "nova-cloud-controller": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "nova-compute": {
                    "num_units": 6,
                    "to": [1000, 1001, 1002, 1003, 1004, 1005],
                },
                "octavia": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "openstack-dashboard": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "placement": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "rabbitmq-server": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "heat": {"to": ["lxd:1000", "lxd:1001", "lxd:1002"]},
                "designate": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "designate-bind": {"num_units": 2, "to": ["lxd:1001", "lxd:1002"]},
                "memcached": {"to": ["designate-bind/0", "designate-bind/1"]},
                "ceilometer": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "glance-simplestreams-sync": {"to": ["lxd:1005"]},
                "easyrsa": {"to": ["lxd:1004"]},
                "etcd": {"to": ["lxd:1001", "lxd:1003", "lxd:1005"]},
                "vault": {"to": [15, 16, 17]},
            },
        }

    @property
    def master_not_bb(self):
        return {
            "project": {},
            "layers": [
                {"name": "baremetal"},
                {
                    "name": "maas",
                    "type": "maas",
                    "parent": "baremetal",
                    "config": {
                        "tweaks": ["nobond", "nobridge"],
                        "maas_vip": "1.2.3.4",
                        "postgresql_vip": "1.2.3.5",
                        "maas_config": {
                            "dnssec_validation": "no",
                            "upstream_dns": "1.2.3.6",
                        },
                    },
                },
                {
                    "name": "juju_maas_controller",
                },
                {
                    "name": "openstack",
                    "type": "openstack",
                    "parent": "juju_maas_controller",
                    "features": [
                        {
                            "name": "openstack",
                            "options": {
                                "designate-bind_forwarders": "1.2.3.7",
                            },
                        },
                        {"name": "ha", "options": {"ha_count": 3}},
                        {"name": "ovn", "options": {"data-port": "br-data:eth1"}},
                    ],
                    "config": {},
                },
                {"name": "lma"},
                {"name": "lmacmr"},
                {
                    "name": "juju_openstack_controller",
                },
                {"name": "kubernetes"},
            ],
        }

    @property
    def master_bb_ap(self):
        return {
            "project": {},
            "layers": [
                {"name": "baremetal"},
                {
                    "name": "maas",
                    "type": "maas",
                    "parent": "baremetal",
                    "config": {
                        "tweaks": ["nobond", "nobridge"],
                        "maas_vip": "1.2.3.4",
                        "postgresql_vip": "1.2.3.5",
                        "maas_config": {
                            "dnssec_validation": "no",
                            "upstream_dns": "1.2.3.6",
                        },
                    },
                },
                {
                    "name": "juju_maas_controller",
                },
                {
                    "name": "openstack",
                    "type": "openstack",
                    "parent": "juju_maas_controller",
                    "features": [
                        {
                            "name": "openstack",
                            "options": {
                                "designate-bind_forwarders": "1.2.3.7",
                            },
                        },
                        {"name": "ha", "options": {"ha_count": 3}},
                        {"name": "ovn", "options": {"data-port": "br-data:eth1"}},
                        {"name": "automatic-placement"},
                    ],
                    "config": {
                        "build_bundle": True,
                    },
                },
                {"name": "lma"},
                {"name": "lmacmr"},
                {
                    "name": "juju_openstack_controller",
                },
                {"name": "kubernetes"},
            ],
        }
