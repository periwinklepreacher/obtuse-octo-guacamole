# obtuse-octo-guacamole
A set of scripts for managing multi-media programs.

<b>arbiter</b>     : A python 2 script for setting uTorrent download rate depending on state of SABnzbd.

<b>postprocess</b> : A python 2 script for moving files from uTorrent download directory to a storage folder
              or handoff to media library manager.
              
      This script pre-processes compressed archives and copies the media
      to a shared file system or for hand-off to other multimedia management
      applications.
      
      Typically used for mega-packs that often include multiple unrelated
      media files that sometimes have strangely nested and multi-part
      compressed archives.
      
      Allows the specification of untrusted files. These files are meant
      to be evaluated in a protected environment. When extracting files
      from an archive these files are encrypted and password protected.
      
      Allow a json service to be specified that returns the amount of
      available disk space to store media files: used when shared CIFS
      volumes report incorrect file system usage data.
      
      Finally, globbing is used to specify a group of media storage folders
      so that files can be copied to volumes with the most amount of
      free space.

<b>rtorrent upstart OpenVPN</b> (these files should be created in /etc/init)

<b>rtorrent.conf</b> : Start and stop rtorrent as an upstart controlled service. rtorrent is started when the VPN is established and terminated when the VPN is disconnected.

<b>port-forward.conf</b> : Polls PIA server for port forward assignment. Polling is started when VPN is established and terminated when VPN is disconnected.

<b>OpenVPN Scripts and Configuration</b> (these files should be created in /etc/openvpn)

<b>rtorrent-up.sh</b> : Creates a split routing table to restrict rtorrent traffic to the VPN. Also emits an upstart torrent-up event to launch rtorrent as a service bound to the local VPN interface.

<b>rtorrent-down.sh</b> : Deletes the torrent split routing table and emits an upstart torrent-down event. The event will cause rtorrent to be shut down and to clean up any temporary files.

<b>torrent.openvpn.conf</b> : Sample OpenVPN configuration file. Pay attention to the following attributes: script-security, route-nopull, up, down, and auth-user-pass.

<b>login.ini</b> : Two line file. First line is VPN username, and second line is VPN password.

<b>pia-clientid.ini</b> : Unique string composed of letters and numbers. Can be generated using the following commands: head -n 100 /dev/urandom | md5sum | tr -d " -"

<b>rtorrent XMLPRC</b> (the following file should be renamed to rtrpc, made executable, and created in /usr/bin)

<b>rtrpc.py</b> : Python module for interacting with rtorrent's XML-RPC interface. The port-forward.conf scripts assumes this script is executable and available in /usr/bin or in a PATH location supported by upstart.
