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

import functools
import os
import pkg_resources
import re
import weakref

from anvil import cfg
from anvil import colorizer
from anvil import component
from anvil import decorators
from anvil import downloader as down
from anvil import exceptions as excp
from anvil import importer
from anvil import log as logging
from anvil import packager
from anvil import patcher
from anvil import shell as sh
from anvil import trace as tr
from anvil import utils

from anvil.packaging import pip
from anvil.packaging import yum

from anvil.packaging.helpers import pip_helper

from anvil.components.configurators import base as conf

LOG = logging.getLogger(__name__)

####
#### Utils...
####

# Cache of accessed packagers
_PACKAGERS = {}


def make_packager(package, default_class, **kwargs):
    packager_name = package.get('packager_name') or ''
    packager_name = packager_name.strip()
    if packager_name:
        packager_cls = importer.import_entry_point(packager_name)
    else:
        packager_cls = default_class
    if packager_cls in _PACKAGERS:
        return _PACKAGERS[packager_cls]
    p = packager_cls(**kwargs)
    _PACKAGERS[packager_cls] = p
    return p


# Remove any private keys from a package dictionary
def filter_package(pkg):
    n_pkg = {}
    for (k, v) in pkg.items():
        if not k or k.startswith("_"):
            continue
        else:
            n_pkg[k] = v
    return n_pkg

####
#### INSTALL CLASSES
####


class PkgInstallComponent(component.Component):
    def __init__(self, *args, **kargs):
        component.Component.__init__(self, *args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracewriter = tr.TraceWriter(trace_fn, break_if_there=False)
        self.configurator = conf.Configurator(self)

    def _get_download_config(self):
        return None

    def _get_download_location(self):
        key = self._get_download_config()
        if not key:
            return (None, None)
        uri = self.get_option(key, default_value='').strip()
        if not uri:
            raise ValueError(("Could not find uri in config to download "
                              "from option %s") % (key))
        return (uri, self.get_option('app_dir'))

    def download(self):
        (from_uri, target_dir) = self._get_download_location()
        if not from_uri and not target_dir:
            return []
        else:
            uris = [from_uri]
            utils.log_iterable(uris, logger=LOG,
                               header="Downloading from %s uris" % (len(uris)))
            sh.mkdirslist(target_dir, tracewriter=self.tracewriter)
            # This is used to delete what is downloaded (done before
            # fetching to ensure its cleaned up even on download failures)
            self.tracewriter.download_happened(target_dir, from_uri)
            fetcher = down.GitDownloader(self.distro, from_uri, target_dir)
            fetcher.download()
            return uris

    def patch(self, section):
        what_patches = self.get_option('patches', section)
        (_from_uri, target_dir) = self._get_download_location()
        if not what_patches:
            what_patches = []
        canon_what_patches = []
        for path in what_patches:
            if sh.isdir(path):
                canon_what_patches.extend(sorted(sh.listdir(path, files_only=True)))
            elif sh.isfile(path):
                canon_what_patches.append(path)
        if canon_what_patches:
            patcher.apply_patches(canon_what_patches, target_dir)

    def config_params(self, config_fn):
        mp = dict(self.params)
        if config_fn:
            mp['CONFIG_FN'] = config_fn
        return mp

    @property
    def packages(self):
        return self.extended_packages()

    def extended_packages(self):
        pkg_list = self.get_option('packages', default_value=[])
        if not pkg_list:
            pkg_list = []
        for name, values in self.subsystems.items():
            if 'packages' in values:
                LOG.debug("Extending package list with packages for subsystem: %r", name)
                pkg_list.extend(values.get('packages'))
        return pkg_list

    def install(self):
        pass

    def pre_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = make_packager(p, self.distro.package_manager_class,
                                      distro=self.distro)
            installer.pre_install(p, self.params)

    def post_install(self):
        pkgs = self.packages
        for p in pkgs:
            installer = make_packager(p, self.distro.package_manager_class,
                                      distro=self.distro)
            installer.post_install(p, self.params)

    def _configure_files(self):
        config_fns = self.configurator.config_files
        if config_fns:
            utils.log_iterable(config_fns, logger=LOG,
                               header="Configuring %s files" % (len(config_fns)))
            for fn in config_fns:
                tgt_fn = self.configurator.target_config(fn)
                sh.mkdirslist(sh.dirname(tgt_fn), tracewriter=self.tracewriter)
                (source_fn, contents) = self.configurator.source_config(fn)
                LOG.debug("Configuring file %s ---> %s.", (source_fn), (tgt_fn))
                contents = self.configurator.config_param_replace(fn, contents, self.config_params(fn))
                contents = self.configurator.config_adjust(contents, fn)
                sh.write_file(tgt_fn, contents, tracewriter=self.tracewriter)
        return len(config_fns)

    def _configure_symlinks(self):
        links = self.configurator.symlinks
        if not links:
            return 0
        # This sort happens so that we link in the correct order
        # although it might not matter. Either way. We ensure that the right
        # order happens. Ie /etc/blah link runs before /etc/blah/blah
        link_srcs = sorted(links.keys())
        link_srcs.reverse()
        link_nice = []
        for source in link_srcs:
            links_to_be = links[source]
            for link in links_to_be:
                link_nice.append("%s => %s" % (link, source))
        utils.log_iterable(link_nice, logger=LOG,
                           header="Creating %s sym-links" % (len(link_nice)))
        links_made = 0
        for source in link_srcs:
            links_to_be = links[source]
            for link in links_to_be:
                try:
                    LOG.debug("Symlinking %s to %s.", link, source)
                    sh.symlink(source, link, tracewriter=self.tracewriter)
                    links_made += 1
                except (IOError, OSError) as e:
                    LOG.warn("Symlinking %s to %s failed: %s", colorizer.quote(link), colorizer.quote(source), e)
        return links_made

    def prepare(self):
        pass

    def configure(self):
        return self._configure_files() + self._configure_symlinks()


class PythonInstallComponent(PkgInstallComponent):
    forced_packages = []

    def __init__(self, *args, **kargs):
        PkgInstallComponent.__init__(self, *args, **kargs)
        tools_dir = sh.joinpths(self.get_option('app_dir'), 'tools')
        self.requires_files = [
            sh.joinpths(tools_dir, 'pip-requires'),
        ]
        if self.get_bool_option('use_tests_requires', default_value=True):
            self.requires_files.append(sh.joinpths(tools_dir, 'test-requires'))

    def _get_download_config(self):
        return 'get_from'

    @property
    def python_directories(self):
        py_dirs = {}
        app_dir = self.get_option('app_dir')
        if sh.isdir(app_dir):
            py_dirs[self.name] = app_dir
        return py_dirs

    @property
    def pips_to_packages(self):
        pip_pkg_list = self.get_option('pip_to_package', default_value=[])
        if not pip_pkg_list:
            pip_pkg_list = []
        return pip_pkg_list

    def _clean_pip_requires(self):
        # Fixup these files if they exist, sometimes they have 'junk' in them
        # that anvil will install instead of pip or setup.py and we don't want
        # the setup.py file to attempt to install said dependencies since it
        # typically picks locations that either are not what we desire or if
        # said file contains editables, it may even pick external source directories
        # which is what anvil is setting up as well...
        req_fns = [f for f in self.requires_files if sh.isfile(f)]
        if req_fns:
            utils.log_iterable(req_fns, logger=LOG,
                               header="Adjusting %s pip 'requires' files" % (len(req_fns)))
            if self.forced_packages:
                forced_by_key = dict((pkg.key, pkg) for pkg in self.forced_packages)
            else:
                forced_by_key = {}
            for fn in req_fns:
                old_lines = sh.load_file(fn).splitlines()
                if forced_by_key:
                    new_lines = []
                    for line in old_lines:
                        try:
                            req = pkg_resources.Requirement.parse(line)
                            new_lines.append(str(forced_by_key[req.key]))
                        except:
                            # we don't force the package of it has a bad format
                            new_lines.append(line)
                    old_lines = new_lines
                new_lines = self._filter_pip_requires(fn, old_lines)
                contents = "# Cleaned on %s\n\n%s\n" % (utils.iso8601(), "\n".join(new_lines))
                sh.write_file_and_backup(fn, contents)
        return len(req_fns)

    def _filter_pip_requires(self, fn, lines):
        # The default does no filtering except to ensure that said lines are valid...
        return lines

    def _install_python_setups(self):
        py_dirs = self.python_directories
        if py_dirs:
            real_dirs = {}
            for (name, wkdir) in py_dirs.items():
                real_dirs[name] = wkdir
                if not real_dirs[name]:
                    real_dirs[name] = self.get_option('app_dir')
            utils.log_iterable(real_dirs.values(), logger=LOG,
                               header="Setting up %s python directories" % (len(real_dirs)))
            setup_cmd = self.distro.get_command('python', 'setup')
            for (name, working_dir) in real_dirs.items():
                sh.mkdirslist(working_dir, tracewriter=self.tracewriter)
                setup_fn = sh.joinpths(self.get_option('trace_dir'), "%s.python.setup" % (name))
                sh.execute(*setup_cmd, cwd=working_dir, run_as_root=True,
                           stderr_fn='%s.stderr' % (setup_fn),
                           stdout_fn='%s.stdout' % (setup_fn),
                           tracewriter=self.tracewriter)
                self.tracewriter.py_installed(name, working_dir)

    def install(self):
        super(PythonInstallComponent, self).install()
        self._install_python_setups()

    def prepare(self):
        self._clean_pip_requires()


####
#### RUNTIME CLASSES
####

DEFAULT_RUNNER = 'anvil.runners.fork:ForkRunner'

####
#### STATUS CONSTANTS
####
STATUS_INSTALLED = 'installed'
STATUS_STARTED = "started"
STATUS_STOPPED = "stopped"
STATUS_UNKNOWN = "unknown"


class ProgramStatus(object):
    def __init__(self, status, name=None, details=''):
        self.name = name
        self.status = status
        self.details = details


class Program(object):
    def __init__(self, name, path=None, working_dir=None, argv=None):
        self.name = name
        if path is None:
            self.path = name
        else:
            self.path = path
        self.working_dir = working_dir
        if argv is None:
            self.argv = tuple()
        else:
            self.argv = tuple(argv)

    def __str__(self):
        what = str(self.name)
        if self.path:
            what += " (%s)" % (self.path)
        return what


class ProgramRuntime(component.Component):
    @property
    def applications(self):
        # A list of applications since a single component sometimes
        # has a list of programs to start (ie nova) instead of a single application (ie the db)
        return []

    def restart(self):
        # How many applications restarted
        return 0

    def post_start(self):
        pass

    def pre_start(self):
        pass

    def statii(self):
        # A list of statuses since a single component sometimes
        # has a list of programs to report on (ie nova) instead of a single application (ie the db)
        return []

    def start(self):
        # How many applications started
        return 0

    def stop(self):
        # How many applications stopped
        return 0

    # TODO(harlowja): seems like this could be a mixin?
    def wait_active(self, between_wait=1, max_attempts=5):
        # Attempt to wait until all potentially started applications
        # are actually started (for whatever defintion of started is applicable)
        # for up to a given amount of attempts and wait time between attempts.
        num_started = len(self.applications)
        if not num_started:
            raise excp.StatusException("No %r programs started, can not wait for them to become active..." % (self.name))

        def waiter(try_num):
            LOG.info("Waiting %s seconds for component %s programs to start.", between_wait, colorizer.quote(self.name))
            LOG.info("Please wait...")
            sh.sleep(between_wait)

        for i in range(0, max_attempts):
            statii = self.statii()
            if len(statii) >= num_started:  # >= if someone reports more than started...
                not_worked = []
                for p in statii:
                    if p.status != STATUS_STARTED:
                        not_worked.append(p)
                if len(not_worked) == 0:
                    return
            else:
                # Eck less applications were found with status then what were started!
                LOG.warn("%s less applications reported status than were actually started!",
                         num_started - len(statii))
            waiter(i + 1)

        tot_time = max(0, (between_wait * max_attempts))
        raise excp.StatusException("Failed waiting %s seconds for component %r programs to become active..."
                                   % (tot_time, self.name))


class EmptyRuntime(ProgramRuntime):
    pass


class PythonRuntime(ProgramRuntime):
    def __init__(self, *args, **kargs):
        ProgramRuntime.__init__(self, *args, **kargs)
        start_trace = tr.trace_filename(self.get_option('trace_dir'), 'start')
        self.tracewriter = tr.TraceWriter(start_trace, break_if_there=True)
        self.tracereader = tr.TraceReader(start_trace)

    def app_params(self, program):
        params = dict(self.params)
        if program and program.name:
            params['APP_NAME'] = str(program.name)
        return params

    def start(self):
        # Perform a check just to make sure said programs aren't already started and bail out
        # so that it we don't unintentionally start new ones and thus causing confusion for all
        # involved...
        what_may_already_be_started = []
        try:
            what_may_already_be_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if what_may_already_be_started:
            msg = "%s programs of component %s may already be running, did you forget to stop those?"
            raise excp.StartException(msg % (len(what_may_already_be_started), self.name))

        # Select how we are going to start it and get on with the show...
        runner_entry_point = self.get_option("run_type", default_value=DEFAULT_RUNNER)
        starter_args = [self, runner_entry_point]
        starter = importer.construct_entry_point(runner_entry_point, *starter_args)
        amount_started = 0
        for program in self.applications:
            self._start_app(program, starter)
            amount_started += 1
        return amount_started

    def _start_app(self, program, starter):
        app_working_dir = program.working_dir
        if not app_working_dir:
            app_working_dir = self.get_option('app_dir')

        # Un-templatize whatever argv (program options) the program has specified
        # with whatever program params were retrieved to create the 'real' set
        # of program options (if applicable)
        app_params = self.app_params(program)
        if app_params:
            app_argv = [utils.expand_template(arg, app_params) for arg in program.argv]
        else:
            app_argv = program.argv
        LOG.debug("Starting %r using a %r", program.name, starter)

        # TODO(harlowja): clean this function params up (should just take a program)
        details_path = starter.start(program.name,
                                     app_pth=program.path,
                                     app_dir=app_working_dir,
                                     opts=app_argv)

        # This trace is used to locate details about what/how to stop
        LOG.info("Started program %s under component %s.", colorizer.quote(program.name), self.name)
        self.tracewriter.app_started(program.name, details_path, starter.name)

    def _locate_investigators(self, applications_started):
        # Recreate the runners that can be used to dive deeper into the applications list
        # that was started (a 3 tuple of (name, trace, who_started)).
        investigators_created = {}
        to_investigate = []
        for (name, _trace, who_started) in applications_started:
            investigator = investigators_created.get(who_started)
            if investigator is None:
                try:
                    investigator_args = [self, who_started]
                    investigator = importer.construct_entry_point(who_started, *investigator_args)
                    investigators_created[who_started] = investigator
                except RuntimeError as e:
                    LOG.warn("Could not load class %s which should be used to investigate %s: %s",
                             colorizer.quote(who_started), colorizer.quote(name), e)
                    continue
            to_investigate.append((name, investigator))
        return to_investigate

    def stop(self):
        # Anything to stop in the first place??
        what_was_started = []
        try:
            what_was_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if not what_was_started:
            return 0

        # Get the investigators/runners which can be used
        # to actually do the stopping and attempt to perform said stop.
        applications_stopped = []
        for (name, handler) in self._locate_investigators(what_was_started):
            handler.stop(name)
            applications_stopped.append(name)
        if applications_stopped:
            utils.log_iterable(applications_stopped,
                               header="Stopped %s programs started under %s component" % (len(applications_stopped), self.name),
                               logger=LOG)

        # Only if we stopped the amount which was supposedly started can
        # we actually remove the trace where those applications have been
        # marked as started in (ie the connection back to how they were started)
        if len(applications_stopped) < len(what_was_started):
            diff = len(what_was_started) - len(applications_stopped)
            LOG.warn(("%s less applications were stopped than were started, please check out %s"
                      " to stop these program manually."), diff, colorizer.quote(self.tracereader.filename(), quote_color='yellow'))
        else:
            sh.unlink(self.tracereader.filename())

        return len(applications_stopped)

    def statii(self):
        # Anything to get status on in the first place??
        what_was_started = []
        try:
            what_was_started = self.tracereader.apps_started()
        except excp.NoTraceException:
            pass
        if not what_was_started:
            return []

        # Get the investigators/runners which can be used
        # to actually do the status inquiry and attempt to perform said inquiry.
        statii = []
        for (name, handler) in self._locate_investigators(what_was_started):
            (status, details) = handler.status(name)
            statii.append(ProgramStatus(name=name,
                                        status=status,
                                        details=details))
        return statii


####
#### UNINSTALL CLASSES
####

class PkgUninstallComponent(component.Component):
    def __init__(self, *args, **kargs):
        component.Component.__init__(self, *args, **kargs)
        trace_fn = tr.trace_filename(self.get_option('trace_dir'), 'created')
        self.tracereader = tr.TraceReader(trace_fn)
        self.purge_packages = kargs.get('purge_packages')

    def unconfigure(self):
        self._unconfigure_links()

    def _unconfigure_links(self):
        sym_files = self.tracereader.symlinks_made()
        if sym_files:
            utils.log_iterable(sym_files, logger=LOG,
                               header="Removing %s symlink files" % (len(sym_files)))
            for fn in sym_files:
                sh.unlink(fn, run_as_root=True)

    def uninstall(self):
        self._uninstall_pkgs()
        self._uninstall_files()

    def post_uninstall(self):
        self._uninstall_dirs()

    def pre_uninstall(self):
        pass

    def _uninstall_pkgs(self):
        pkgs = self.tracereader.packages_installed()
        if pkgs:
            pkg_names = set([p['name'] for p in pkgs])
            utils.log_iterable(pkg_names, logger=LOG,
                               header="Potentially removing %s distribution packages" % (len(pkg_names)))
            which_removed = []
            with utils.progress_bar('Uninstalling', len(pkgs), reverse=True) as p_bar:
                for (i, p) in enumerate(pkgs):
                    uninstaller = make_packager(p, self.distro.package_manager_class,
                                                distro=self.distro,
                                                remove_default=self.purge_packages)
                    if uninstaller.remove(p):
                        which_removed.append(p['name'])
                    p_bar.update(i + 1)
            utils.log_iterable(which_removed, logger=LOG,
                               header="Actually removed %s distribution packages" % (len(which_removed)))

    def _uninstall_files(self):
        files_touched = self.tracereader.files_touched()
        if files_touched:
            utils.log_iterable(files_touched, logger=LOG,
                               header="Removing %s miscellaneous files" % (len(files_touched)))
            for fn in files_touched:
                sh.unlink(fn, run_as_root=True)

    def _uninstall_dirs(self):
        dirs_made = self.tracereader.dirs_made()
        dirs_alive = filter(sh.isdir, dirs_made)
        if dirs_alive:
            utils.log_iterable(dirs_alive, logger=LOG,
                               header="Removing %s created directories" % (len(dirs_alive)))
            for dir_name in dirs_alive:
                sh.deldir(dir_name, run_as_root=True)


class PythonUninstallComponent(PkgUninstallComponent):

    def uninstall(self):
        self._uninstall_python()
        PkgUninstallComponent.uninstall(self)

    def _uninstall_python(self):
        py_listing = self.tracereader.py_listing()
        if py_listing:
            py_listing_dirs = set()
            for (_name, where) in py_listing:
                py_listing_dirs.add(where)
            utils.log_iterable(py_listing_dirs, logger=LOG,
                               header="Uninstalling %s python setups" % (len(py_listing_dirs)))
            unsetup_cmd = self.distro.get_command('python', 'unsetup')
            for where in py_listing_dirs:
                if sh.isdir(where):
                    sh.execute(*unsetup_cmd, cwd=where, run_as_root=True)
                else:
                    LOG.warn("No python directory found at %s - skipping", colorizer.quote(where, quote_color='red'))


####
#### TESTING CLASSES
####


class EmptyTestingComponent(component.Component):
    def run_tests(self):
        return


class PythonTestingComponent(component.Component):
    def __init__(self, *args, **kargs):
        component.Component.__init__(self, *args, **kargs)
        self.helper = pip_helper.Helper(self.distro)

    def _get_test_exclusions(self):
        return self.get_option('exclude_tests', default_value=[])

    def _use_run_tests(self):
        return True

    def _get_test_command(self):
        # See: http://docs.openstack.org/developer/nova/devref/unit_tests.html
        # And: http://wiki.openstack.org/ProjectTestingInterface
        app_dir = self.get_option('app_dir')
        if sh.isfile(sh.joinpths(app_dir, 'run_tests.sh')) and self._use_run_tests():
            cmd = [sh.joinpths(app_dir, 'run_tests.sh'), '-N']
            if not self._use_pep8():
                cmd.append('--no-pep8')
        else:
            # Assume tox is being used, which we can't use directly
            # since anvil doesn't really do venv stuff (its meant to avoid those...)
            cmd = ['nosetests']
        # See: $ man nosetests
        if self.get_bool_option("verbose", default_value=False):
            cmd.append('--nologcapture')
        for e in self._get_test_exclusions():
            cmd.append('--exclude=%s' % (e))
        xunit_fn = self.get_option("xunit_filename")
        if xunit_fn:
            cmd.append("--with-xunit")
            cmd.append("--xunit-file=%s" % (xunit_fn))
        return cmd

    def _use_pep8(self):
        return self.get_bool_option('use_pep8', default_value=True)

    def _get_env(self):
        env_addons = {}
        tox_fn = sh.joinpths(self.get_option('app_dir'), 'tox.ini')
        if sh.isfile(tox_fn):
            # Suck out some settings from the tox file
            try:
                tox_cfg = cfg.BuiltinConfigParser(fns=[tox_fn])
                env_values = tox_cfg.get('testenv', 'setenv') or ''
                for env_line in env_values.splitlines():
                    env_line = env_line.strip()
                    env_line = env_line.split("#")[0].strip()
                    if not env_line:
                        continue
                    env_entry = env_line.split('=', 1)
                    if len(env_entry) == 2:
                        (name, value) = env_entry
                        name = name.strip()
                        value = value.strip()
                        if name.lower() != 'virtual_env':
                            env_addons[name] = value
                if env_addons:
                    LOG.debug("From %s we read in %s environment settings:", tox_fn, len(env_addons))
                    utils.log_object(env_addons, logger=LOG, level=logging.DEBUG)
            except IOError:
                pass
        return env_addons

    def run_tests(self):
        app_dir = self.get_option('app_dir')
        if not sh.isdir(app_dir):
            LOG.warn("Unable to find application directory at %s, can not run %s tests.",
                     colorizer.quote(app_dir), colorizer.quote(self.name))
            return
        cmd = self._get_test_command()
        env = self._get_env()
        with open(os.devnull, 'wb') as null_fh:
            if self.get_bool_option("verbose", default_value=False):
                null_fh = None
            try:
                sh.execute(*cmd, stdout_fh=None, stderr_fh=null_fh, cwd=app_dir, env_overrides=env)
            except excp.ProcessExecutionError as e:
                if self.get_bool_option("ignore-test-failures", default_value=False):
                    LOG.warn("Ignoring test failure of component %s: %s", colorizer.quote(self.name), e)
                else:
                    raise e


####
#### PACKAGING CLASSES
####

class EmptyPackagingComponent(component.Component):
    def package(self):
        return None
