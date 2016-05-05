%global _without_doc 1
%global with_doc %{!?_without_doc:1}%{?_without_doc:0}
%global python_name ceilometer
%global daemon_prefix openstack-ceilometer
%global os_version ${version}

%if ! 0%{?overwrite_configs}
%global configfile %config(noreplace)
%else
%global configfile %verify(mode)
%endif

Name:             openstack-ceilometer
Version:          %{os_version}$version_suffix
Release:          $release%{?dist}
Summary:          OpenStack measurement collection service
Epoch:            $epoch

Group:            Applications/System
License:          ASL 2.0
URL:              https://wiki.openstack.org/wiki/Ceilometer
Source0:          %{python_name}-%{os_version}.tar.gz
Source1:          ceilometer-dist.conf
Source2:          ceilometer.logrotate
Source4:          ceilometer-rootwrap-sudoers
Source5:          openstack-ceilometer-polling

%if ! (0%{?rhel} > 6)
Source10:         openstack-ceilometer-api.init
Source11:         openstack-ceilometer-collector.init
Source12:         openstack-ceilometer-compute.init
Source13:         openstack-ceilometer-central.init
Source14:         openstack-ceilometer-alarm-notifier.init
Source15:         openstack-ceilometer-alarm-evaluator.init
Source16:         openstack-ceilometer-notification.init
Source17:         openstack-ceilometer-ipmi.init
Source18:         openstack-ceilometer-polling.init
%else
Source10:         openstack-ceilometer-api.service
Source11:         openstack-ceilometer-collector.service
Source12:         openstack-ceilometer-compute.service
Source13:         openstack-ceilometer-central.service
Source14:         openstack-ceilometer-alarm-notifier.service
Source15:         openstack-ceilometer-alarm-evaluator.service
Source16:         openstack-ceilometer-notification.service
Source17:         openstack-ceilometer-ipmi.service
Source18:         openstack-ceilometer-polling.service
%endif


#for $idx, $fn in enumerate($patches)
Patch$idx: $fn
#end for

BuildRoot:        %{_tmppath}/%{name}-%{version}-%{release}

BuildArch:        noarch
BuildRequires:    intltool
BuildRequires:    systemd-units

#Rhel6 requires
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-sphinx10
# These are required to build due to the requirements check added
BuildRequires:    python-sqlalchemy0.7
%endif

#rhel7 requires
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-sqlalchemy
%endif

BuildRequires:    python-setuptools
BuildRequires:    python-pbr
BuildRequires:    python-d2to1
BuildRequires:    python2-devel
#Rhel6 requires
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-webob1.2
%endif

#rhel7 requires
%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-webob
%endif

%description
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

%package -n       python-ceilometer
Summary:          OpenStack ceilometer python libraries
Group:            Applications/System

#for $i in $requires
Requires:         ${i}
#end for

#for $i in $conflicts
Conflicts:       ${i}
#end for

%description -n   python-ceilometer
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer python library.

%package common
Summary:          Components common to all OpenStack ceilometer services
Group:            Applications/System

Requires:         python-ceilometer = %{epoch}:%{version}-%{release}

Requires(pre):    shadow-utils

%description common
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains components common to all OpenStack
ceilometer services.

%package compute
Summary:          OpenStack ceilometer compute agent
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         %{name}-polling = %{epoch}:%{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         libvirt-python

%description compute
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer agent for
running on OpenStack compute nodes.

%package central
Summary:          OpenStack ceilometer central agent
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         %{name}-polling = %{epoch}:%{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         python-glanceclient
Requires:         python-swiftclient

%description central
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the central ceilometer agent.

%package collector
Summary:          OpenStack ceilometer collector agent
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

Requires:         python-pymongo

%description collector
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer collector agent.

%package api
Summary:          OpenStack ceilometer API service
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

Requires:         python-pymongo
Requires:         python-flask
Requires:         python-pecan
Requires:         python-wsme

%description api
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer API service.

%package alarm
Summary:          OpenStack ceilometer alarm services
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         python-ceilometerclient

%description alarm
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer alarm notification
and evaluation services.

%package notification
Summary:          OpenStack ceilometer notifier services
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         python-ceilometerclient

%description notification
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ceilometer alarm notification
and evaluation services.

%package ipmi
Summary:          OpenStack ceilometer ipmi agent
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}
Requires:         %{name}-polling = %{epoch}:%{version}-%{release}

Requires:         python-novaclient
Requires:         python-keystoneclient
Requires:         python-neutronclient
Requires:         python-tooz
Requires:         python-oslo-rootwrap
Requires:         ipmitool

%description ipmi
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains the ipmi agent to be run on OpenStack
nodes from which IPMI sensor data is to be collected directly,
by-passing Ironic's management of baremetal.

%package polling
Summary:          OpenStack ceilometer polling agent
Group:            Applications/System

Requires:         %{name}-common = %{epoch}:%{version}-%{release}

%description polling
Ceilometer aims to deliver a unique point of contact for billing systems to
aquire all counters they need to establish customer billing, across all
current and future OpenStack components. The delivery of counters must
be tracable and auditable, the counters must be easily extensible to support
new projects, and agents doing data collections should be
independent of the overall system.

This package contains the polling service.


%if 0%{?with_doc}
%package doc
Summary:          Documentation for OpenStack ceilometer
Group:            Documentation

# Required to build module documents
BuildRequires:    python-eventlet
%if ! (0%{?fedora} <= 12 || 0%{?rhel} <= 6)
BuildRequires:    python-sqlalchemy0.7
%endif

%if ! (0%{?fedora} > 12 || 0%{?rhel} > 6)
BuildRequires:    python-sqlalchemy
%endif

BuildRequires:    python-webob
# while not strictly required, quiets the build down when building docs.
BuildRequires:    python-migrate
BuildRequires:    python-iso8601

%description      doc
OpenStack ceilometer provides services to measure and
collect metrics from OpenStack components.

This package contains documentation files for ceilometer.
%endif

%prep
%setup -q -n %{python_name}-%{os_version}

#raw
find . \( -name .gitignore -o -name .placeholder \) -delete

find ceilometer -name \*.py -exec sed -i '/\/usr\/bin\/env python/{d;q}' {} +

# TODO: Have the following handle multi line entries
sed -i '/setup_requires/d; /install_requires/d; /dependency_links/d' setup.py

#end raw
#for $idx, $fn in enumerate($patches)
%patch$idx -p1
#end for

%build

export PBR_VERSION=$version
%{__python} setup.py build

%install

export PBR_VERSION=$version
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

#raw
# docs generation requires everything to be installed first
export PYTHONPATH="$( pwd ):$PYTHONPATH"

pushd doc

%if 0%{?with_doc}
SPHINX_DEBUG=1 sphinx-1.0-build -b html source build/html
# Fix hidden-file-or-dir warnings
rm -fr build/html/.doctrees build/html/.buildinfo
%endif

popd
#end raw

# Setup directories
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer/tmp
install -d -m 755 %{buildroot}%{_localstatedir}/log/ceilometer
install -d -m 755 %{buildroot}%{_sharedstatedir}/ceilometer/rootwrap.d

# Install config files
install -d -m 755 %{buildroot}%{_sysconfdir}/sysconfig
install -d -m 755 %{buildroot}%{_sysconfdir}/ceilometer

install -p -D -m 640 ceilometer/meter/data/meters.yaml %{buildroot}%{_sysconfdir}/ceilometer/meters.yaml

#raw
for i in etc/ceilometer/*; do
    if [ -f $i ] ; then
        install -p -D -m 640 $i  %{buildroot}%{_sysconfdir}/ceilometer
    fi
done
#end raw
mkdir -p %{buildroot}%{_sysconfdir}/ceilometer/rootwrap.d/
install -p -D -m 644 etc/ceilometer/rootwrap.d/* %{buildroot}%{_sysconfdir}/ceilometer/rootwrap.d/
install -p -D -m 644 %{SOURCE5} %{buildroot}%{_sysconfdir}/sysconfig/openstack-ceilometer-polling

%if ! (0%{?rhel} > 6)
# Install initscripts for services
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_initrddir}/%{name}-api
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_initrddir}/%{name}-collector
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_initrddir}/%{name}-compute
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_initrddir}/%{name}-central
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_initrddir}/%{name}-alarm-notifier
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_initrddir}/%{name}-alarm-evaluator
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_initrddir}/%{name}-notification
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_initrddir}/%{name}-ipmi
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_initrddir}/%{name}-polling
%else
install -p -D -m 755 %{SOURCE10} %{buildroot}%{_unitdir}/%{name}-api.service
install -p -D -m 755 %{SOURCE11} %{buildroot}%{_unitdir}/%{name}-collector.service
install -p -D -m 755 %{SOURCE12} %{buildroot}%{_unitdir}/%{name}-compute.service
install -p -D -m 755 %{SOURCE13} %{buildroot}%{_unitdir}/%{name}-central.service
install -p -D -m 755 %{SOURCE14} %{buildroot}%{_unitdir}/%{name}-alarm-notifier.service
install -p -D -m 755 %{SOURCE15} %{buildroot}%{_unitdir}/%{name}-alarm-evaluator.service
install -p -D -m 755 %{SOURCE16} %{buildroot}%{_unitdir}/%{name}-notification.service
install -p -D -m 755 %{SOURCE17} %{buildroot}%{_unitdir}/%{name}-ipmi.service
install -p -D -m 755 %{SOURCE18} %{buildroot}%{_unitdir}/%{name}-polling.service
%endif

%if ! (0%{?rhel} > 6)
sed -i "s#/usr/bin/ceilometer-notification#/usr/bin/ceilometer-agent-notification#" %{buildroot}%{_initrddir}/%{name}-notification
%else
sed -i "s#/usr/bin/ceilometer-notification#/usr/bin/ceilometer-agent-notification#" %{buildroot}%{_unitdir}/%{name}-notification.service
%endif

# Install logrotate
install -p -D -m 644 %{SOURCE2} %{buildroot}%{_sysconfdir}/logrotate.d/%{name}

# Install pid directory
%if 0%{?rhel} && 0%{?rhel} <= 6
install -d -m 755 %{buildroot}%{_localstatedir}/run/ceilometer
%endif

# Remove unneeded in production stuff
rm -f %{buildroot}%{_bindir}/ceilometer-debug
rm -fr %{buildroot}%{python_sitelib}/tests/
rm -fr %{buildroot}%{python_sitelib}/run_tests.*
rm -f %{buildroot}/usr/share/doc/ceilometer/README*
rm -f %{buildroot}/%{python_sitelib}/ceilometer/api/v1/static/LICENSE.*

%pre common
getent group ceilometer >/dev/null || groupadd -r ceilometer --gid 166
if ! getent passwd ceilometer >/dev/null; then
  # Id reservation request: https://bugzilla.redhat.com/923891
  useradd -u 166 -r -g ceilometer -G ceilometer,nobody -d %{_sharedstatedir}/ceilometer -s /sbin/nologin -c "OpenStack ceilometer Daemons" ceilometer
fi
exit 0

%files common
%doc LICENSE
%dir %{_sysconfdir}/ceilometer
%configfile %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/*

%configfile %{_sysconfdir}/logrotate.d/%{name}
%dir %attr(0755, ceilometer, root) %{_localstatedir}/log/ceilometer
%if 0%{?rhel} && 0%{?rhel} <= 6
%dir %attr(0755, ceilometer, root) %{_localstatedir}/run/ceilometer
%endif

%{_bindir}/ceilometer-dbsync
%{_bindir}/ceilometer-expirer

%defattr(-, ceilometer, ceilometer, -)
%dir %{_sharedstatedir}/ceilometer
%dir %{_sharedstatedir}/ceilometer/tmp

%files -n python-ceilometer
%{python_sitelib}/ceilometer
%{python_sitelib}/ceilometer-%{os_version}*.egg-info

%if 0%{?with_doc}
%files doc
%doc doc/build/html
%endif

%files compute
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-compute
%else
%{_unitdir}/%{name}-compute.service
%endif

%if 0%{?rhel} > 6
%post compute
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-compute.service
fi

%preun compute
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-compute.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-compute.service > /dev/null 2>&1 || :
fi

%postun compute
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-compute.service #>/dev/null 2>&1 || :
fi
%endif

%files collector
%{_bindir}/ceilometer-collector*
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-collector
%else
%{_unitdir}/%{name}-collector.service
%endif

%if 0%{?rhel} > 6
%post collector
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-collector.service
fi

%preun collector
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-collector.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-collector.service > /dev/null 2>&1 || :
fi

%postun collector
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-collector.service #>/dev/null 2>&1 || :
fi
%endif

%files api
%{_bindir}/ceilometer-api
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-api
%else
%{_unitdir}/%{name}-api.service
%endif

%if 0%{?rhel} > 6
%post api
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-api.service
fi

%preun api
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-api.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-api.service > /dev/null 2>&1 || :
fi

%postun api
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-api.service #>/dev/null 2>&1 || :
fi
%endif

%files central
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-central
%else
%{_unitdir}/%{name}-central.service
%endif

%if 0%{?rhel} > 6
%post central
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-central.service
fi

%preun central
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-central.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-central.service > /dev/null 2>&1 || :
fi

%postun central
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-central.service #>/dev/null 2>&1 || :
fi
%endif

%files alarm
%{_bindir}/ceilometer-alarm-notifier
%{_bindir}/ceilometer-alarm-evaluator
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-alarm-notifier
%{_initrddir}/%{name}-alarm-evaluator
%else
%{_unitdir}/%{name}-alarm-notifier.service
%{_unitdir}/%{name}-alarm-evaluator.service
%endif

%if 0%{?rhel} > 6
%post alarm
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-alarm-notifier.service
        /usr/bin/systemctl preset %{name}-alarm-evaluator.service
fi

%preun alarm
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-alarm-notifier.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-alarm-notifier.service > /dev/null 2>&1 || :
        /usr/bin/systemctl --no-reload disable %{name}-alarm-evaluator.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-alarm-evaluator.service > /dev/null 2>&1 || :
fi

%postun alarm
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-alarm-notifier.service #>/dev/null 2>&1 || :
        /usr/bin/systemctl try-restart %{name}-alarm-evaluator.service #>/dev/null 2>&1 || :
fi
%endif

%files notification
%configfile %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/meters.yaml
%configfile %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/event_pipeline.yaml
%configfile %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/event_definitions.yaml
%{_bindir}/ceilometer-agent-notification
%{_bindir}/ceilometer-send-sample
%if ! (0%{?rhel} > 6)
%{_initrddir}/%{name}-notification
%else
%{_unitdir}/%{name}-notification.service
%endif

%if 0%{?rhel} > 6
%post notification
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-notification.service
fi

%preun notification
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-notification.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-notification.service > /dev/null 2>&1 || :
fi

%postun notification
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-notification.service #>/dev/null 2>&1 || :
fi
%endif

%files ipmi
%configfile %attr(-, root, ceilometer) %{_sysconfdir}/ceilometer/rootwrap.d/ipmi.filters
%{_bindir}/ceilometer-rootwrap
%if 0%{?rhel} && 0%{?rhel} <= 6
%{_initrddir}/%{name}-ipmi
%else
%{_unitdir}/%{name}-ipmi.service
%endif


%if 0%{?rhel} > 6
%post ipmi
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-ipmi.service
fi

%preun ipmi
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-ipmi.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-ipmi.service > /dev/null 2>&1 || :
fi

%postun ipmi
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-ipmi.service #>/dev/null 2>&1 || :
fi
%endif

%files polling
%{_bindir}/ceilometer-polling
%if 0%{?rhel} && 0%{?rhel} <= 6
%{_initrddir}/%{name}-polling
%else
%attr(-, root, ceilometer) %{_sysconfdir}/sysconfig/openstack-ceilometer-polling
%{_unitdir}/%{name}-polling.service
%endif

%if 0%{?rhel} > 6
%post polling
if [ $1 -eq 1 ] ; then
        # Initial installation
        /usr/bin/systemctl preset %{name}-polling.service
fi

%preun polling
if [ $1 -eq 0 ] ; then
        # Package removal, not upgrade
        /usr/bin/systemctl --no-reload disable %{name}-polling.service > /dev/null 2>&1 || :
        /usr/bin/systemctl stop %{name}-polling.service > /dev/null 2>&1 || :
fi

%postun polling
/usr/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # Package upgrade, not uninstall
        /usr/bin/systemctl try-restart %{name}-polling.service #>/dev/null 2>&1 || :
fi
%endif

%changelog
