# obtuse-octo-guacamole
A set of scripts for managing multi-media programs.

<b>arbiter</b>     : A python 2 script for setting uTorrent download rate depending on state of SABnzbd.

<b>postprocess</b> : A python 2 script for moving files from uTorrent download directory to storage folder
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
