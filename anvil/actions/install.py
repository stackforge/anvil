# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
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

from anvil import action
from anvil import colorizer
from anvil import env_rc
from anvil import log
from anvil import settings
from anvil import shell as sh
from anvil import utils

from anvil.action import PhaseFunctors

LOG = log.getLogger(__name__)


class InstallAction(action.Action):

    @staticmethod
    def get_lookup_name():
        return 'install'

    @staticmethod
    def get_action_name():
        return 'install'

    def _write_rc_file(self):
        fn = sh.abspth(settings.gen_rc_filename('core'))
        writer = env_rc.RcWriter(self.cfg, self.root_dir)
        if not sh.isfile(fn):
            LOG.info("Generating a file at %s that will contain your environment settings.", colorizer.quote(fn))
            writer.write(fn)
        else:
            LOG.info("Updating a file at %s that contains your environment settings.", colorizer.quote(fn))
            am_upd = writer.update(fn)
            LOG.info("Updated %s settings.", colorizer.quote(am_upd))

    def _run(self, persona, component_order, instances):
        self._write_rc_file()
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Downloading %s.', colorizer.quote(i.name)),
                run=lambda i: i.download(),
                end=lambda i, result: LOG.info("Performed %s downloads.", len(result))
            ),
            component_order,
            instances,
            "Download"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Configuring %s.', colorizer.quote(i.name)),
                run=lambda i: i.configure(),
                end=lambda i, result: LOG.info("Configured %s items.", colorizer.quote(result)),
            ),
            component_order,
            instances,
            "Configure"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Preinstalling %s.', colorizer.quote(i.name)),
                run=lambda i: i.pre_install(),
                end=None,
            ),
            component_order,
            instances,
            "Pre-install"
            )

        def install_start(instance):
            subsystems = set(list(instance.subsystems))
            if subsystems:
                utils.log_iterable(sorted(subsystems), logger=LOG,
                    header='Installing %s using subsystems' % colorizer.quote(instance.name))
            else:
                LOG.info("Installing %s.", colorizer.quote(instance.name))

        def install_finish(instance, result):
            if not result:
                LOG.info("Finished install of %s.", colorizer.quote(instance.name))
            else:
                LOG.info("Finished install of %s with result %s.",
                         colorizer.quote(instance.name), result)

        self._run_phase(
            PhaseFunctors(
                start=install_start,
                run=lambda i: i.install(),
                end=install_finish,
            ),
            component_order,
            instances,
            "Install"
            )
        self._run_phase(
            PhaseFunctors(
                start=lambda i: LOG.info('Post-installing %s.', colorizer.quote(i.name)),
                run=lambda i: i.post_install(),
                end=None
            ),
            component_order,
            instances,
            "Post-install",
            )
        # Knock off anything connected to uninstall
        self._delete_phase_files(['uninstall'])
