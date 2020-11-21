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
        apps = self.placement_bb["applications"]
        # for app, data in apps.items():
        ret = mb.reduce_it("rabbitmq-server", apps["rabbitmq-server"], mb.special_cases)
        self.assertEqual(ret["num_units"], 1)
        ret = mb.reduce_it("vault", apps["vault"], mb.special_cases)
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

    def test_fix_cluster_size(self):
        ret = mb.fix_cluster_size(self.placement_bb, "rabbitmq-server")
        self.assertEqual(
            1, ret["applications"]["rabbitmq-server"]["options"]["min-cluster-size"]
        )

    def test_fix_nova_compute(self):
        _, _, ret = mb.fix_nova_compute(
            None, self.master_bb, self.placement_bb, True, False
        )
        self.assertEqual(
            ret["applications"]["nova-compute"]["options"]["cpu-mode"], "none"
        )
        self.assertEqual(
            ret["applications"]["nova-compute"]["options"]["reserved-host-memory"], 0
        )
        ret = mb.fix_nova_compute(
            None, self.master_bb_ap, self.placement_bb, True, True
        )

    def test_fix_designate_bind_forwarders(self):
        _, ret = mb.fix_designate_bind_forwarders(None, self.master_bb, True)
        feature = self._get_layer_bb_feature(ret, ["openstack"])
        self.assertEqual(
            feature["options"]["designate-bind_forwarders"],
            "10.244.40.30",
        )
        _, ret = mb.fix_designate_bind_forwarders(None, self.master_bb_ap, True)
        feature = self._get_layer_bb_feature(ret, ["openstack"])
        self.assertEqual(
            feature["options"]["designate-bind_forwarders"],
            "10.244.40.30",
        )
        ret, _ = mb.fix_designate_bind_forwarders(self.bundle, None, False)
        self.assertEqual(
            ret["applications"]["designate-bind"]["options"]["forwarders"],
            "10.244.40.30",
        )

    def test_remove_application_from_machines(self):
        bundle = self.bundle
        for app in mb.remove_applications:
            bundle = mb.remove_application_from_machines(bundle, app)
        for i in [0, 1, 5, 9, 10]:
            self.assertIn(str(i), self.bundle["machines"])
            self.assertNotIn(str(i), bundle["machines"])

    def test_remove_application_from_applications(self):
        bundle = self.bundle
        for app in mb.remove_applications:
            bundle = mb.remove_application_from_applications(bundle, app)
        for app in mb.remove_applications:
            if app in self.bundle["applications"]:
                self.assertNotIn(app, bundle["applications"])

    def test_remove_application_from_relations(self):
        bundle = self.bundle
        for app in mb.remove_applications:
            bundle = mb.remove_application_from_relations(bundle, app)
        self.assertGreater(len(self.bundle["relations"]), 1)
        self.assertEqual(len(bundle["relations"]), 1)

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

    @property
    def bundle(self):
        return {
            "series": "bionic",
            "machines": {
                "0": {"constraints": "tags=nagios", "series": "bionic"},
                "1": {"constraints": "tags=grafana", "series": "bionic"},
                "5": {"constraints": "tags=elastic zones=zone1"},
                "9": {"constraints": "tags=prometheus", "series": "bionic"},
                "10": {"constraints": "tags=graylog zones=zone1", "series": "bionic"},
                "13": {"constraints": "tags=elastic zones=zone2"},
                "15": {"constraints": "tags=vault zones=zone1"},
                "16": {"constraints": "tags=vault zones=zone2"},
                "17": {"constraints": "tags=vault zones=zone3"},
                "18": {"constraints": "tags=elastic zones=zone3"},
                "19": {"constraints": "tags=graylog zones=zone2", "series": "bionic"},
                "20": {"constraints": "tags=graylog zones=zone3", "series": "bionic"},
                "1000": {"constraints": "tags=foundation-nodes zones=zone1"},
                "1001": {"constraints": "tags=foundation-nodes zones=zone2"},
                "1002": {"constraints": "tags=foundation-nodes zones=zone3"},
                "1003": {"constraints": "tags=foundation-nodes zones=zone1"},
                "1004": {"constraints": "tags=foundation-nodes zones=zone2"},
                "1005": {"constraints": "tags=foundation-nodes zones=zone3"},
            },
            "applications": {
                "hacluster-aodh": {"charm": "cs:hacluster"},
                "hacluster-barbican": {"charm": "cs:hacluster"},
                "hacluster-cinder": {"charm": "cs:hacluster"},
                "hacluster-glance": {"charm": "cs:hacluster"},
                "hacluster-gnocchi": {"charm": "cs:hacluster"},
                "hacluster-horizon": {"charm": "cs:hacluster"},
                "hacluster-keystone": {"charm": "cs:hacluster"},
                "hacluster-neutron": {"charm": "cs:hacluster"},
                "hacluster-nova": {"charm": "cs:hacluster"},
                "hacluster-mysql": {"charm": "cs:hacluster"},
                "hacluster-octavia": {"charm": "cs:hacluster"},
                "hacluster-radosgw": {"charm": "cs:hacluster"},
                "hacluster-designate": {"charm": "cs:hacluster"},
                "hacluster-heat": {"charm": "cs:hacluster"},
                "hacluster-ceilometer": {"charm": "cs:hacluster"},
                "hacluster-vault": {"charm": "cs:hacluster"},
                "ceph-mon": {
                    "charm": "cs:ceph-mon",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "ceph-osd": {
                    "charm": "cs:ceph-osd",
                    "num_units": 6,
                    "to": ["1000", "1001", "1002", "1003", "1004", "1005"],
                },
                "ceph-radosgw": {
                    "charm": "cs:ceph-radosgw",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "aodh": {
                    "charm": "cs:aodh",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "barbican": {
                    "charm": "cs:barbican",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "barbican-vault": {},
                "gnocchi": {
                    "charm": "cs:gnocchi",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "cinder": {
                    "charm": "cs:cinder",
                    "num_units": 3,
                    "constraints": "spaces=ceph-access-space,oam-space",
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "cinder-ceph": {
                    "charm": "cs:cinder-ceph",
                    "num_units": 0,
                },
                "glance": {
                    "charm": "cs:glance",
                    "constraints": "spaces=ceph-access-space,oam-space",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "keystone": {
                    "charm": "cs:~openstack-charmers-next/keystone",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "keystone-ldap": {
                    "charm": "cs:keystone-ldap",
                    "num_units": 0,
                },
                "logrotate": {
                    "charm": "cs:~logrotate-charmers/logrotate-charm",
                    "num_units": 0,
                    "options": {"logrotate-retention": 60},
                },
                "mysql": {
                    "charm": "cs:percona-cluster",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "neutron-api": {
                    "charm": "cs:neutron-api",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "neutron-gateway": {
                    "charm": "cs:neutron-gateway",
                    "num_units": 2,
                    "bindings": {"": "oam-space", "data": "internal-space"},
                    "to": [1004, 1005],
                },
                "neutron-openvswitch": {
                    "charm": "cs:neutron-openvswitch",
                    "num_units": 0,
                    "bindings": {"": "oam-space", "data": "internal-space"},
                },
                "nova-cloud-controller": {
                    "charm": "cs:nova-cloud-controller",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "nova-compute-kvm": {
                    "charm": "cs:nova-compute",
                    "num_units": 4,
                    "options": {
                        "openstack-origin": "cloud:bionic-stein",
                        "reserved-host-memory": 16384,
                        "cpu-mode": "custom",
                        "cpu-model": "Haswell-noTSX-IBRS",
                    },
                    "to": [1000, 1001, 1002, 1003],
                },
                "octavia": {
                    "charm": "cs:octavia",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "octavia-dashboard": {"charm": "cs:octavia-dashboard", "num_units": 0},
                "octavia-diskimage-retrofit": {
                    "charm": "cs:octavia-diskimage-retrofit",
                },
                "openstack-dashboard": {
                    "charm": "cs:openstack-dashboard",
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "rabbitmq-server": {
                    "charm": "cs:rabbitmq-server",
                    "options": {"source": "cloud:bionic-stein", "min-cluster-size": 3},
                    "num_units": 3,
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "heat": {
                    "charm": "cs:heat",
                    "num_units": 3,
                    "to": ["lxd:1000", "lxd:1001", "lxd:1002"],
                },
                "designate": {
                    "charm": "cs:designate",
                    "num_units": 3,
                    "options": {
                        "openstack-origin": "cloud:bionic-stein",
                        "region": "RegionOne",
                        "vip": "10.244.8.84 192.168.33.6",
                        "use-internal-endpoints": True,
                        "nameservers": "ns1.example.com.",
                    },
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "designate-bind": {
                    "charm": "cs:designate-bind",
                    "num_units": 2,
                    "options": {
                        "use-internal-endpoints": True,
                        "allowed_nets": "172.16.0.0/24;10.0.0.0/8",
                        "forwarders": "10.245.208.49",
                        "recursion": True,
                        "disable-dnssec-validation": True,
                    },
                    "to": ["lxd:1001", "lxd:1002"],
                },
                "ceilometer": {
                    "charm": "cs:ceilometer",
                    "num_units": 3,
                    "options": {
                        "openstack-origin": "cloud:bionic-stein",
                        "region": "RegionOne",
                        "vip": "10.244.8.81 192.168.33.3",
                        "use-internal-endpoints": True,
                    },
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "graylog": {},
                "graylog-mongodb": {},
                "elasticsearch": {},
                "filebeat": {},
                "nagios": {},
                "grafana": {},
                "telegraf": {
                    "charm": "cs:telegraf",
                    "bindings": {"prometheus-client": "oam-space"},
                },
                "thruk-agent": {
                    "charm": "cs:thruk-agent",
                    "series": "bionic",
                },
                "glance-simplestreams-sync": {},
                "etcd": {
                    "charm": "cs:etcd",
                    "num_units": 3,
                    "constraints": "spaces=oam-space",
                    "bindings": {"": "internal-space"},
                    "options": {"channel": "3.2/stable"},
                    "to": ["lxd:1001", "lxd:1003", "lxd:1005"],
                },
                "vault": {
                    "charm": "cs:vault",
                    "num_units": 3,
                    "bindings": {"": "internal-space"},
                    "options": {"vip": "192.168.33.15"},
                    "to": [15, 16, 17],
                },
            },
            "relations": [
                ["ceph-osd", "ceph-mon"],
                ["ceph-mon", "landscape-client"],
                ["ceph-mon", "filebeat"],
                ["ceph-mon", "logrotate"],
                ["graylog:beats", "filebeat:logstash"],
                ["graylog", "ntp"],
                ["nagios:juju-info", "canonical-livepatch"],
                ["prometheus", "filebeat"],
                ["grafana", "filebeat"],
                ["grafana", "logrotate"],
                ["nagios", "nrpe-container"],
                ["nagios", "nrpe-host"],
                ["graylog", "elasticsearch"],
                ["prometheus:nrpe-external-master", "nrpe-host:nrpe-external-master"],
            ],
        }
