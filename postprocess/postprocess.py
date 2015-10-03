#!/usr/bin/python2

''' 
Created on September 6, 2015

@author: periwinklepreacher

program name: postprocess
 description: This script pre-processes compressed archives and copies the media
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
              
       usage: uTorrent > Preferences > Advanced > Run Program > Run this program when a torrent finishes:
             "C:\Python27\python.exe" "C:\Program Files\PostProcess\postprocess.py" \
                 -f "%F" -d "%D" -t "%N" -s "%S" -l "%L" -m "%M" -i "%I"

Tested using SABnzbd 0.7.20, uTorrent 2.2.1, python 2.7.10, Windows XP 2002 SP3

Copyright (C) 2015  periwinklepreacher.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from ConfigParser import SafeConfigParser
import argparse
import glob
import itertools
import logging
import os.path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib, json


try:
    from ctypes import c_ulong, byref, windll # @UnusedImport
except ImportError:
    from os import statvfs                    # @UnusedImport


class CommandLine( argparse.Namespace ):
    def __init__( self ):
        program_name, program_ext = os.path.splitext( os.path.basename( sys.argv[0] ) )  # @UnusedVariable
        program_path = os.path.dirname( sys.argv[0] )

        log_format = logging.Formatter( '%(asctime)s %(levelname)-8s %(message)s', '%b-%d %H:%M:%S' )
        log_level = { 'all' : logging.NOTSET + 1, 'debug' : logging.DEBUG, 'info' : logging.INFO,
                      'warning' : logging.WARNING, 'error' : logging.ERROR, 'critical' : logging.CRITICAL }
        log_folder = os.path.join( os.sep, 'var', 'log' ) if sys.platform.lower().startswith( 'linux' ) else tempfile.gettempdir( )
        log_default = os.path.join( log_folder, '{}.log'.format( program_name ) )
        config_default = os.path.join( program_path, program_name + '.ini' )

        parser = argparse.ArgumentParser( )
        parser.add_argument( '-c', "--config", required = False, default = config_default, help = "INI configuration file." )
        parser.add_argument( '-f', "--file", required = True, help = "Name of downloaded file (for single file torrents)." )
        parser.add_argument( '-d', "--directory", required = True, help = "Directory where files have been downloaded." )
        parser.add_argument( '-t', "--title", required = False, default = "", help = "Title of torrent." )
        parser.add_argument( '-s', "--state", required = False, default = "", help = "State of torrent." )
        parser.add_argument( '-l', "--label", required = False, default = "", help = "Torrent label." )
        parser.add_argument( '-m', "--message", required = False, default = "", help = "Status message string." )
        parser.add_argument( '-i', "--infohash", required = False, default = "", help = "Hex encoded infohash." )
        parser.add_argument( '--level', dest = 'level', choices = log_level.keys(), required = False, default = 'warning', help = "Console messages are filtered by this severity." )
        parser.add_argument( '--logfile', dest = 'logfile', required = False, default = log_default, help = "Name of the log file. The log file is not filtered by the level setting." )
        parser.add_argument( '--pretend', dest = 'pretend', required = False, default = False, action = 'store_true', help = "Don't actually transfer the file to the storage server." )

        log = logging.getLogger( )
        log.setLevel( log_level[ 'all' ] )
        log_to_console = logging.StreamHandler( )
        log_to_console.setFormatter( log_format )
        log_to_console.setLevel( logging.ERROR )
        log.addHandler( log_to_console )

        try:
            parser.parse_args( namespace = self )
        except:
            log.critical( ' '.join( sys.argv ) )    
            exit( -1 )

        if self.logfile:
            os.umask( 0o077 )
            log_to_file = logging.FileHandler( self.logfile )
            log_to_file.setFormatter( log_format )
            log_to_file.setLevel( logging.DEBUG )
            log.addHandler( log_to_file )
            
        if self.level:
            log_to_console.setLevel( log_level[ self.level ] )
            
        log.info( ' '.join( sys.argv ) )


class Configuration:
    ''' Load configuration settings from a file.
    '''
    def __init__( self ):
        self.args = CommandLine( )
        self.ini = SafeConfigParser( )
        self.ini.read( self.args.config )
        
        self.archive_extensions = self.as_array( "ArchiveExtensions" )
        self.media_extensions = self.as_array( "MediaExtensions" )
        self.meta_extensions = self.as_array( "MetaExtensions" )
        self.subtitle_extensions = self.as_array( "SubtitleExtensions" )
        self.ignore_words= self.as_array( "IgnoreWords" )
    
        self.zip_program = self.get_property( "ArchiveProgram" )
        self.media_sandbox = self.as_array( "MediaSandbox" )
        self.sandbox_password = self.get_property( "SandboxPassword" )

        self.stacked_flag = self.as_boolean( "FlattenStacked" )
        self.re_stacked = self.get_property( "StackedRegex" )
        
        self.parent_flag = self.as_boolean( "MakeParent" )
        self.re_parent = self.get_property( "ParentRegex" )
        
        self.subtitle_flag = self.as_boolean( "IncludeSubtitles" )
        self.meta_flag = self.as_boolean( "IncludeMeta" )
        self.flatten_flag = self.as_boolean( "FlattenFolders" )

        self.storage_service = self.get_property( "StorageService" )
        self.storage_map = None
        if self.storage_service:
            map_property = self.get_property( "StorageMap", '' )
            map_tuple = map_property.split( ' ' )
            if len( map_tuple ) is not 2:
                raise ValueError( 'Bad format for {}. Expecting <remote path> <local path>.'.format( map_property ) )
            self.storage_map = map_tuple[0], map_tuple[1]

        storage = self.get_property( "Storage",  default = os.path.expanduser( '~\\Documents' ) )
        path_list = filter( lambda f: os.path.isdir( f ), glob.glob( storage ) )
        space_list = map( lambda p: Storage.GetFreeSpace( self.storage_service, self.storage_map, p ), path_list )
        largest = max( space_list )
        index = space_list.index( largest )
        self.storage_folder = path_list[index]
        
    def get_property( self, name, default = None ):
        value = self._get_property( name, default )
        logging.debug( "get_property( {}, '{}' ) = {}".format( name, default, value ) )
        return value
    
    def _get_property( self, name, default = None ):
        if self.ini.has_section( self.args.label ) and self.ini.has_option( self.args.label, name ):
            return self.ini.get( self.args.label, name )
        elif self.ini.has_section( 'Default' ) and self.ini.has_option( 'Default', name ):
            return self.ini.get( 'Default', name )
        else:
            return default
    
    def as_array( self, name ):
        value = self.get_property( name )
        return [ v.lower( ).strip( ) for v in value.split( ',' ) ] if value else None

    def as_boolean( self, name ):
        value = self.get_property( name )
        return value in [ "Yes", "yes", "True", "true", "Y", "y", "T", "t", "1" ] 
        

class Storage:
    ''' StorageObject queries file system free space locally or remotely from an external file server. CIFS shares
        may provide unreliable free space data so a direct request to the file server using a JSON query can be used
        instead.
        
        An example StorageService configuration is defined like this:
            [Movies]
            Storage = \\FileServer\MOVIES??
            StorageService = http://FileServer/disks.json.php
            StorageMap = /share/MOVIES \\FileServer\MOVIES
        
        A simple http GET is sent to the storage server to fetch JSON data at the StorageService URL. An example JSON
        response captured from a "mount" system call is as follows (abbreviated to reduce display width):
        [
            ...
            { "size" : 19236, "used" : 16460, "available" : 79576, "mount" : "/share/MOVIES01" }
            { "size" : 45336, "used" : 36460, "available" : 11876, "mount" : "/share/MOVIES02" }
            { "size" : 96268, "used" : 95900, "available" : 57368, "mount" : "/share/TV" }
            ...
        ]
        
        Instances of storage object are populated with whatever fields are returned in the JSON dictionary. The "mount"
        field is mapped to a local UNC, and "available" is used to pick the shared folder with the most free space. Any
        other fields in the json response are used to populate the storage object but are not used.
        
        Example Storage object:
        {
            self.size =  19236
            self.used = 16460
            self.available = 79576
            self.mount = "/share/MOVIES01"
            self.unc = "\\FileServer\MOVIES01"
        }
    '''
    _storage_list = None

    @staticmethod
    def GetFreeDiskSpaceEx( folder ):
        ''' GetDiskFreeSpaceEx() has two names (as do most windows functions that use strings), the Ansi version and the
            Unicode version, and you need to use the real name for the function you wish to use.
        '''
        if sys.platform.lower().startswith( 'win' ):
            freeBytesAvailable = c_ulong()
            totalNumberOfBytes = c_ulong()
            totalNumberOfFreeBytes = c_ulong()
            return_code = windll.kernel32.GetDiskFreeSpaceExA(  # @UndefinedVariable
                folder,
                byref( freeBytesAvailable ),
                byref( totalNumberOfBytes ),
                byref( totalNumberOfFreeBytes ) )
            return totalNumberOfFreeBytes.value if return_code else None

        elif sys.platform.lower().startswith( 'linux' ):
            stinfo = statvfs( folder )
            return stinfo.f_bsize * stinfo.f_bavail

    @staticmethod
    def Initialize( url, storage_map ):
        ''' Get the storage objects from the remote server.
        '''
        if not Storage._storage_list:
            response = urllib.urlopen( url )
            json_data = json.load( response )
            storage_list = map( lambda jd: Storage( jd, storage_map ), json_data )
            storage_list = sorted( storage_list, cmp = lambda soa, sob: len( sob.mount ) - len( soa.mount ) )
            Storage._storage_list = storage_list
        return Storage._storage_list

    @staticmethod
    def GetFreeStorageSpace( storage_service, storage_map, path ):
        ''' Return the free space available for the given path from the remote storage server. Relies on the remote
            server having an HTTP end-point defined that responds to the StorageService URL. Also must have a mapping
            property defined that allows remote server mount points to be translated into UNC paths.
        '''
        storage_list = Storage.Initialize( storage_service, storage_map )
        storage_object = next( so for so in storage_list if path.startswith( so.unc ) )
        return storage_object.available

    @staticmethod
    def GetFreeSpace( storage_service, storage_map, path ):
        try:
            return Storage.GetFreeDiskSpaceEx( path ) if not storage_service else \
                   Storage.GetFreeStorageSpace( storage_service, storage_map, path )
        except:
            logging.error( "Unable to fetch storage metadata from {}. Skipping.".format( storage_service ) )

    def __init__( self, json_data, storage_map ):
        ''' Update the storage object with properties from the JSON dictionary. Add a UNC property by mapping the
            supplied mount property into a local UNC reference property.
        '''
        self.__dict__.update( json_data )
        self.unc = self.mount.replace( storage_map[0], storage_map[1] )


class Context:
    ''' Object with attributes corresponding to group names matched when parsing output from command-line program.
    '''
    def __init__( self, name = "context" ):
        self.name = name
    
    def getNumber( self, attribute, default = '0' ):
        return int( getattr( self, attribute, default ) )

    def search( self, pattern, string = None ):
        string = self.name if string is None else string  
        match = re.search( pattern, string.decode( 'UTF-8' ), re.IGNORECASE )
        if not match: return
        for groupname in match.groupdict( ):
            setattr( self, groupname, match.group( groupname ) )


def commandline( cmd, pattern_list = [ ] ):
    ''' Execute cmd then pass output through regex. Named regex match groups are added to the context object as
        attributes.
    '''
    context = Context( name = cmd[0] )
    p = subprocess.Popen( cmd, shell = False, stdout = subprocess.PIPE, stderr = subprocess.STDOUT )
    for line in p.stdout.readlines( ):
        for pattern in pattern_list:
            context.search( pattern, line )
    context.return_code = p.wait( )
    return context

def listdir( path ):
    ''' Same as os.listdir but returns full path names. 
    '''
    return map( lambda f: os.path.join( path, f ), os.listdir( path ) )

def extension_in_list( fullname, ext_list ):
    ''' True if filename extension is in the supplied list of extensions.
    '''
    name, ext = os.path.splitext( fullname.lower( ) )  # @UnusedVariable
    return ext in ext_list

def ignored( fullname ):
    ''' True if the filename contains an ignored sub-string. 
    '''
    return any( word in os.path.basename( fullname.lower( ) ) for word in config.ignore_words )

def ignore_filter( fullname ):
    ''' True if path is a regular file and does not contain an ignored sub-string.
    '''
    return os.path.isfile( fullname ) and not ignored( fullname )

def media_filter( fullname ):
    ''' True if media file has a media extension, or if wild-card '*' is specified; then will include any extension not
        already defined as meta, subtitle, or archive.
    '''
    return extension_in_list( fullname, config.media_extensions ) if config.media_extensions != ['*'] else \
           not extension_in_list( fullname, itertools.chain( config.meta_extensions, \
                                                             config.subtitle_extensions, \
                                                             config.archive_extensions ) )

def meta_filter( fullname ):
    ''' True if full-name has a meta-file extension.  
    '''
    return extension_in_list( fullname, config.meta_extensions ) 

def subtitle_filter( fullname ):
    ''' '' True if full-name has a subtitle extension.
    '''
    return extension_in_list( fullname, config.subtitle_extensions )

def archive_filter( fullname ):
    ''' True if full-name has an archive extension and passes archive integrity check. The integrity check has the
        added benefit of filtering out subordinate archive files in a multi-part fileset. 
    '''
    return extension_in_list( fullname, config.archive_extensions ) and archive_test( fullname )

def fileset_filter( archive, fullname ):
    ''' True is full-name is part of archive fileset (assume context has already been verified to have more than one
        volume).
    '''
    # TODO: Potential bug. Will filter archive files outside the set if they happen to be multi-part
    # archive files with the same file extension and in the same directory.
    archive_basename, archive_ext = os.path.splitext( os.path.basename( archive ) )
    basename, ext = os.path.splitext( os.path.basename( fullname ) )
    return ( archive == fullname ) or \
           ( archive_basename == basename and ext[-1:].isdigit( ) ) or \
           ( archive_ext == ext and basename[-1:].isdigit( ) )

def archive_context( archive ):
    ''' Return a context object that evaluates the archive list output. Returns:
            volumes: number of archive files in the fileset.
            sandbox: name of files to sandbox instead of extracting as a regular file.
        return_code: 0 indicates success.
    '''
    return commandline( [ config.zip_program, 'l', '-bd', '-y',  archive ],
                        [ 'Volumes = (?P<volumes>\d+)', '(?P<sandbox>keygen.exe)' ] )

def archive_test( filename ):
    context = commandline( [ config.zip_program, 't', '-bd', '-y', filename ] )
    return context.return_code == 0

def archive_fileset_filter( context, file_list, archive ):
    ''' Filter archive fileset from file_list.
    '''
    return filter( lambda f: not fileset_filter( archive, f ), file_list ) if context.getNumber( 'volumes' ) > 1 else \
           filter( lambda f: not f == archive, file_list ) 

def extract_archive( context, workspace, archive ):
    ''' Extract files from archive into workspace. Sandboxed files are put into a password protected self-extracting
        archive.  
    '''
    cmd =  [ config.zip_program, 'x', '-bd', '-y' ]
    if hasattr( context, 'sandbox' ):
        extract_and_sandbox( workspace, archive, context.sandbox )
        cmd.append( '-x!{}'.format( context.sandbox ) )
    cmd.append( '-o{}'.format( workspace ) )
    cmd.append( archive )
    context = commandline( cmd )
    if context.return_code:
        raise AssertionError( 'Error extracting files', workspace, archive )

def extract_and_sandbox( workspace, archive, filename ):
    ''' Extract file into a password protected self-extracting archive. The uncompressed file is never exposed to the
        operating system (where a virus scanner may decide to quarantine the file). The file can later be uncompressed
        and evaluated using a sandbox environment built for the task.
    '''
    path, ext = os.path.splitext( filename )
    sandbox = os.path.join( workspace, '.7z'.join( [ path, ext ] ) )
    include = '-i!{}'.format( filename )
    inputname = '-si{}'.format( filename )
    password = '-p{}'.format( config.sandbox_password )
    xtract = subprocess.Popen( [ config.zip_program, 'x', '-bd', '-y', include, '-so', archive ],
                               stdout = subprocess.PIPE, shell = False )
    encode = subprocess.Popen( [ config.zip_program, 'a', '-bd', '-y', inputname, '-sfx7z.sfx', password, sandbox ],
                               stdin = xtract.stdout, stdout = subprocess.PIPE, shell = False )
    encode.communicate( )
    if encode.returncode:
        raise AssertionError( 'Error extracting file', filename )        
    return archive

def get_stack( basename ):
    ''' Return any stack attributes from the filename as a list of tuples [ ( matched string, tag, sequence ), ... ] 
    '''
    if not config.stacked_flag:
        return None
    match_list = re.findall( config.re_stacked, basename, re.IGNORECASE )
    if not match_list:
        return None
    return filter( lambda m: m[0], match_list )

def set_stack( basename, stack ):
    ''' Append stack attributes in basename if not already present. Stack attributes are extracted from the parent
        directory name such as CD1, or Part 1, etc when analyzing the parent folder name. The stack attributes
        are inserted into the contained file names if the parent folder is flattened in preparation for copying the
        media to storage.
    '''
    if not stack:
        return basename
    new_stack = filter( ( lambda s: s[1] != t[1] or s[2] != t[2] for t in get_stack( basename ) ), stack )
    stack_string = '.'.join( map( lambda s: '-{}{}'.format( s[1], s[2] ), new_stack ) )
    name, ext = os.path.splitext( basename )
    return ''.join( [ name, '.', stack_string, ext ] )

def handle_storage( storage, source ):
    ''' There are endless ways of encoding sequence numbers into media files, directories, archive file names, and
        combinations thereof. This function handles the case where a directory name has the stack identifier and
        sequence number (e.g., CD1, or Part 1, etc) but we want to flatten these directories from the output hierarchy.
    '''
    basename = os.path.basename( source )
    stack = get_stack( basename )
    if stack:
        handle_folder( storage, source, stack )
    else:
        workspace = os.path.join( storage, basename )
        handle_folder( workspace, source )

def handle_folder( storage, source, stack = None ):
    if not os.path.exists( source ):
        logging.warn( "Directory {0} does not exist. Skipping.".format( source ) )
        return
    file_list = filter( ignore_filter, listdir( source ) )

    archive_list = filter( archive_filter, file_list )
    if len( archive_list ) > 0:
        ''' TODO: Should probably name the temporary directory using the archive name. May be useful when re-naming
                  media using the name of the containing folder. Currently no re-naming is done as that feature is
                  typically handled by a media manager which is better suited to the task.
        '''
        workspace =  tempfile.mkdtemp( )
        for archive in archive_list:
            context = archive_context( archive )
            extract_archive( context, workspace, archive )
            file_list = archive_fileset_filter( context, file_list, archive )
        handle_folder( storage, workspace, stack )
        shutil.rmtree( workspace )

    for media in file_list:
        handle_media( storage, os.path.join( source, media ), stack )

    if config.subtitle_flag:
        for subtitle in filter( subtitle_filter, file_list ):
            handle_media( storage, os.path.join( source, subtitle ), stack )
        
    if config.meta_flag:
        for meta in filter( meta_filter, file_list ):
            handle_media( storage, os.path.join( source, meta ), stack )

    for folder in filter( os.path.isdir, listdir( source ) ):
        handle_storage( storage, os.path.join( source, folder ) )

def handle_media( storage_folder, source_fullname, stack = None ):
    ''' By default the storage will follow the same directory hierarchy as the source and will preserve source file
        names. The default can be changed using the configuration file.
            FlattenFolders : Strip away the source folder hierarchy and copy the source files directly into the storage
                             folder.
                KeepParent : Modify FlattenFolders to keep only the folder containing the media and collapse any others.
    '''
    storage_filename = set_stack( os.path.basename( source_fullname ), stack )
    storage_fullname = os.path.join( storage_folder, storage_filename )
    if config.flatten_flag:
        storage_fullname = os.path.join( config.storage_folder, storage_filename )

    logging.info( "Copy {} to {}".format( source_fullname, storage_fullname ) )
    if not os.path.exists( os.path.dirname( storage_fullname ) ) and not config.args.pretend:
        os.makedirs( os.path.dirname( storage_fullname ), 777 )
    if not os.path.exists( storage_fullname ) and not config.args.pretend:
        shutil.copy2( source_fullname, storage_fullname )

def make_parent( storage, filename ):
    ''' Some downloads are just a single bare media file. This function uses the media filename to formulate a parent
        folder name. The default algorithm looks for a prefix followed by a date then a postfix. The parent folder is
        given the name with the following format <prefix>.[<year>] 
    '''
    if not config.parent_flag:
        return storage
    match = re.match( config.re_parent, filename, re.IGNORECASE )
    if not match:
        return storage
    folder_name = '{}.[{}]'.format( match.group( 'folder'), match.group( 'year' ) )
    return os.path.join( storage, folder_name )

config = Configuration( )
if config.args.file:
    handle_media( make_parent( config.storage_folder, config.args.file ),
                  os.path.join( config.args.directory, config.args.file ) )
else:
    handle_storage( config.storage_folder, config.args.directory )
