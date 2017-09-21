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

import itertools
from six.moves import queue as six_queue
import time

from oslo_log import log as logging


from kuryr_kubernetes.handlers import base

LOG = logging.getLogger(__name__)

DEFAULT_QUEUE_DEPTH = 100
DEFAULT_GRACE_PERIOD = 5
STALE_PERIOD = 0.5


# 封装 Dispatcher
# 通过 group_by fucn 使得不同的 object 位于不同的 group, 每个 group 用于一个独立的队列
# 不同的 group, Async 会创建不同的线程, 用 Dispatcher 对象函数 (__call__) 去分发 event
# 相同的 group 在同一个线程中利用 Dispatcher 对象函数 (__call__) 去分发 event
class Async(base.EventHandler):
    """Handles events asynchronously.

    `Async` can be used to decorate another `handler` to be run asynchronously
    using the specified `thread_group`. `Async` distinguishes *related* and
    *unrelated* events (based on the result of `group_by`(`event`) function)
    and handles *unrelated* events concurrently while *related* events are
    handled serially and in the same order they arrived to `Async`.
    """

    def __init__(self, handler, thread_group, group_by,
                 queue_depth=DEFAULT_QUEUE_DEPTH,
                 grace_period=DEFAULT_GRACE_PERIOD):
        self._handler = handler
        self._thread_group = thread_group
        self._group_by = group_by
        self._queue_depth = queue_depth
        self._grace_period = grace_period
        self._queues = {}

    def __call__(self, event):
        group = self._group_by(event)
        try:
            queue = self._queues[group]
        except KeyError:
            queue = six_queue.Queue(self._queue_depth)
            self._queues[group] = queue
            thread = self._thread_group.add_thread(self._run, group, queue)
            # refer to:
            #   openstack/deb-python-eventlet/eventlet/greenthread.py
            #   openstack/cloudpulse/cloudpulse/openstack/common/threadgroup.py
            #
            # class GreenThread(greenlet.greenlet):
            #   def link(self, func, *curried_args, **curried_kwargs):
            #       """ Set up a function to be called with the results of the GreenThread.
            #       The function must have the following signature::
            #         def func(gt, [curried args/kwargs]):
            #       When the GreenThread finishes its run, it calls *func* 
            #       with itself and with the curried arguments
            #       Note that *func* is called within execution context of
            #       the GreenThread
            #       """
            thread.link(self._done, group)
        # 线程已经起来, 把 event 放入 queue, 等待线程处理
        queue.put(event)

    def _run(self, group, queue):
        LOG.debug("Asynchronous handler started processing %s", group)
        for _ in itertools.count():
            # NOTE(ivc): this is a mock-friendly replacement for 'while True'
            # to allow more controlled environment for unit-tests (e.g. to
            # avoid tests getting stuck in infinite loops)
            try:
                event = queue.get(timeout=self._grace_period)
            # 如果 timeout 之后 queue 还是 Empty, 那么线程就退出
            except six_queue.Empty:
                break
            # FIXME(ivc): temporary workaround to skip stale events
            # If K8s updates resource while the handler is processing it,
            # when the handler finishes its work it can fail to update an
            # annotation due to the 'resourceVersion' conflict. K8sClient
            # was updated to allow *new* annotations to be set ignoring
            # 'resourceVersion', but it leads to another problem as the
            # Handler will receive old events (i.e. before annotation is set)
            # and will start processing the event 'from scratch'.
            # It has negative effect on handlers' performance (VIFHandler
            # creates ports only to later delete them and LBaaS handler also
            # produces some excess requests to Neutron, although with lesser
            # impact).
            # Possible solutions (can be combined):
            #  - use K8s ThirdPartyResources to store data/annotations instead
            #    of native K8s resources (assuming Kuryr-K8s will own those
            #    resources and no one else would update them)
            #  - use the resulting 'resourceVersion' received from K8sClient's
            #    'annotate' to provide feedback to Async to skip all events
            #    until that version
            #  - stick to the 'get-or-create' behaviour in handlers and
            #    also introduce cache for long operations
            time.sleep(STALE_PERIOD)
            while not queue.empty():
                event = queue.get()
                if queue.empty():
                    time.sleep(STALE_PERIOD)
            # consumer 处理 event
            self._handler(event)

    def _done(self, thread, group):
        LOG.debug("Asynchronous handler stopped processing %s", group)
        queue = self._queues.pop(group)

        if not queue.empty():
            LOG.critical("Asynchronous handler terminated abnormally; "
                         "%(count)s events dropped for %(group)s",
                         {'count': queue.qsize(), 'group': group})

        if not self._queues:
            LOG.debug("Asynchronous handler is idle")
