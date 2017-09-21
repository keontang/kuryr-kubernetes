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
import contextlib
import itertools
import os

from oslo_log import log as logging
from oslo_serialization import jsonutils
import requests

from kuryr.lib._i18n import _
from kuryr_kubernetes import config
from kuryr_kubernetes import exceptions as exc

LOG = logging.getLogger(__name__)


class K8sClient(object):
    # REVISIT(ivc): replace with python-k8sclient if it could be extended
    # with 'WATCH' support

    def __init__(self, base_url):
        self._base_url = base_url
        cert_file = config.CONF.kubernetes.ssl_client_crt_file
        key_file = config.CONF.kubernetes.ssl_client_key_file
        ca_crt_file = config.CONF.kubernetes.ssl_ca_crt_file
        self.verify_server = config.CONF.kubernetes.ssl_verify_server_crt
        token_file = config.CONF.kubernetes.token_file
        self.token = None
        self.cert = (None, None)
        if token_file:
            if os.path.exists(token_file):
                with open(token_file, 'r') as f:
                    self.token = f.readline().rstrip('\n')
            else:
                raise RuntimeError(
                    _("Unable to find token_file  : %s") % token_file)
        else:
            if cert_file and not os.path.exists(cert_file):
                raise RuntimeError(
                    _("Unable to find ssl cert_file  : %s") % cert_file)
            if key_file and not os.path.exists(key_file):
                raise RuntimeError(
                    _("Unable to find ssl key_file : %s") % key_file)
            self.cert = (cert_file, key_file)
        if self.verify_server:
            if not ca_crt_file:
                raise RuntimeError(
                    _("ssl_ca_crt_file cannot be None"))
            elif not os.path.exists(ca_crt_file):
                raise RuntimeError(
                    _("Unable to find ca cert_file  : %s") % ca_crt_file)
            else:
                self.verify_server = ca_crt_file

    def get(self, path):
        LOG.debug("Get %(path)s", {'path': path})
        url = self._base_url + path
        header = {}
        if self.token:
            header.update({'Authorization': 'Bearer %s' % self.token})
        response = requests.get(url, cert=self.cert,
                                verify=self.verify_server,
                                headers=header)
        if not response.ok:
            raise exc.K8sClientException(response.text)
        return response.json()

    def annotate(self, path, annotations, resource_version=None):
        """Pushes a resource annotation to the K8s API resource

        The annotate operation is made with a PATCH HTTP request of kind:
        application/merge-patch+json as described in:

        https://github.com/kubernetes/community/blob/master/contributors/devel/api-conventions.md#patch-operations  # noqa
        """
        LOG.debug("Annotate %(path)s: %(names)s", {
            'path': path, 'names': list(annotations)})
        url = self._base_url + path
        header = {'Content-Type': 'application/merge-patch+json',
                  'Accept': 'application/json'}
        if self.token:
            header.update({'Authorization': 'Bearer %s' % self.token})
        while itertools.count(1):
            data = jsonutils.dumps({
                "metadata": {
                    "annotations": annotations,
                    "resourceVersion": resource_version,
                }
            }, sort_keys=True)
            # POST 方法用来创建一个子资源，如 /api/users, 会在 users 下面创建一个 user, 如 users/1
            # POST 方法不是幂等的, 多次执行, 将导致多条相同的用户被创建 (users/1, users/2 ... 而这些用户除了自增长 id 外有着相同的数据, 除非你的系统实现了额外的数据唯一性检查)
            # 而 PUT 方法用来创建一个 URI 已知的资源, 或对已知资源进行完全替换, 比如 users/1
            # 因此 PUT 方法一般会用来更新一个已知资源, 除非在创建前, 你完全知道自己要创建的对象的 URI
            # PATCH 方法是新引入的, 是对 PUT 方法的补充, 用来对已知资源进行局部更新
            response = requests.patch(url, data=data,
                                      headers=header, cert=self.cert,
                                      verify=self.verify_server)
            if response.ok:
                return response.json()['metadata']['annotations']
            if response.status_code == requests.codes.conflict:
                resource = self.get(path)
                new_version = resource['metadata']['resourceVersion']
                retrieved_annotations = resource['metadata'].get(
                    'annotations', {})

                for k, v in annotations.items():
                    if v != retrieved_annotations.get(k, v):
                        break
                else:
                    # No conflicting annotations found. Retry patching
                    resource_version = new_version
                    continue
                LOG.debug("Annotations for %(path)s already present: "
                          "%(names)s", {'path': path,
                                        'names': retrieved_annotations})
            raise exc.K8sClientException(response.text)

    # 由于 yield 关键字, watch 变成一个生成器
    def watch(self, path):
        # Watch API 实际上一个标准的 HTTP GET 请求, 我们以 Pod 的 Watch API 为例
        #     HTTP Request
        #         GET /api/v1/watch/namespaces/{namespace}/pods
        #
        #       Path Parameters:
        #         namespace: object name and auth scope
        #
        #       Query Parameters:
        #         fieldSelector: A selector to restrict the list of returned
        #             objects by their fields. Defaults to everything.
        #         labelSelector: A selector to restrict the list of returned
        #             objects by their labels. Defaults to everything.
        #         pretty: If ‘true’, then the output is pretty printed.
        #         resourceVersion: When specified with a watch call, shows
        #             changes that occur after that particular version of a
        #             resource.
        #         timeoutSeconds: Timeout for the list/watch call.
        #         watch: Watch for changes to the described resources and
        #             return them as a stream of add, update, and remove
        #             notifications.
        params = {'watch': 'true'}
        url = self._base_url + path
        header = {}
        if self.token:
            header.update({'Authorization': 'Bearer %s' % self.token})

        # TODO(ivc): handle connection errors and retry on failure
        while True:
            with contextlib.closing(
                    requests.get(url, params=params, stream=True,
                                 cert=self.cert, verify=self.verify_server,
                                 headers=header)) as response:
                if not response.ok:
                    raise exc.K8sClientException(response.text)
                # refer to: kubernetes/pkg/apiserver/watch.go: ServeHTTP()
                # // Event represents a single event to a watched resource.
                # type Event struct {
                #     Type EventType
                # 
                #     // Object is:
                #     //  * If Type is Added or Modified: the new state of the object.
                #     //  * If Type is Deleted: the state of the object immediately before deletion.
                #     //  * If Type is Error: *api.Status is recommended; other types may make sense
                #     //    depending on context.
                #     Object runtime.Object
                # }
                for line in response.iter_lines(delimiter='\n'):
                    line = line.strip()
                    if line:
                        # jsonutils.loads() return a python dict
                        yield jsonutils.loads(line)
