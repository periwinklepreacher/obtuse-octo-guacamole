## A set of scripts for managing multi-media programs

**arbiter** : A python 2 script for setting uTorrent download rate depending on the state of SABnzbd.

**rtorrent OpenVPN Debian Linux (Mint 17.2)** : A set of scripts for running rtorrent as an upstart controlled daemon process connected to the internet via split routing, sandboxed, killswitch, and using an internet VPN service.

**postprocess** : A python 2 script for copying files from the uTorrent download directory to a local file server or to handoff to a local media library manager.

- - - - -
## <span style="background-color:yellow; ">arbiter</span>

Simple script that limits uTorrent bandwidth by enabling the uTorrent scheduler whenever SABnzbd is in a 'Downloading' state. The underlying communications framework could be used to implement a different set of cross-application schedules and priorities.

    usage: arbiter [-h] --shost SHOST --sport SPORT --apikey APIKEY --uhost UHOST
                   --uport UPORT --uname UNAME --upasswd UPASSWD
                   [--level {info,all,warning,critical,error,debug}]
                   [--logfile LOGFILE]

    optional arguments:
      -h, --help            show this help message and exit
      --shost SHOST         IP or name of SABnzbd host.
      --sport SPORT         SABnzbd API port.
      --apikey APIKEY       This key gives 3rd party programs full access to
                            SABnzbd API.
      --uhost UHOST         IP or name of uTorrent host.
      --uport UPORT         uTorrent WebUI port.
      --uname UNAME         uTorrent WebUI user name.
      --upasswd UPASSWD     uTorrent WebUI password.
      --level {info,all,warning,critical,error,debug}
                            Console messages are filtered by this severity.
      --logfile LOGFILE     Name of the log file. The log file is not filtered by
                            the level setting.

**Installation**

Copy the arbiter script into a location accessible by cron. For example, as root user copy the script to `/root/arbiter`. Set execute permissions and ownership of the script using `chmod 755 arbiter` and `chown root:root arbiter`.

Run manually to verify installation and file permissions then add to cron. Running the script every 5 to 15 mins should be fine.
```
/root/arbiter --shost sabhost --sport 8100 --apikey 9d35c65529e0229f1ae3f \
              --uhost uthost --uport 8200 --uname homer --upasswd doh
```

```
crontab -e
*/5 * * * * /root/arbiter --shost sabhost --sport 8100 --apikey 9d35c65529e0229f1ae3f \
                          --uhost uthost --uport 8200 --uname homer --upasswd doh >/dev/null 2>&1
```

**Verification**

| description | shell command | verify |
|-------------|---------------|--------|
| Python 2.7.X is installed | `python2 --version` | Python 2.7.10 |
| Execute permissions are set | `ls -la arbiter` | -rwxr-xr-x 1 root root 8221 Jan 04 19:02 arbiter |
| SABnzbd Host, Port, Key configured and enabled | SABnzbd > Config > General | http://wiki.sabnzbd.org/configure-general-0-7 |
| uTorrent Host, Port, User, Password configured and enabled | uTorrent > Preferences > WebUI | http://forum.utorrent.com/topic/49588-%C2%B5torrent-webui/ |
| Running manually generates a log entry (default location is /var/log/arbiter.log) | `tail -f /var/log/arbiter.log` | Jan-16 04:00:01 SABnzbd is IDLE uTorrent sched_enable set to 0 |

## <span style="background-color:yellow; ">rtorrent OpenVPN Debian Linux (Mint 17.2)</span>

Follow this link to get rtorrent installed and running on a debian system (skip the init.d integration as the scripts that follow use upstart and openvpn to secure and control an rtorrent daemon):
http://terminal28.com/how-to-install-and-configure-rutorrent-rtorrent-libtorrent-xmlrpc-screen-debian-7-wheezy/

**rtorrent upstart (these files should be copied to /etc/init)**

| file | description |
|------|-------------|
| **rtorrent.conf** | Start and stop rtorrent as an upstart controlled service. rtorrent is started when the VPN is established and terminated when the VPN is disconnected.|
| **port-forward.conf** | Polls PIA server for port forward assignment. Polling is started when VPN is established and terminated when VPN is disconnected. |

**OpenVPN Scripts and Configuration (these files should be copied to /etc/openvpn)**

| file | description |
|------|-------------|
|**rtorrent-up.sh** | Creates a split routing table to restrict rtorrent traffic to the VPN. Also emits an upstart torrent-up event to launch rtorrent as a service bound to the local VPN interface. |
| **rtorrent-down.sh** | Deletes the torrent split routing table and emits an upstart torrent-down event. The event will cause rtorrent to be shut down and to clean up any temporary files. |
| **torrent.openvpn.conf** | Sample OpenVPN configuration file. Pay attention to the following attributes: script-security, route-nopull, up, down, and auth-user-pass. |
| **login.ini** | Two line file. First line is VPN username, and second line is VPN password. |
| **pia-clientid.ini** | Unique string composed of letters and numbers. Can be generated using the following commands: <code>head -n 100 /dev/urandom &#124; md5sum &#124; tr -d " -"</code> |

**rtorrent XMLRPC (the following file should be renamed to rtrpc, made executable, and copied to /usr/bin)**

| file | description |
|------|-------------|
| **rtrpc.py** | Python module for interacting with rtorrent's XML-RPC interface. The port-forward.conf script assumes this script is executable and available in /usr/bin or in a PATH location supported by upstart. |

## <span style="background-color:yellow; ">postprocess</span>

This script pre-processes compressed archives and copies the media to a shared file system or for hand off to other multimedia management applications.

Typically used for mega-packs that often include multiple unrelated media files that sometimes have strangely nested and multi-part compressed archives.

Allows the specification of untrusted files. These files are meant to be evaluated in a protected environment. When extracting files from an archive these files are encrypted and password protected.

Allow a json service to be specified that returns the amount of available disk space to store media files: used when shared CIFS volumes report incorrect file system usage data.

Finally, globbing is used to specify a group of media storage folders so that files can be copied to volumes with the most amount of free space.
