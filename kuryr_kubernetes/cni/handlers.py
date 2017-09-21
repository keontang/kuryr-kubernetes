# Copyright (c) 2016 Mirantis, Inc.
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

import abc
import six

from os_vif import objects as obj_vif
from oslo_log import log as logging
from oslo_serialization import jsonutils

from kuryr_kubernetes.cni.binding import base as b_base
from kuryr_kubernetes import constants as k_const
from kuryr_kubernetes.handlers import dispatch as k_dis
from kuryr_kubernetes.handlers import k8s_base

LOG = logging.getLogger(__name__)

# pod annotation:
#
# "openstack.org/kuryr-vif": "{
#     \"versioned_object.data\": {
#         \"active\": true, 
#         \"address\": \"fa:16:3e:29:cf:9e\", 
#         \"bridge_name\": \"br-int\",
#         \"has_traffic_filtering\": true, 
#         \"id\": \"2faf4e00-fc66-4746-83b2-1e5782e2ae92\",
#         \"network\": {
#             \"versioned_object.data\": {
#                 \"bridge\": \"br-int\", 
#                 \"id\": \"2dc4b4eb-9313-4007-9286-46ca79e71304\",
#                 \"label\": \"kuryr\",
#                 \"mtu\": 1500, 
#                 \"multi_host\": false, 
#                 \"should_provide_bridge\": false, 
#                 \"should_provide_vlan\": false, 
#                 \"subnets\": {
#                     \"versioned_object.data\": {
#                         \"objects\": [{
#                             \"versioned_object.data\": {
#                                 \"cidr\": \"10.10.0.0/16\",
#                                 \"dns\": [], 
#                                 \"gateway\": \"10.10.0.254\",
#                                 \"ips\": {
#                                     \"versioned_object.data\": {
#                                         \"objects\": [{
#                                             \"versioned_object.data\": {\"address\": \"10.10.1.8\"}, 
#                                             \"versioned_object.name\": \"FixedIP\", 
#                                             \"versioned_object.namespace\": \"os_vif\", 
#                                             \"versioned_object.version\": \"1.0\"
#                                         }]
#                                     }, 
#                                     \"versioned_object.name\": \"FixedIPList\", 
#                                     \"versioned_object.namespace\": \"os_vif\", 
#                                     \"versioned_object.version\": \"1.0\"
#                                 }, 
#                                 \"routes\": {
#                                     \"versioned_object.data\": {
#                                         \"objects\": []
#                                     }, 
#                                     \"versioned_object.name\": \"RouteList\", 
#                                     \"versioned_object.namespace\": \"os_vif\", 
#                                     \"versioned_object.version\": \"1.0\"
#                                 }
#                             }, 
#                             \"versioned_object.name\": \"Subnet\", 
#                             \"versioned_object.namespace\": \"os_vif\", 
#                             \"versioned_object.version\": \"1.0\"
#                         }]
#                     }, 
#                     \"versioned_object.name\": \"SubnetList\", 
#                     \"versioned_object.namespace\": \"os_vif\", 
#                     \"versioned_object.version\": \"1.0\"
#                 }
#             }, 
#             \"versioned_object.name\": \"Network\", 
#             \"versioned_object.namespace\": \"os_vif\", 
#             \"versioned_object.version\": \"1.1\"
#         }, 
#         \"plugin\": \"ovs\", 
#         \"port_profile\": {
#             \"versioned_object.data\": {
#                 \"interface_id\": \"2faf4e00-fc66-4746-83b2-1e5782e2ae92\"
#             }, 
#             \"versioned_object.name\": \"VIFPortProfileOpenVSwitch\", 
#             \"versioned_object.namespace\": \"os_vif\", 
#             \"versioned_object.version\": \"1.0\"
#         }, 
#         \"preserve_on_delete\": false, 
#         \"vif_name\": \"tap2faf4e00-fc\"
#     }, 
#     \"versioned_object.name\": \"VIFOpenVSwitch\", 
#     \"versioned_object.namespace\": \"os_vif\", 
#     \"versioned_object.version\": \"1.0\"
# }"
#

@six.add_metaclass(abc.ABCMeta)
class CNIHandlerBase(k8s_base.ResourceEventHandler):
    OBJECT_KIND = k_const.K8S_OBJ_POD

    def __init__(self, cni, on_done):
        self._cni = cni
        self._callback = on_done
        self._vif = None

    def on_present(self, pod):
        vif = self._get_vif(pod)

        if vif:
            self.on_vif(pod, vif)

    @abc.abstractmethod
    def on_vif(self, pod, vif):
        raise NotImplementedError()

    def _get_vif(self, pod):
        # TODO(ivc): same as VIFHandler._get_vif
        try:
            annotations = pod['metadata']['annotations']
            vif_annotation = annotations[k_const.K8S_ANNOTATION_VIF]
        except KeyError:
            return None
        vif_dict = jsonutils.loads(vif_annotation)
        # refer to openstack/oslo.versionedobjects/oslo_versionedobjects/base.py:VersionedObject
        vif = obj_vif.vif.VIFBase.obj_from_primitive(vif_dict)
        LOG.debug("Got VIF from annotation: %r", vif)
        # just like:
        #     Got VIF from annotation: 
        #     VIFOpenVSwitch(active=True,address=fa:16:3e:3f:95:b5,bridge_name='br-int',has_traffic_filtering=True,id=a77d35cf-31c0-4c04-ba9d-fed095bac91a,network=Network(2dc4b4eb-9313-4007-9286-46ca79e71304),plugin='ovs',port_profile=VIFPortProfileBase,preserve_on_delete=False,vif_name='tapa77d35cf-31')
        return vif

    def _get_inst(self, pod):
        return obj_vif.instance_info.InstanceInfo(
            uuid=pod['metadata']['uid'], name=pod['metadata']['name'])


class AddHandler(CNIHandlerBase):

    def __init__(self, cni, on_done):
        LOG.debug("AddHandler called with CNI env: %r", cni)
        super(AddHandler, self).__init__(cni, on_done)
        self._vif = None

    def on_vif(self, pod, vif):
        if not self._vif:
            self._vif = vif.obj_clone()
            self._vif.active = True
            b_base.connect(self._vif, self._get_inst(pod),
                           self._cni.CNI_IFNAME, self._cni.CNI_NETNS)

        if vif.active:
            self._callback(vif)


class DelHandler(CNIHandlerBase):

    def on_vif(self, pod, vif):
        b_base.disconnect(vif, self._get_inst(pod),
                          self._cni.CNI_IFNAME, self._cni.CNI_NETNS)
        self._callback(vif)


class CNIPipeline(k_dis.EventPipeline):

    def _wrap_dispatcher(self, dispatcher):
        return dispatcher

    def _wrap_consumer(self, consumer):
        return consumer
