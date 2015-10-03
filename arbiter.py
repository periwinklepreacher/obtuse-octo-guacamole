#!/usr/bin/python2

''' 
Created on September 28, 2015

@author: periwinklepreacher

program name: arbiter
 description: A script for controlling uTorrent download rate depending on
              state of SABnzbd.
              
              If SABnzbd is 'Downloading' then uTorrent schedule is enabled,
              and disabled otherwise. User must manually configure bandwidth
              sensitive time periods to "seed only" in the uTorrent schedule.
              
              This works better than setting max_dl_rate because a low
              download rate also limits the upload rate.
              
              This script should be run as a cron job (every 5 to 15 mins
              should be fine). Output is captured in a rotated log file.

Example usage - Run arbiter every 5 minutes:

crontab -e
*/5 * * * * /root/scripts/arbiter --shost sabhost --sport 8100 --apikey 8a7c6a876c87a6cb786acb87abc876ba8cb \
                                  --uhost uthost --uport 8200 --uname utuser --upasswd utpassword >/dev/null 2>&1

Tested using SABnzbd 0.7.20, uTorrent 2.2.1 and python 2.7.10.

Based in part on code written by ftao / py-utorrent authored Nov 21, 2014
https://github.com/ftao/py-utorrent.git

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

import argparse
import cookielib
import json
import logging  # @UnusedImport
import logging.handlers
import os
import re
import sys
import tempfile
import urllib
import urllib2
import urlparse


class CommandLine( argparse.Namespace ):
    def __init__( self ):
        program_name, program_ext = os.path.splitext( os.path.basename( sys.argv[0] ) )  # @UnusedVariable

        log_format = logging.Formatter( '%(asctime)s %(levelname)-8s %(message)s', '%b-%d %H:%M:%S' )
        log_level = { 'all' : logging.NOTSET + 1, 'debug' : logging.DEBUG, 'info' : logging.INFO, 'warning' : logging.WARNING,
                      'error' : logging.ERROR, 'critical' : logging.CRITICAL }
        log_folder = os.path.join( os.sep, 'var', 'log' ) if sys.platform.lower().startswith( 'linux' ) else tempfile.gettempdir( )
        log_default = os.path.join( log_folder, '{}.log'.format( program_name ) )

        parser = argparse.ArgumentParser( )
        parser.add_argument( '--shost', dest = 'shost', required = True, help = "IP or name of SABnzbd host." )
        parser.add_argument( '--sport', dest = 'sport', required = True, help = "SABnzbd API port." )
        parser.add_argument( '--apikey', dest = 'apikey', required = True, help = "This key gives 3rd party programs full access to SABnzbd API." )
        parser.add_argument( '--uhost', dest = 'uhost', required = True, help = "IP or name of uTorrent host." )
        parser.add_argument( '--uport', dest = 'uport', required = True, help = "uTorrent WebUI port." )
        parser.add_argument( '--uname', dest = 'uname', required = True, help = "uTorrent WebUI user name." )
        parser.add_argument( '--upasswd', dest = 'upasswd', required = True, help = "uTorrent WebUI password." )
        parser.add_argument( '--level', dest = 'level', choices = log_level.keys(), required = False, default = 'warning', help = "Console messages are filtered by this severity." )
        parser.add_argument( '--logfile', dest = 'logfile', required = False, default = log_default, help = "Name of the log file. The log file is not filtered by the level setting." )

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
            ''' IMPORTANT: SABnzbd API key and uTorrent passwords are logged so only allow root user to view the
                           log contents.
            '''
            os.umask( 0o077 )
            log_to_file = logging.handlers.RotatingFileHandler( self.logfile, maxBytes=262144, backupCount=4 )
            log_to_file.setFormatter( log_format )
            log_to_file.setLevel( logging.DEBUG )
            log.addHandler( log_to_file )
            
        if self.level:
            log_to_console.setLevel( log_level[ self.level ] )
            
        log.info( ' '.join( sys.argv ) )

class UTorrent( object ):
    def __init__( self, base_url, username, password ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.opener = self._make_opener( 'uTorrent', base_url, username, password )
        self.token = self._get_token( )

    def _make_opener( self, realm, base_url, username, password ):
        '''uTorrent API need HTTP Basic Auth and cookie support for token verify.'''
        auth_handler = urllib2.HTTPBasicAuthHandler( )
        auth_handler.add_password( realm=realm,
                                   uri=base_url,
                                   user=username,
                                   passwd=password)
        opener = urllib2.build_opener( auth_handler )
        urllib2.install_opener( opener )
        cookie_jar = cookielib.CookieJar( )
        cookie_handler = urllib2.HTTPCookieProcessor( cookie_jar )
        handlers = [ auth_handler, cookie_handler ]
        opener = urllib2.build_opener( *handlers )
        return opener
    
    def _get_token(self):
        url = urlparse.urljoin( self.base_url, 'token.html' )
        response = self.opener.open( url )
        token_re = "<div id='token' style='display:none;'>([^<>]+)</div>"
        match = re.search( token_re, response.read( ) )
        return match.group( 1 )
    
    def _action( self, params, body=None, content_type=None ):
        #about token, see https://github.com/bittorrent/webui/wiki/TokenSystem
        url = self.base_url + '?token=' + self.token + '&' + urllib.urlencode( params )
        logging.debug( url )
        request = urllib2.Request( url )
        if body:
            request.add_data( body )
            request.add_header( 'Content-length', len( body ) )
        if content_type:
            request.add_header( 'Content-type', content_type )
        try:
            response = self.opener.open( request )
            return response.code, json.loads( response.read( ) )
        except urllib2.HTTPError, e:  # @UnusedVariable
            raise 

# Previous implementation of this script set max_dl_rate to a low value when SABnzbd was downloading and then
# back to unlimited when SABnzbd was IDLE. This has the unintended side-effect of also lowering the upload rate
# when seeding because of internal uTorrent bandwidth management algorithms.
#  
#     @property
#     def max_dl_rate( self ):
#         json_response = self._action( { 'action' : 'getsettings' } )
#         logging.debug( json_response )
#         element = next( setting for setting in json_response[1]['settings'] if setting[0] == 'max_dl_rate' )
#         return element[2]
# 
#     @max_dl_rate.setter
#     def max_dl_rate( self, v ):
#         json_response = self._action( { 'action' : 'setsetting', 's' : 'max_dl_rate', 'v' : v } )
#         logging.debug( json_response )
#         if json_response is None or len( json_response ) < 1 or json_response[0] is not 200:
#             raise AssertionError( 'Unable to set max_dl_rate to {}. Server response is {}.'.format( v, json_response ) )
    
    @property
    def sched_enable( self ):
        json_response = self._action( { 'action' : 'getsettings' } )
        logging.debug( json_response )
        element = next( setting for setting in json_response[1]['settings'] if setting[0] == 'sched_enable' )
        return '1' if element[2] == 'true' else '0' 
        
    @sched_enable.setter
    def sched_enable( self, v ):
        json_response = self._action( { 'action' : 'setsetting', 's' : 'sched_enable', 'v' : v } )
        logging.debug( json_response )
        if json_response is None or len( json_response ) < 1 or json_response[0] is not 200:
            raise AssertionError( 'Unable to set sched_enable to {}. Server response is {}.'.format( v, json_response ) )

args = CommandLine( )

sabnzbd_url = ''.join( [ 'http://', args.shost, ':', args.sport, '/sabnzbd/api?', 'apikey=', args.apikey, '&mode=qstatus&output=json' ] )
sabnzbd_response = urllib.urlopen( sabnzbd_url )
sabnzbd_json = json.load( sabnzbd_response )
logging.debug( sabnzbd_json )

sched_enable = '0' if sabnzbd_json['state'] == 'IDLE' else '1'

utorrent_url = ''.join( [ 'http://', args.uhost, ':', args.uport, '/gui/' ] )
utorrent = UTorrent( utorrent_url, args.uname, args.upasswd )
utorrent.sched_enable = sched_enable
logging.info( 'SABnzbd is {} uTorrent sched_enable set to {}'.format( sabnzbd_json['state'], sched_enable ) )
