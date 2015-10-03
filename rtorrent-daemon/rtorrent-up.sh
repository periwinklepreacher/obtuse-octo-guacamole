#!/usr/bin/env /bin/bash

function log ( ) { logger "$(basename $0)[$1]: $2"; }

# Configure routing tables to implement split routing based on source IP.
# Be sure to bind torrent to the ifconfig_local address. This script should
# be called by the openvpn `--up` option.

log $LINENO "Adding torrent routing table."

grep -q torrent /etc/iproute2/rt_tables
if [ $? -ne 0 ]; then
    echo "200 torrent" >> /etc/iproute2/rt_tables
fi

ip rule add from "${ifconfig_local}" table torrent
ip route add table torrent default via "${ifconfig_remote}"
ip route add table torrent "${ifconfig_remote}" via "${ifconfig_local}" dev $dev
ip route flush cache

# Emit a torrent-up event: event handler should launch rtorrent and bind to
# ifconfig_local.

RT_ENV=( RT_LOGIN="/etc/openvpn/pia-login.ini"
         RT_CLIENTID="/etc/openvpn/pia-clientid.ini"
         RT_IPV4="${ifconfig_local}"
         RT_DEVICE="${dev}" )
log $LINENO "$(IFS=$','; echo ${RT_ENV[@]})"
initctl emit torrent-up ${RT_ENV[@]}
