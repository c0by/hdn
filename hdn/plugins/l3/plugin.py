# Copyright 2015 Taturiello Consulting
# All Rights Reserved.
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

from oslo_log import log

from hdn.common import constants
from hdn.common import hdnlib

LOG = log.getLogger(__name__)


class HdnL3Plugin(l3_db.L3_NAT_db_mixin):

    def create_router(self, context, router):
        # Put the router in PENDING CREATE
        router['router']['status'] = constants.STATUS_PENDING_CREATE
        new_router = super(HdnNeutronPlugin, self).create_router(
            context, router)
        # Notify HDN operators
        hdnlib.notify_router_create(new_router)
        LOG.debug("Queued request to create router: %s", new_router['id'])
        return new_router

    def update_router(self, context, router_id, router):
        # Put the router in PENDING_UPDATE
        router['router']['status'] = constants.STATUS_PENDING_UPDATE
        upd_router = super(HdnNeutronPlugin, self).update_router(
            context, router)
        # Notify HDN operators
        hdnlib.notify_router_update(upd_router)
        LOG.debug("Queued request to update router: %s", router['id'])
        return upd_router

    def delete_router(self, context, router_id, router):
        # Put the router in PENDING_DELETE status
        with context.session.begin(subtransactions=True):
            router = self._ensure_router_not_in_use(router_id)
            router.status = constants.STATUS_PENDING_DELETE
        # Notify HDN operators
        hdnlib.notify_router_delete({'id': router_id,
                                     'tenant_id': context.tenant_id})
        LOG.debug(_("Queued request to delete router: %s"), router_id)

    # GET operations for routers are not redefined. The operation defined
    # in NeutronDBPluginV2 is enough for the HDN plugin

    def _update_fip_assoc(self, context, fip, floatingip_db, external_port):
        """Performs association of a floating IP with a port.

        This method is invoked by create_floatingip and update_floatingip.
        """
        super(HdnNeutronPlugin, self).update_fip_assoc(
            context, fip, floatingip_db, external_port)
        self.update_floatingip_status(
            fip['id'], constants.STATUS_PENDING_UPDATE)
        # Notify HDN operators
        hdnlib.notify_floatingip_update_association(floatingip_db)

    def delete_floatingip(self, context, floatingip_id):
        # TODO(salv): Add operational status for floating IPs
        # Notify HDN operators
        hdnlib.notify_floatingip_delete({'id': floatingip_id,
                                         'tenant_id': context.tenant_id})
        self.update_floatingip_status(
            floatingip_id, constants.STATUS_PENDING_DELETE)
        LOG.debug(_("Queued request to delete floating ip: %s"),
                  floatingip_id)

    def disassociate_floatingips(self, context, port_id):
        # This method is redefined as this plugin does not use a RPC
        # notifier, which would be against the HDN principles.
        with context.session.begin(subtransactions=True):
            try:
                fip_qry = context.session.query(l3_db.FloatingIP)
                floating_ip = fip_qry.filter_by(fixed_port_id=port_id).one()
                floating_ip.update({'fixed_port_id': None,
                                    'fixed_ip_address': None,
                                    'router_id': None})
                self.update_floatingip_status(fip['id'],
                                              constants.STATUS_PENDING_UPDATE)
                # Notify HDN operators for each floating IP
                hdnlib.notify_floatingip_disassociate(floating_ip)
            except sa_exc.NoResultFound:
                return
            except sa_exc.MultipleResultsFound:
                # should never happen
                raise Exception(_('Multiple floating IPs found for port %s'))

    # GET operations for floating IPs are not redefined. The operation defined
    # in NeutronDBPluginV2 is enough for the HDN plugin