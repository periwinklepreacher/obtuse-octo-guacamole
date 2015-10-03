#!/usr/bin/python2

'''
Created on Aug 19, 2015

@author: periwinklepreacher

 program name: rtrpc

  description: Python module for interacting with rtorrent's XML-RPC interface.

     examples: import rtrpc
      
               proxy = SCGIServerProxy( 'scgi://localhost:5000' )
               downloads = proxy.d.multicall(
                 'main', 'd.get_hash=', 'd.get_name=', 'd.get_state=',
                 'd.get_size_bytes=', 'd.get_priority=', 'd.get_creation_date=' )
               print( downloads )

               proxy = SCGIServerProxy( 'scgi://localhost:5000' )
               print( proxy.system.listMethods() )
               print proxy.get_port_open( )
               print proxy.get_port_random( )
               print proxy.get_port_range( )

               proxy = SCGIServerProxy( 'scgi://localhost:5000' )
               multicall = proxy.system.multicall( [
                   { 'methodName': 'get_port_open', 'params': [ ] },
                   { 'methodName': 'get_port_random', 'params': [ ] },
                   { 'methodName': 'get_port_range', 'params': [ ] }
               ] )
               print( multicall ) 

         env : rtorrent 0.9.2, libtorrent-0.13.2, xmlrpc-c 1.39.5, GCC 4.8.2
               Python 2.7.6, /usr/lib/python2.7/xmlrpc

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
    
    This file is based on:
        rtorrent_xmlrpc (c) 2011 by Roger Que
        
    Portions based on Python's xmlrpclib:
        Copyright (c) 1999-2002 by Secret Labs AB
        Copyright (c) 1999-2002 by Fredrik Lundh
'''

from collections import OrderedDict
import errno
import re
import socket
import urllib
import xmlrpclib
import argparse

class SCGITransport( xmlrpclib.Transport ):
    def __repr__( self ):
        return ( '<SCGIServerProxy for %s%s>' % ( self.__host, self.__handler ) )
     
    __str__ = __repr__
     
    def connect( self, host, handler ):
        if host:
            host, port = urllib.splitport( host )
            addrinfo = socket.getaddrinfo( host, port, socket.AF_INET, socket.SOCK_STREAM )
            sd = socket.socket( *addrinfo[0][:3] )
            sd.setblocking( True )
            sd.connect( addrinfo[0][4] )
        else:
            sd = socket.socket( socket.AF_UNIX, socket.SOCK_STREAM )
            sd.setblocking( True )
            sd.connect( handler )
        return sd

    def readall( self, fd ):
        parts = [ ]
        while True:
            chunk = fd.read( fd._CHUNK_SIZE if hasattr(fd,"_CHUNK_SIZE") else 8192 )
            if not chunk: break
            parts.append( chunk )
        return u''.join( parts )
    
    def single_request( self, host, handler, request, verbose = 0 ):
        # Add SCGI headers to the request.
        content_length = str( len( request ) )
        params =  OrderedDict( [ ('CONTENT_LENGTH',content_length), ('SCGI','1') ] )
        header = '\x00'.join( '%s\x00%s' % i for i in params.items( ) ) + '\x00'
        header = '%d:%s' % ( len( header ), header )
        send_payload = ( '%s,%s' % ( header, request ) ).encode( )
        sd = None
        try:
            sd = self.connect( host, handler )
            sd.sendall( send_payload, socket.MSG_WAITALL )
            self.verbose = verbose
            return self.parse_response( sd.makefile( ) )
        finally:
            if sd: sd.close( )

    def parse_response( self, response ):
        recv_payload = self.readall( response )
        if not len( recv_payload ):
            raise OSError( errno.EPIPE, "Server closed the connection without responding." )
        # Remove SCGI headers from the response. Header looks something like
        # str: Status: 200 OK\nContent-Type: text/xml\nContent-Length: 49495\n\n
        # <?xml version="1.0" encoding="UTF-8"?> ...
        splits = re.split( r'\n\s*?\n', recv_payload, maxsplit = 1 )  # @UnusedVariable
        header, body = splits if len( splits ) == 2 else ( recv_payload, u'' )  # @UnusedVariable
        if self.verbose: print( 'body:', repr( body ) )
        p, u = self.getparser( )
        p.feed( body )
        p.close( )
        return u.close( )
 
class SCGIServerProxy( xmlrpclib.ServerProxy ):
    def __init__( self, uri, transport=None, encoding=None, verbose=False,
                  allow_none=False, use_datetime=False ):
        protocol, uri = urllib.splittype( uri )
        if protocol not in ( 'scgi' ):
            raise IOError( 'Unsupported XML-RPC protocol' )
        self.__host, self.__handler = urllib.splithost( uri )
        if not self.__handler:
            self.__handler = '/'
        if transport is None:
            transport = SCGITransport( use_datetime = use_datetime )
        self.__transport = transport
         
        self.__encoding = encoding
        self.__verbose = verbose
        self.__allow_none = allow_none
  
    def __close( self ):
        self.__transport.close( )
     
    def __request( self, methodname, params ):
        # call a method on the remote server
        request = xmlrpclib.dumps( params, methodname,
                                   encoding = self.__encoding,
                                   allow_none = self.__allow_none )
        response = self.__transport.request( self.__host, self.__handler,
                                             request, verbose=self.__verbose )
        if len( response ) == 1:
            response = response[0]
        return response
     
    def __getattr__( self, name ):
        # magic method dispatcher
        return xmlrpclib._Method( self.__request, name )
 
    # note: to call a remote object with an non-standard name, use
    # result getattr(server, "strange-python-name")(args)
 
    def __call__( self, attr ):
        """A workaround to get special attributes on the ServerProxy
           without interfering with the magic __getattr__
        """
        if attr == "close":
            return self.__close
        elif attr == "transport":
            return self.__transport
        raise AttributeError( "Attribute %r not found" % ( attr, ) )

def dump_long( self, value, write ):
    if int( value ) > 2**31-1:
        write( "<value><i8>" )
        write( str( int( value ) ) )
        write( "</i8></value>\n" )
    else:
        write( "<value><i4>" )
        write( str( int( value ) ) )
        write( "</i4></value>\n" )

xmlrpclib.Marshaller.dispatch[int] = dump_long

if __name__ == "__main__":
    parser = argparse.ArgumentParser( )
    parser.add_argument( '-H', '--host', default="scgi://localhost:5000" )
    group = parser.add_mutually_exclusive_group( )
    group.add_argument( '-g', '--get' )
    group.add_argument( '-s', '--set', nargs=2 )
    args = parser.parse_args( )

    proxy = SCGIServerProxy( args.host )
    if args.get:
        multicall = proxy.system.multicall( [
            { 'methodName': args.get, 'params': [ ] }
        ] )
        reply = multicall[0]
        print( reply[0] if isinstance( reply, list ) and len( reply ) == 1 else reply )
    elif args.set:
        multicall = proxy.system.multicall( [
            { 'methodName': args.set[0], 'params': [ args.set[1] ] }
        ] )
