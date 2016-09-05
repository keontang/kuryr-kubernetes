# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import asyncio
import sys

from kuryr.lib._i18n import _LI
from oslo_log import log as logging
from oslo_service import service

from kuryr_kubernetes import config
from kuryr_kubernetes.watchers import pod


LOG = logging.getLogger(__name__)


class KuryrK8sService(service.Service):
    """Kuryr-Kubernetes base service.

    This class extends the oslo_service.service.Service class to provide an
    asynchronous event loop. It assumes that all the elements of the
    `_watchers` list has a method called `watch` (normally, implemented by the
    class `kuryr_kubernetes.watchers.base.AbstractBaseWatcher`).

    The event loop is the default used by asyncio (asyncio.SelectorEventLoop)
    """

    def __init__(self):
        super(KuryrK8sService, self).__init__()
        self._event_loop = asyncio.new_event_loop()
        self._watchers = [
            pod.PodWatcher
        ]

    def start(self):
        LOG.info(_LI("Service '%(class_name)s' started"),
                 {'class_name': self.__class__.__name__})

        for watcher in self._watchers:
            instance = watcher(self._event_loop)
            self._event_loop.create_task(instance.watch())
        try:
            self._event_loop.run_forever()
            self._event_loop.close()
        except Exception:
            sys.exit(1)
        sys.exit(0)

    def wait(self):
        """Waits for K8sController to complete."""
        super(KuryrK8sService, self).wait()

    def stop(self, graceful=False):
        """Stops the event loop if it's not stopped already."""
        super(KuryrK8sService, self).stop(graceful)


def start():
    config.init(sys.argv[1:])
    config.setup_logging()
    kuryrk8s_launcher = service.launch(config.CONF, KuryrK8sService())
    kuryrk8s_launcher.wait()


if __name__ == '__main__':
    start()