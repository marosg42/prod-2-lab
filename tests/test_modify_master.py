from mock import call, patch, Mock, ANY

import unittest

import prod2lab.modify_master as mm


class TestModifyBundle(unittest.TestCase):
    def _get_layer_number(self, master, layer_name):
        for n, layer in enumerate(master["layers"]):
            if layer_name == layer["name"]:
                return n

    def _get_layer_feature_number(self, master, feature_names, layer_name="openstack"):
        layer = self._get_layer_number(master, layer_name)
        feature = None
        for name in feature_names:
            for i, feature in enumerate(master["layers"][layer]["features"]):
                if feature["name"] == name:
                    return i
        return None

    def _get_layer_feature(self, master, feature_names, layer_name="openstack"):
        layer = self._get_layer_number(master, layer_name)
        feature = None
        for name in feature_names:
            for i, feature in enumerate(master["layers"][layer]["features"]):
                if feature["name"] == name:
                    return feature
        return None

    def test_get_layer_number_none(self):
        ret = mm.get_layer_number(self.master, "wrong_layer")
        self.assertEqual(None, ret)

    def test_get_layer_number_existing(self):
        ret = mm.get_layer_number(self.master, "openstack")
        self.assertEqual(3, ret)

    def test_get_layer_feature_none(self):
        ret = mm.get_layer_feature(self.master, ["oxvn"])
        self.assertEqual(ret, None)

    def test_get_layer_feature(self):
        ret = mm.get_layer_feature(self.master, ["ovn"])
        self.assertEqual(ret, {"name": "ovn", "options": {"data-port": "br-data:eth1"}})

    @patch("prod2lab.modify_master.get_layer_feature")
    def test_fix_interface(self, mock_gf):
        master = self.master
        mock_gf.return_value = self._get_layer_feature(master, ["ovn"])
        self.assertEqual(
            mock_gf.return_value,
            {"name": "ovn", "options": {"data-port": "br-data:eth1"}},
        )
        mm.fix_interface(master)
        ret = self._get_layer_feature(master, ["ovn"])
        self.assertEqual(ret, {"name": "ovn", "options": {"data-port": "br-data:ens4"}})

    @patch("prod2lab.modify_master.get_layer_feature")
    def test_modify_hacluster(self, mock_gf):
        master = self.master
        mock_gf.return_value = self._get_layer_feature(master, ["ha"])
        mm.modify_hacluster(master)
        ret = self._get_layer_feature(master, ["ha"])
        self.assertEqual(ret, {"name": "ha", "options": {"ha_count": 1}})

    def test_fix_nova_compute(self):
        master = self.master
        mm.fix_nova_compute(master)
        # FIXME
        # self.assertEqual(
        #     placement["applications"]["nova-compute"]["options"]["cpu-mode"], "none"
        # )
        # self.assertEqual(
        #     placement["applications"]["nova-compute"]["options"][
        #         "reserved-host-memory"
        #     ],
        #     0,
        # )

    def test_fix_designate_bind_forwarders(self):
        master = self.master
        mm.fix_designate_bind_forwarders(master)
        feature = self._get_layer_feature(master, ["openstack"])
        print(feature)
        self.assertEqual(
            feature["options"]["designate-bind_forwarders"],
            "10.244.40.30",
        )

    @property
    def master(self):
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
