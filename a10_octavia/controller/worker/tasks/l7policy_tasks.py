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


import acos_client.errors as acos_errors
from oslo_config import cfg
from oslo_log import log as logging
from taskflow import task

from a10_octavia.controller.worker.tasks import utils
from a10_octavia.controller.worker.tasks.decorators import axapi_client_decorator
from a10_octavia.controller.worker.tasks.policy import PolicyUtil

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class L7PolicyUtility(object):

    def _create_l7policy(self, l7policy):
        file = l7policy.id
        p = PolicyUtil()
        script = p.createPolicy(l7policy)
        size = len(script.encode('utf-8'))
        self.axapi_client.slb.aflex_policy.create(
            file=file, script=script, size=size, action="import")

    def _get_virtual_port(self, listener):
        return self.axapi_client.slb.virtual_server.vport.get(
            listener.load_balancer_id, listener.name,
            listener.protocol, listener.protocol_port)

    def _update_virtual_port(self, listener, **kwargs):
        c_pers, s_pers = utils.get_sess_pers_templates(listener.default_pool)
        self.axapi_client.slb.virtual_server.vport.update(
            listener.load_balancer_id, listener.name,
            listener.protocol, listener.protocol_port,
            listener.default_pool_id, s_pers,
            c_pers, 1, **kwargs)


class CreateL7Policy(L7PolicyUtility, task.Task):
    """Task to create a L7Policy"""

    @axapi_client_decorator
    def execute(self, l7policy, listeners, vthunder):
        port_update_params = {}
        listener = listeners[0]
        try:
            self._create_l7policy(l7policy)
            LOG.debug("Successfully created L7 policy: %s", l7policy.id)
        except (acos_errors.ACOSException, ConnectionError) as e:
            LOG.exception("Failed to create L7 policy: %s", l7policy.id)
            raise e
        try:
            listener_data = self._get_virtual_port(listener)
        except (acos_errors.ACOSException, ConnectionError) as e:
            LOG.exception("Failed to create L7 policy: %s", l7policy.id)
            raise e
        else:
            try:
                port_update_params['aflex-scripts'] = listener_data['port']['aflex-scripts']
            except KeyError:
                port_update_params['aflex-scripts'] = []
            port_update_params.append({"aflex": l7policy.id})

            try:
                self._update_l7policy(listener, **port_update_params)
                LOG.debug("Successfully associated L7 policy to port %s", l7policy.id. lis)
            except (acos_errors.ACOSException, ConnectionError) as e:
                LOG.exception("Failed to associate L7 policy %s to port %s", l7policy.id)
                raise e


class UpdateL7Policy(L7PolicyUtility, task.Task):
    """Task to update L7Policy"""

    @axapi_client_decorator
    def execute(self, l7policy, listeners, vthunder, update_dict):
        l7policy.update(update_dict)
        self.set(l7policy, listeners)


class DeleteL7Policy(L7PolicyUtility, task.Task):
    """Task to delete L7Policy"""

    @axapi_client_decorator
    def execute(self, l7policy, vthunder):
        update_params = {}
        listener = l7policy.listener
        try:
            listener_data = self._get_virtual_port(listener)
        except (acos_errors.ACOSException, ConnectionError) as e:
            raise e

        try:
            aflex_scripts = listener_data['port']['aflex-scripts']
        except KeyError:
            pass
        else:
            update_params['aflex-scripts'] = [aflex for aflex in aflex_scripts if aflex['aflex'] != l7policy.id]
            try:
                self._update_virtual_port(l7policy, listener, **update_params)
                LOG.debug("Successfully dissociated l7policy %s from port %s", l7policy.id, listener.id)
            except (acos_errors.ACOSException, ConnectionError) as e:
                LOG.warning("Failed to dissociate l7policy %s from port %s", l7policy.id, listener.id)
                raise e

        try:
            self.axapi_client.slb.aflex_policy.delete(l7policy.id)
            LOG.debug("Successfully deleted l7policy: %s", l7policy.id)
        except (acos_errors.ACOSException, ConnectionError) as e:
            LOG.exception("Failed to delete l7policy: %s", l7policy.id)
            raise e
