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

from kuryr_kubernetes.handlers import dispatch


# Pod watch event:
#
# {
#     "type":"ADDED",
#     "object": {
#         "kind":"Pod",
#         "apiVersion":"v1",
#         "metadata": {
#             "name":"nginx-p8lbx",
#             "generateName":"nginx-",
#             "namespace":"default",
#             "selfLink":"/api/v1/namespaces/default/pods/nginx-p8lbx",
#             "uid":"9693c563-8966-11e7-a2a1-ac1f6b1274fa",
#             "resourceVersion":"929758",
#             "creationTimestamp":"2017-08-25T07:25:36Z",
#             "deletionTimestamp":"2017-08-31T01:47:07Z",
#             "deletionGracePeriodSeconds":30,
#             "labels": { "app":"nginx" },
#             "annotations": {
#                 "kubernetes.io/created-by": "{
#                     \"kind\":\"SerializedReference\",
#                     \"apiVersion\":\"v1\",
#                     \"reference\": {
#                         \"kind\":\"ReplicationController\",
#                         \"namespace\":\"default\",
#                         \"name\":\"nginx\",
#                         \"uid\":\"63ce2552-88b2-11e7-a2a1-ac1f6b1274fa\",
#                         \"apiVersion\":\"v1\",
#                         \"resourceVersion\":\"288364\"
#                     }
#                 }\n"
#             },
#             "ownerReferences":[{
#                 "apiVersion":"v1",
#                 "kind":"ReplicationController",
#                 "name":"nginx",
#                 "uid":"63ce2552-88b2-11e7-a2a1-ac1f6b1274fa",
#                 "controller":true,
#                 "blockOwnerDeletion":true
#             }]
#         },
#         "spec": {
#             "volumes":[{
#                 "name":"default-token-wpf02",
#                 "secret":{
#                     "secretName":"default-token-wpf02",
#                     "defaultMode":420
#                 }
#             }],
#             "containers":[{
#                 "name":"nginx",
#                 "image":"nginx:net.tools",
#                 "ports":[{
#                     "containerPort":80,
#                     "protocol":"TCP"
#                 }],
#                 "resources":{},
#                 "volumeMounts":[{
#                     "name":"default-token-wpf02",
#                     "readOnly":true,
#                     "mountPath":"/var/run/secrets/kubernetes.io/serviceaccount"
#                 }],
#                 "terminationMessagePath":"/dev/termination-log",
#                 "terminationMessagePolicy":"File",
#                 "imagePullPolicy":"IfNotPresent"
#             }],
#             "restartPolicy":"Always",
#             "terminationGracePeriodSeconds":30,
#             "dnsPolicy":"ClusterFirst",
#             "serviceAccountName":"default",
#             "serviceAccount":"default",
#             "nodeName":"computer2",
#             "securityContext":{},
#             "schedulerName":"default-scheduler"
#         },
#         "status":{
#             "phase":"Running",
#             "conditions":[{
#                 "type":"Initialized",
#                 "status":"True",
#                 "lastProbeTime":null,
#                 "lastTransitionTime":"2017-08-25T07:25:36Z"
#             },
#             {
#                 "type":"Ready",
#                 "status":"True",
#                 "lastProbeTime":null,
#                 "lastTransitionTime":"2017-08-25T07:26:03Z"
#             },
#             {
#                 "type":"PodScheduled",
#                 "status":"True",
#                 "lastProbeTime":null,
#                 "lastTransitionTime":"2017-08-25T07:25:36Z"
#             }],
#             "hostIP":"192.168.16.21",
#             "podIP":"10.10.1.8",
#             "startTime":"2017-08-25T07:25:36Z",
#             "containerStatuses":[{
#                 "name":"nginx",
#                 "state":{
#                     "running":{"startedAt":"2017-08-25T07:25:51Z"}
#                 },
#                 "lastState":{},
#                 "ready":true,
#                 "restartCount":0,
#                 "image":"nginx:net.tools",
#                 "imageID":"docker://sha256:d200f748dac803fb4d0d9f7f323b703a8c5273aabb9709ad1bc817bc68fb327e",
#                 "containerID":"docker://5e311f7788aca834e45203cf14ac5710f8b2ea596e21410f535638aae7c39776"
#             }],
#             "qosClass":"BestEffort"
#         }
#     }
# }


def object_kind(event):
    try:
        return event['object']['kind']
    except KeyError:
        return None


def object_link(event):
    try:
        return event['object']['metadata']['selfLink']
    except KeyError:
        return None


class ResourceEventHandler(dispatch.EventConsumer):
    """Base class for K8s event handlers.

    Implementing classes should override the `OBJECT_KIND` attribute with a
    valid Kubernetes object type name (e.g. 'Pod' or 'Namespace'; see [1]
    for more details).

    Implementing classes are expected to override any or all of the
    `on_added`, `on_present`, `on_modified`, `on_deleted` methods that would
    be called depending on the type of the event (with K8s object as a single
    argument).

    [1] https://github.com/kubernetes/kubernetes/blob/release-1.4/docs/devel\
        /api-conventions.md#types-kinds
    """

    OBJECT_KIND = None

    @property
    def consumes(self):
        return {object_kind: self.OBJECT_KIND}

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
    #
    #
    # 此时的 event 是一个 dict
    def __call__(self, event):
        event_type = event.get('type')
        obj = event.get('object')
        if 'MODIFIED' == event_type:
            self.on_modified(obj)
            self.on_present(obj)
        elif 'ADDED' == event_type:
            self.on_added(obj)
            self.on_present(obj)
        elif 'DELETED' == event_type:
            self.on_deleted(obj)

    def on_added(self, obj):
        pass

    def on_present(self, obj):
        pass

    def on_modified(self, obj):
        pass

    def on_deleted(self, obj):
        pass
