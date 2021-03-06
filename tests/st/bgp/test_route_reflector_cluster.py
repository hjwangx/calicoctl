# Copyright (c) 2015-2016 Tigera, Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from nose.plugins.attrib import attr

from tests.st.test_base import TestBase
from tests.st.utils.docker_host import DockerHost
from tests.st.utils.route_reflector import RouteReflectorCluster

from .peer import create_bgp_peer, ADDITIONAL_DOCKER_OPTIONS

class TestRouteReflectorCluster(TestBase):

    @attr('slow')
    def test_route_reflector_cluster(self):
        """
        Run a multi-host test using a cluster of route reflectors and node
        specific peerings.
        """
        with DockerHost('host1',
                        additional_docker_options=ADDITIONAL_DOCKER_OPTIONS) as host1, \
             DockerHost('host2',
                        additional_docker_options=ADDITIONAL_DOCKER_OPTIONS) as host2, \
             DockerHost('host3',
                        additional_docker_options=ADDITIONAL_DOCKER_OPTIONS) as host3, \
             RouteReflectorCluster(2, 2) as rrc:

            # Set the default AS number - as this is used by the RR mesh, and
            # turn off the node-to-node mesh (do this from any host).
            host1.calicoctl("config set asNumber 64513")
            host1.calicoctl("config set nodeToNodeMesh off")

            # Create a workload on each host in the same network.
            network1 = host1.create_network("subnet1")
            workload_host1 = host1.create_workload("workload1", network=network1)
            workload_host2 = host2.create_workload("workload2", network=network1)
            workload_host3 = host3.create_workload("workload3", network=network1)

            # Allow network to converge (which it won't)
            self.assert_false(workload_host1.check_can_ping(workload_host2.ip, retries=5))
            self.assert_true(workload_host1.check_cant_ping(workload_host3.ip))
            self.assert_true(workload_host2.check_cant_ping(workload_host3.ip))

            # Set distributed peerings between the hosts, each host peering
            # with a different set of redundant route reflectors.
            for host in [host1, host2, host3]:
                for rr in rrc.get_redundancy_group():
                    create_bgp_peer(host, "node", rr.ip, 64513)

            # Allow network to converge (which it now will).
            self.assert_true(workload_host1.check_can_ping(workload_host2.ip, retries=10))
            self.assert_true(workload_host1.check_can_ping(workload_host3.ip, retries=10))
            self.assert_true(workload_host2.check_can_ping(workload_host3.ip, retries=10))

            # And check connectivity in both directions.
            self.assert_ip_connectivity(workload_list=[workload_host1,
                                                       workload_host2,
                                                       workload_host3],
                                        ip_pass_list=[workload_host1.ip,
                                                      workload_host2.ip,
                                                      workload_host3.ip])
