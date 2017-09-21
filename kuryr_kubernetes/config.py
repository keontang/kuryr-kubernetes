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
import os
import sys

from kuryr.lib._i18n import _
from kuryr.lib import config as lib_config
from oslo_config import cfg
from oslo_log import log as logging

from kuryr_kubernetes import version

LOG = logging.getLogger(__name__)

kuryr_k8s_opts = [
    cfg.StrOpt('pybasedir',
               help=_('Directory where Kuryr-kubernetes python module is '
                      'installed.'),
               default=os.path.abspath(
                   os.path.join(os.path.dirname(__file__),
                                '../../'))),
]

k8s_opts = [
    cfg.StrOpt('api_root',
               help=_("The root URL of the Kubernetes API"),
               default=os.environ.get('K8S_API', 'http://localhost:8080')),
    cfg.StrOpt('ssl_client_crt_file',
               help=_("Absolute path to client cert to "
                      "connect to HTTPS K8S_API")),
    cfg.StrOpt('ssl_client_key_file',
               help=_("Absolute path client key file to "
                      "connect to HTTPS K8S_API")),
    cfg.StrOpt('ssl_ca_crt_file',
               help=_("Absolute path to ca cert file to "
                      "connect to HTTPS K8S_API")),
    cfg.BoolOpt('ssl_verify_server_crt',
                help=_("HTTPS K8S_API server identity verification"),
                default=False),
    cfg.StrOpt('token_file',
               help=_("The token to talk to the k8s API"),
               default=''),
    cfg.StrOpt('pod_project_driver',
               help=_("The driver to determine OpenStack "
                      "project for pod ports"),
               default='default'),
    cfg.StrOpt('service_project_driver',
               help=_("The driver to determine OpenStack "
                      "project for services"),
               default='default'),
    cfg.StrOpt('pod_subnets_driver',
               help=_("The driver to determine Neutron "
                      "subnets for pod ports"),
               default='default'),
    cfg.StrOpt('service_subnets_driver',
               help=_("The driver to determine Neutron "
                      "subnets for services"),
               default='default'),
    cfg.StrOpt('pod_security_groups_driver',
               help=_("The driver to determine Neutron "
                      "security groups for pods"),
               default='default'),
    cfg.StrOpt('service_security_groups_driver',
               help=_("The driver to determine Neutron "
                      "security groups for services"),
               default='default'),
    cfg.StrOpt('pod_vif_driver',
               help=_("The driver that provides VIFs for Kubernetes Pods."),
               default='neutron-vif'),
    cfg.StrOpt('endpoints_lbaas_driver',
               help=_("The driver that provides LoadBalancers for "
                      "Kubernetes Endpoints"),
               default='lbaasv2'),
    cfg.StrOpt('vif_pool_driver',
               help=_("The driver that manages VIFs pools for "
                      "Kubernetes Pods."),
               default='noop'),
]

neutron_defaults = [
    cfg.StrOpt('project',
               help=_("Default OpenStack project ID for "
                      "Kubernetes resources")),
    cfg.StrOpt('pod_subnet',
               help=_("Default Neutron subnet ID for Kubernetes pods")),
    cfg.ListOpt('pod_security_groups',
                help=_("Default Neutron security groups' IDs "
                       "for Kubernetes pods")),
    cfg.StrOpt('ovs_bridge',
               help=_("Default OpenVSwitch integration bridge"),
               sample_default="br-int"),
    cfg.StrOpt('service_subnet',
               help=_("Default Neutron subnet ID for Kubernetes services")),
]


CONF = cfg.CONF
CONF.register_opts(kuryr_k8s_opts)
CONF.register_opts(k8s_opts, group='kubernetes')
CONF.register_opts(neutron_defaults, group='neutron_defaults')

# in github.com/openstack/kuryr/kuryr/lib/config.py
#
#     core_opts = [
#         cfg.StrOpt('bindir',
#                    default='/usr/libexec/kuryr',
#                    help=_('Directory for Kuryr vif binding executables.')),
#         cfg.StrOpt('subnetpool_name_prefix',
#                    default='kuryrPool',
#                    help=_('Neutron subnetpool name will be prefixed by this.')),
#         cfg.StrOpt('deployment_type',
#                    default='baremetal',
#                    help=_("baremetal or nested-containers are the supported"
#                           " values.")),
#     ]
#
#
#
#     binding_opts = [
#         cfg.StrOpt('veth_dst_prefix',
#                    default='eth',
#                    help=_('The name prefix of the veth endpoint put inside the '
#                           'container.')),
#         cfg.StrOpt('driver',
#                    default='kuryr.lib.binding.drivers.veth',
#                    help=_('Driver to use for binding and unbinding ports.')),
#         cfg.StrOpt('link_iface',
#                    default='',
#                    help=_('Specifies the name of the Nova instance interface to '
#                           'link the virtual devices to (only applicable to some '
#                           'binding drivers.')),
#     ]
#
#
#     neutron_opts = [
#         cfg.StrOpt('enable_dhcp',
#                    default='True',
#                    help=_('Enable or Disable dhcp for neutron subnets.')),
#         cfg.StrOpt('default_subnetpool_v4',
#                    default='kuryr',
#                    help=_('Name of default subnetpool version 4')),
#         cfg.StrOpt('default_subnetpool_v6',
#                    default='kuryr6',
#                    help=_('Name of default subnetpool version 6')),
#         cfg.BoolOpt('vif_plugging_is_fatal',
#                     default=False,
#                     help=_("Whether a plugging operation is failed if the port "
#                            "to plug does not become active")),
#         cfg.IntOpt('vif_plugging_timeout',
#                    default=0,
#                    help=_("Seconds to wait for port to become active")),
#         cfg.StrOpt('endpoint_type',
#                    default='public',
#                    choices=['public', 'admin', 'internal'],
#                    help=_('Type of the neutron endpoint to use. This endpoint '
#                           'will be looked up in the keystone catalog and should '
#                           'be one of public, internal or admin.')),
#     ]
#
#
#
#     def register_keystoneauth_opts(conf, conf_group):
#         ks_loading.register_session_conf_options(conf, conf_group)
#         ks_loading.register_auth_conf_options(conf, conf_group)
#
#
#
#    neutron_group = cfg.OptGroup(
#        'neutron',
#        title='Neutron Options',
#        help=_('Configuration options for OpenStack Neutron'))
#
#
#
#     def register_neutron_opts(conf):
#         conf.register_group(neutron_group)
#         conf.register_opts(neutron_opts, group=neutron_group)
#         register_keystoneauth_opts(conf, neutron_group.name)
#
#
# Endpoint: 一个可以通过网络来访问和定位某个 Openstack service 的地址, 通常是一个 URL.
#     比如, 当 Nova 需要访问 Glance 服务去获取 image 时, Nova 通过访问 Keystone 拿到
#     Glance 的 endpoint. 然后通过访问该 endpoint 去获取 Glance 服务. 
#     我们可以通过 Endpoint 的 region 属性去定义多个 region.
#     Endpoint 该使用对象分为三类:
#         admin url –> 给 admin 用户使用, Post: 35357
#         internal url –> OpenStack 内部服务使用来跟别的服务通信, Port: 5000
#         public url –> 其它用户可以访问的地址, Post: 5000
#     创建完 service 后创建 API EndPoint. 在 openstack 中, 每一个 service
#     都有三种 endpoints: Admin, public, internal. 
#     Admin 是用作管理用途的, 如它能够修改 user/tenant(project). 
#     public 是让客户调用的, 比如可以部署在外网上让客户可以管理自己的云. 
#     internal 是 openstack 内部调用的. 
#     三种 endpoints 在网络上开放的权限一般也不同. 
#     Admin 通常只能对内网开放, 
#     public 通常可以对外网开放,
#     internal 通常只能对安装有 openstack 对服务的机器开放.

CONF.register_opts(lib_config.core_opts)
CONF.register_opts(lib_config.binding_opts, 'binding')
lib_config.register_neutron_opts(CONF)

logging.register_options(CONF)


def init(args, **kwargs):
    version_k8s = version.version_info.version_string()
    # 解析命令行参数
    CONF(args=args, project='kuryr-k8s', version=version_k8s, **kwargs)


def setup_logging():

    logging.setup(CONF, 'kuryr-kubernetes')
    logging.set_defaults(default_log_levels=logging.get_default_log_levels())
    version_k8s = version.version_info.version_string()
    LOG.info("Logging enabled!")
    LOG.info("%(prog)s version %(version)s",
             {'prog': sys.argv[0], 'version': version_k8s})
