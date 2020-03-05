#    Copyright 2019, A10 Networks
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

from oslo_config import cfg
from oslo_log import log as logging
from taskflow.types import failure

from octavia.common import constants
from octavia.common import exceptions
from octavia.controller.worker.tasks.compute_tasks import BaseComputeTask

CONF = cfg.CONF
LOG = logging.getLogger(__name__)



class ComputeCreate(BaseComputeTask):
    """Create the compute instance for a new amphora."""

    def execute(self, amphora_id, build_type_priority=constants.LB_CREATE_NORMAL_PRIORITY,
                server_group_id=None, ports=None):
        import rpdb; rpdb.set_trace()
        ports = ports or []
        network_ids = CONF.a10_controller_worker.amp_boot_network_list[:]
        LOG.debug("Compute create execute for amphora with id %s", amphora_id)
        key_name = CONF.a10_controller_worker.amp_ssh_key_name
        topology = CONF.a10_controller_worker.loadbalancer_topology

        try:
            if CONF.a10_controller_worker.build_rate_limit != -1:
                self.rate_limit.add_to_build_request_queue(
                    amphora_id, build_type_priority)

            compute_id = self.compute.build(
                name="amphora-" + amphora_id,
                amphora_flavor=CONF.a10_controller_worker.amp_flavor_id,
                image_id=CONF.a10_controller_worker.amp_image_id,
                image_tag=CONF.a10_controller_worker.amp_image_tag,
                image_owner=CONF.a10_controller_worker.amp_image_owner_id,
                key_name=key_name,
                sec_groups=CONF.a10_controller_worker.amp_secgroup_list,
                network_ids=network_ids,
                port_ids=[port.id for port in ports],
                server_group_id=server_group_id)

            LOG.debug("Server created with id: %s for amphora id: %s",
                      compute_id, amphora_id)
            return compute_id

        except Exception:
            LOG.exception("Compute create for amphora id: %s failed",
                          amphora_id)
            raise

    def revert(self, result, amphora_id, *args, **kwargs):
        """This method will revert the creation of the

        amphora. So it will just delete it in this flow
        """
        if isinstance(result, failure.Failure):
            return
        compute_id = result
        LOG.warning("Reverting compute create for amphora with id"
                    "%(amp)s and compute id: %(comp)s",
                    {'amp': amphora_id, 'comp': compute_id})
        try:
            self.compute.delete(compute_id)
        except Exception:
            LOG.exception("Reverting compute create failed")


class ComputeActiveWait(BaseComputeTask):
    """Wait for the compute driver to mark the amphora active."""

    def execute(self, compute_id, amphora_id):
        """Wait for the compute driver to mark the amphora active

        :raises: Generic exception if the amphora is not active
        :returns: An amphora object
        """
        for i in range(CONF.a10_controller_worker.amp_active_retries):
            amp, fault = self.compute.get_amphora(compute_id)
            if amp.status == constants.ACTIVE:
                if CONF.a10_controller_worker.build_rate_limit != -1:
                    self.rate_limit.remove_from_build_req_queue(amphora_id)
                return amp
            elif amp.status == constants.ERROR:
                raise exceptions.ComputeBuildException(fault=fault)
            time.sleep(CONF.a10_controller_worker.amp_active_wait_sec)

        raise exceptions.ComputeWaitTimeoutException(id=compute_id)


class NovaServerGroupCreate(BaseComputeTask):
    def execute(self, loadbalancer_id):
        """Create a server group by nova client api

        :param loadbalancer_id: will be used for server group's name
        :param policy: will used for server group's policy
        :raises: Generic exception if the server group is not created
        :returns: server group's id
        """

        name = 'octavia-lb-' + loadbalancer_id
        server_group = self.compute.create_server_group(
            name, CONF.a10_nova.anti_affinity_policy)
        LOG.debug("Server Group created with id: %s  for load balancer id: %s"
                  "", server_group.id, loadbalancer_id)
        return server_group.id

    def revert(self, result, *args, **kwargs):
        """This method will revert the creation of the

        :param result: here it refers to server group id
        """
        server_group_id = result
        LOG.warning("Reverting server group create with id: %s",
                    server_group_id)
        try:
            self.compute.delete_server_group(server_group_id)
        except Exception as e:
            LOG.error("Failed to delete server group.  Resources may "
                      "still be in use for server group: %(sg)s due to "
                      "error: %(except)s",
                      {'sg': server_group_id, 'except': e})