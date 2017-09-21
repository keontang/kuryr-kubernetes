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

import os
import signal
import sys

import os_vif
from oslo_log import log as logging

from kuryr_kubernetes import clients
from kuryr_kubernetes.cni import api as cni_api
from kuryr_kubernetes.cni import handlers as h_cni
from kuryr_kubernetes import config
from kuryr_kubernetes import constants as k_const
from kuryr_kubernetes import objects
from kuryr_kubernetes import watcher as k_watcher

LOG = logging.getLogger(__name__)
_CNI_TIMEOUT = 180


class K8sCNIPlugin(cni_api.CNIPlugin):

    def add(self, params):
        self._setup(params)
        self._pipeline.register(h_cni.AddHandler(params, self._done))
        self._watcher.start()
        return self._vif

    def delete(self, params):
        self._setup(params)
        self._pipeline.register(h_cni.DelHandler(params, self._done))
        self._watcher.start()

    def _done(self, vif):
        self._vif = vif
        self._watcher.stop()

    def _setup(self, params):
        args = ['--config-file', params.config.kuryr_conf]

        try:
            if params.config.debug:
                args.append('-d')
        except AttributeError:
            pass

        # 解析 cni 命令行参数
        config.init(args)
        config.setup_logging()

        # github.com/openstack/os_vif/os_vif/__init__.py
        #
        # def initialize(reset=False):
        #     """
        #     Loads all os_vif plugins and initializes them with a dictionary of
        #     configuration options. These configuration options are passed as-is
        #     to the individual VIF plugins that are loaded via stevedore.
        #     :param reset: Recreate and load the VIF plugin extensions.
        #     """
        #     global _EXT_MANAGER
        #     if _EXT_MANAGER is None:
        #         os_vif.objects.register_all()
        # 
        #     if reset or (_EXT_MANAGER is None):
        #         _EXT_MANAGER = extension.ExtensionManager(namespace='os_vif',
        #                                             invoke_on_load=False)
        #         loaded_plugins = []
        #         for plugin_name in _EXT_MANAGER.names():
        #             cls = _EXT_MANAGER[plugin_name].plugin
        #             obj = cls.load(plugin_name)
        #             LOG.debug(("Loaded VIF plugin class '%(cls)s' "
        #                        "with name '%(plugin_name)s'"),
        #                       {'cls': cls, 'plugin_name': plugin_name})
        #             loaded_plugins.append(plugin_name)
        #             _EXT_MANAGER[plugin_name].obj = obj
        #         LOG.info("Loaded VIF plugins: %s", ", ".join(loaded_plugins))
        #
        #
        # stevedore 基于 setuptools entry point, 提供 python 应用程序管理插件的功能.
        # os_vif 正式利用 stevedore 加载多个 plugin.
        #
        # 我们看 github.com/openstack/kuryr-kubernetes/setup.cfg:
        #     [entry_points]
        #     os_vif =
        #         noop = kuryr_kubernetes.os_vif_plug_noop:NoOpPlugin
        #
        # 然后 github.com/openstack/os-vif/setup.cfg:
        #     [entry_points]
        #     os_vif =
        #         linux_bridge = vif_plug_linux_bridge.linux_bridge:LinuxBridgePlugin
        #         ovs = vif_plug_ovs.ovs:OvsPlugin
        #
        #
        os_vif.initialize()
        clients.setup_kubernetes_client()
        # _pipeline 对象: 对 Event 事件进行分发到对应的 consumer 去处理
        self._pipeline = h_cni.CNIPipeline()
        # _watcher 对象: Observes K8s resources' events using K8s '?watch=true' API
        self._watcher = k_watcher.Watcher(self._pipeline)
        self._watcher.add(
            "%(base)s/namespaces/%(namespace)s/pods"
            "?fieldSelector=metadata.name=%(pod)s" % {
                'base': k_const.K8S_API_BASE,
                'namespace': params.args.K8S_POD_NAMESPACE,
                'pod': params.args.K8S_POD_NAME})


def run():
    # REVISIT(ivc): current CNI implementation provided by this package is
    # experimental and its primary purpose is to enable development of other
    # components (e.g. functional tests, service/LBaaSv2 support)

    # TODO(vikasc): Should be done using dynamically loadable OVO types plugin.
    objects.register_locally_defined_vifs()

    runner = cni_api.CNIRunner(K8sCNIPlugin())

    def _timeout(signum, frame):
        runner._write_dict(sys.stdout, {
            'msg': 'timeout',
            'code': k_const.CNI_TIMEOUT_CODE,
        })
        LOG.debug('timed out')
        sys.exit(1)

    # singnal.signal(signalnum, handler)
    #     signalnum 为某个信号, handler 为该信号的处理函数
    signal.signal(signal.SIGALRM, _timeout)
    # 在 signal.alarm() 执行 _CNI_TIMEOUT 秒之后，进程将向自己发出 SIGALRM 信号
    signal.alarm(_CNI_TIMEOUT)
    status = runner.run(os.environ, sys.stdin, sys.stdout)
    LOG.debug("Exiting with status %s", status)
    if status:
        sys.exit(status)
