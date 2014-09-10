#!/bin/bash

locale -a | grep -q -e "^en_US$" && export LANG="en_US"

shopt -s nocasematch

SMITHY_NAME=$(readlink -f "$0")
cd "$(dirname "$0")"

VERBOSE="${VERBOSE:-0}"
YUM_OPTS="--assumeyes --nogpgcheck"
YUM_CONFIG_MANAGER_OPTS=""
CURL_OPTS=""
USE_SCL="${USE_SCL:-0}"  # Eventually this flag might branch for py27 and py33.

# Give access to the system packages so that when clients get installed
# after installation that the virtualenv can access them to do things like
# install images, setup keystone...
VENV_OPTS="--system-site-packages"
VENV_DIR="$PWD/.venv"
VENV_ACTIVATE="$VENV_DIR/bin/activate"
YYOOM_CMD="$PWD/tools/yyoom"

# Set the command used to create virtualenvs and invoke pip.
VIRTUALENV_CMD="virtualenv"
PIP_CMD="source $VENV_ACTIVATE && pip"
PYTHON_CMD="source $VENV_ACTIVATE && python"
if [ "$USE_SCL" != "0" ] ; then
    # Note: The use of scl introduces some complications. The chain of
    # environment variables set by the scl environment must be inherited
    # by the virtualenv.  In addition, the use of && to chain commands
    # requires that we pass this string to eval so that command splitting
    # can happen after parameter expansion.
    VIRTUALENV_CMD="source /opt/rh/python27/enable && $VIRTUALENV_CMD"
    PIP_CMD="source /opt/rh/python27/enable && $PIP_CMD"
    PYTHON_CMD="source /opt/rh/python27/enable && $PYTHON_CMD"
fi

if [ "$VERBOSE" == "0" ]; then
    YUM_OPTS="$YUM_OPTS -q"
    CURL_OPTS="-s"
    VENV_OPTS="$VENV_OPTS -q"
fi

# Source in our variables (or overrides)
source ".anvilrc"
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [ -n "$USER_HOME" ]; then
        HOME_RC="${USER_HOME}/.anvilrc"
        if [ -f "$HOME_RC" ]; then
            source "$HOME_RC"
        fi
    fi
fi

dump_list()
{
    for var in "$@"; do
        for name in $var; do
            echo "  - $name"
        done
    done
}

yum_install()
{
    local requires=$@
    if [ "$VERBOSE" == "0" ]; then
        yum install $YUM_OPTS $requires > /dev/null 2>&1
    else
        yum install $YUM_OPTS $requires
    fi
    return $?
}

yum_remove()
{
    local remove=$@
    if [ "$VERBOSE" == "0" ]; then
        yum remove $YUM_OPTS $remove > /dev/null 2>&1
    else
        yum remove $YUM_OPTS $remove
    fi
    return $?
}

bootstrap_rpm_packages()
{
    if [ -n "$REQUIRES" ]; then
        echo -e "Installing system packages:"
        dump_list $REQUIRES
        echo "Please wait..."
        yum_install $REQUIRES
        if [ "$?" != "0" ]; then
            echo -e "Failed installing!"
            return 1
        fi
    fi
    if [ -n "$CONFLICTS" ]; then
        echo -e "Removing conflicting system packages:"
        dump_list $CONFLICTS
        echo "Please wait..."
        yum_remove $CONFLICTS
        if [ "$?" != "0" ]; then
            echo -e "Failed removing!"
            return 1
        fi
    fi
    return 0
}

clean_anvil_deps()
{
    # A previously failed anvil build which is not fully cleaned
    # up has the potential for leaving broken packages.  We disable
    # the anvil-deps repo on bootstrap to avoid subsequent yum failures
    # when pulling packages from this repo during bootstrap.
    yum-config-manager $YUM_CONFIG_MANAGER_OPTS --disable anvil-deps
}

bootstrap_scl()
{
    # Read scl variables.
    source "tools/bootstrap/SCLRepo"
    # Create the repo configuration file if it doesn't already exist.
    if [ ! -s $SCL_REPO_FN ] ; then
        touch $SCL_REPO_FN
        if [ $? -ne 0 ] ; then
            echo "Unable to create $SCL_REPO_FN"
            return 1
        fi
        echo "$SCL_REPO_FN_DATA" > $SCL_REPO_FN
        if [ ! -s $SCL_REPO_FN ] ; then
            echo "Unable to write to $SCL_REPO_FN"
            return 1
        fi
        chmod 444 $SCL_REPO_FN
    fi
    # Install the repo gpg key if it doesn't already exist.
    if [ ! -s $SCL_REPO_GPG_KEY_FN ] ; then
        wget $SCL_REPO_GPG_KEY_URL --output-document $SCL_REPO_GPG_KEY_FN
        if [ $? -ne 0 ] ; then
            echo "Fail from $SCL_REPO_GPG_KEY_URL to $SCL_REPO_GPG_KEY_FN"
            return 1
        fi
    fi
    # Install and remove scl specific packages.
    # I wish this code were better, but here is why it isn't:
    # bootstrap_rpm_packages uses global variables to obtain lists of
    # packages to install and remove.  Save the state of those lists to
    # temporary variables in order to be able to reuse the code in
    # bootstrap_rpm_packages when bootstrapping scl.
    OLD_REQUIRES="$REQUIRES"
    REQUIRES="$SCL_REQUIRES_PYTHON27"
    OLD_CONFLICTS="$CONFLICTS_PYTHON27"
    CONFLICTS="$SCL_CONFLICTS"
    bootstrap_rpm_packages
    if [ $? -ne 0 ] ; then
        echo "Unable to bootstrap scl required packages"
        return 1
    fi
    REQUIRES="$OLD_REQUIRES"
    CONFLICTS="$OLD_CONFLICTS"
    return 0
}

clean_pip()
{
    # See: https://github.com/pypa/pip/issues/982
    if [ -n "$SUDO_USER" ]; then
        rm -rf "/tmp/pip-build-$SUDO_USER"
    fi
}

bootstrap_epel()
{
    # Installs the repository that will allow for installation of packages
    # from epel, see https://fedoraproject.org/wiki/EPEL for information
    # about what is epel.
    [ -z "$EPEL_RPM_URL" ] && return 0
    echo "Installing epel rpm from $EPEL_RPM_URL"
    cache_and_install_rpm_url "$EPEL_RPM_URL"
    return $?
}

bootstrap_repos()
{
    # Installs other repositories that will allow for installation of packages
    # from places other than epel. This allows for anvil to find dependencies
    # from other places (so anvil can avoid building those dependencies in the
    # first place).
    [ -z "$REPO_URLS" ] && return 0
    # If urls were provided but no directory, that's bad.
    [ -z "$REPO_DIR" ] && return 1
    for repo_url in $REPO_URLS; do
        echo "Installing repo file from $repo_url -> $REPO_DIR"
        local base_filename=$(basename $repo_url)
        local output_filename="$REPO_DIR/$base_filename"
        if [ "$VERBOSE" == "0" ]; then
            wget -q "$repo_url" -O "$output_filename"
        else
            wget "$repo_url" -O "$output_filename"
        fi
        if [ "$?" != "0" ]; then
            echo -e "Failed downloading $repo_url -> $output_filename"
            return 1
        fi
    done
    return 0
}

unsudo()
{
    # If a sudo user is active the given files/directories will be changed to
    # be owned by that user instead of the current root user, if no sudo user
    # is active, then nothing changes.
    if [ -n "$SUDO_UID" -a -n "$SUDO_GID" ]; then
        if [ "$VERBOSE" == "0" ]; then
            chown -R "$SUDO_UID:$SUDO_GID" $@
        else
            chown -R -c "$SUDO_UID:$SUDO_GID" $@
        fi
    fi
}

bootstrap_virtualenv()
{
    # Creates a virtualenv and then installs anvils requirements in it.
    # Use subshells to avoid polluting environment vars in calling process.
    echo "Setting up virtualenv in $VENV_DIR"
    eval "($VIRTUALENV_CMD $VENV_OPTS $VENV_DIR || return 1)"
    unsudo $VENV_DIR
    local deps=$(cat requirements.txt | grep -v '^$\|^\s*\#' | sort)
    if [ -n "$deps" ]; then
        echo "Installing anvil dependencies in $VENV_DIR"
        dump_list $deps
        echo "Please wait..."
        if [ "$VERBOSE" == "0" ]; then
            eval "($PIP_CMD install -r requirements.txt)" > /dev/null 2>&1
        else
            eval "($PIP_CMD install -v -r requirements.txt)"
        fi
        if [ "$?" != "0" ]; then
            return 1
        fi
    fi
    unsudo $VENV_DIR
}

bootstrap_selinux()
{
    # See if selinux is on.
    echo "Enabling selinux for yum like binaries."
    if [ "$(getenforce)" == "Enforcing" ]; then
        # Ensure all yum api interacting binaries are ok to be used.
        chcon -h "system_u:object_r:rpm_exec_t:s0" "$YYOOM_CMD"
    fi
}

run_smithy()
{
    # We used to exec to python, but prolly not good with eval.
    eval "($PYTHON_CMD anvil $ARGS)"
    exit $?
}

puke()
{
    local cleaned_force=$(echo "$FORCE" | sed -e 's/\([A-Z]\)/\L\1/g;s/\s//g')
    if [ "$cleaned_force" != "yes" ]; then
        echo -e "To run anyway set FORCE=yes and rerun." >&2
        exit 1
    fi
}

needs_bootstrap()
{
    # Checks if we need to perform the bootstrap phase.
    if [ "$BOOTSTRAP" == "true" ]; then
        return 0
    fi
    if [ ! -d "$VENV_DIR" -o ! -f "$VENV_ACTIVATE" -o ! -f "$VENV_DIR/bin/pip" ]; then
        return 0
    fi
    return 1
}

rpm_is_installed()
{
    # Checks if an rpm is already installed.
    local name=$(basename "$1")
    rpm -q "${name%.rpm}" &>/dev/null
    return $?
}

cache_and_install_rpm_url()
{
    # Downloads an rpm from a url and then installs it (if it's not already
    # installed).
    url=${1:?"Error: rpm url is undefined!"}
    cachedir=${RPM_CACHEDIR:-'/tmp'}
    rpm=$(basename "$url")
    if rpm_is_installed "$rpm"; then
        return 0
    fi
    echo $rpm "not already installed"
    if [ ! -f "$cachedir/$rpm" ]; then
        echo -e "Downloading ${rpm} to ${cachedir}"
        curl $CURL_OPTS "$url" -o "$cachedir/$rpm" || return 1
    fi
    echo -e "Installing $cachedir/$rpm"
    if [ $2 = "True" ]; then
        rpm -i "$cachedir/$rpm" --nodeps;
    else
        yum_install "$cachedir/$rpm";
    fi
    return $?
}

greatest_version()
{
    for arg in "$@"; do
        echo "$arg"
    done | sort --version-sort --reverse | head -n1
}

## Identify which bootstrap configuration file to use: either set
## explicitly (BSCONF_FILE) or determined based on the os distribution:
BSCONF_DIR="${BSCONF_DIR:-$(dirname $(readlink -f "$0"))/tools/bootstrap}"
get_os_info()
{
    if [ "$(uname)" = "Linux" ] ; then
        if [ -f /etc/redhat-release ] ; then
            PKG="rpm"
            OSNAME=`cat /etc/redhat-release`
            OSDIST=`cat /etc/redhat-release | sed -e 's/release.*$//g;s/\s//g'`
            PSUEDONAME=`cat /etc/redhat-release | sed s/.*\(// | sed s/\)//`
            RELEASE=`cat /etc/redhat-release | sed s/.*release\ // | sed s/\ .*//`
        elif [ -f /etc/debian_version ] ; then
            PKG="deb"
            OSDIST=`cat /etc/lsb-release | grep '^DISTRIB_ID' | awk -F= '{ print $2 }'`
            PSUEDONAME=`cat /etc/lsb-release | grep '^DISTRIB_CODENAME' | awk -F= '{ print $2 }'`
            RELEASE=`cat /etc/lsb-release | grep '^DISTRIB_RELEASE' | awk -F= '{ print $2 }'`
            OSNAME="$OSDIST $RELEASE ($PSUEDONAME)"
        fi
    fi
}

get_os_info

if [ -z "$BSCONF_FILE" ]; then
    BSCONF_FILE="$BSCONF_DIR/$OSDIST"
fi

ARGS=""
BOOTSTRAP=false

# Ad-hoc getopt to handle long opts.
#
# Smithy opts are consumed while those to anvil are copied through.
while [ "$#" != 0 ]; do
    case "$1" in
    '--bootstrap')
        BOOTSTRAP=true
        shift
        ;;
    '--force')
        FORCE=yes
        shift
        ;;
    *)
        ARGS="$ARGS $1"
        shift
        ;;
    esac
done

# Source immediately so that we can export the needed variables.
if [ -f "$BSCONF_FILE" ]; then
    source "$BSCONF_FILE"
fi

if ! needs_bootstrap; then
    clean_pip
    run_smithy
else
    clean_anvil_deps
fi

if [ "$BOOTSTRAP" == "false" ]; then
    echo "This system needs to be updated in order to run anvil!" >&2
    echo "Running 'sudo $SMITHY_NAME --bootstrap' will attempt to do so." >&2
    puke
fi

## Bootstrap smithy
if [ "$(id -u)" != "0" ]; then
    echo "You must run '$SMITHY_NAME --bootstrap' with root privileges!" >&2
    exit 1
fi

if [ ! -f "$BSCONF_FILE" ]; then
    echo "Anvil has not been tested on distribution '$OSNAME'" >&2
    puke
else
    MIN_RELEASE=${MIN_RELEASE:?"Error: MIN_RELEASE is undefined!"}
    SHORTNAME=${SHORTNAME:?"Error: SHORTNAME is undefined!"}
    if [ "$RELEASE" != "$(greatest_version "$RELEASE" "$MIN_RELEASE")" ]; then
        echo "This script must be run on $SHORTNAME $MIN_RELEASE+ and not $SHORTNAME $RELEASE." >&2
        puke
    fi
fi

# If we got here then we must be in force mode, setup with the default configuration
# file for unknown distros...
if [ ! -f "$BSCONF_FILE" ]; then
    BSCONF_FILE="$BSCONF_DIR/Unknown"
    SHORTNAME="$OSDIST"
    source "$BSCONF_FILE"
fi

if [ "$USE_SCL" != "0" ] ; then
    echo "Prepending scl to bootstrap: $STEPS"
    STEPS="scl $STEPS"
fi

echo "Bootstrapping $SHORTNAME $RELEASE"
echo "Please wait..."
clean_pip
for step in ${STEPS:?"Error: STEPS is undefined!"}; do
    echo "--- Running bootstrap step $step ---"
    "bootstrap_${step}"
    if [ $? != 0 ]; then
        echo "Bootstrapping $SHORTNAME $RELEASE failed." >&2
        exit 1
    fi
done
clean_pip

# Anvil writes configurations in these locations, make sure they are created
# and that the user running this script can actually access those files (even
# later if they are not running with sudo).
mkdir -p -v /etc/anvil /usr/share/anvil
touch /var/log/anvil.log
unsudo /etc/anvil /usr/share/anvil /var/log/anvil.log

echo "Bootstrapped for $SHORTNAME $RELEASE"
ARGS="-a moo"
run_smithy
