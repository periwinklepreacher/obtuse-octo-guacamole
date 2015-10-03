#!/usr/bin/env /bin/bash

# Tear down rules which implement split routing based on source IP. This
# script should be called by the openvpn `--down` option.

function log ( ) { logger "$(basename $0)[$1]: $2"; }

# Helpful commands used to verify routing changes.
# ip route show table all
# ip rule list

log $LINENO "Removing rtorrent routing table."

ip rule delete from "${ifconfig_local}" table rtorrent
ip route flush table rtorrent
ip route flush cache

/bin/grep -q rtorrent /etc/iproute2/rt_tables
if [ $? -eq 0 ]; then
    /bin/sed -i.backup "/rtorrent/d" /etc/iproute2/rt_tables
fi

# Emit a torrent-down event: event handler should terminate rtorrent
# and clean up any dangling resources.

RT_ENV=( RT_LOGIN="/etc/openvpn/pia-login.ini"
         RT_CLIENTID="/etc/openvpn/pia-clientid.ini"
         RT_IPV4="${ifconfig_local}"
         RT_DEVICE="${dev}" )
log $LINENO "$(IFS=$','; echo ${RT_ENV[@]})"
initctl emit torrent-down ${RT_ENV[@]}
