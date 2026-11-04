"""Bounded, explicit LAN discovery. Replies are hints, never trusted identities."""
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import socket
import ssl
import time

from .transport import Endpoint, ConnectError

MAGIC=b'COUCHSIDE_DISCOVER?'


@dataclass(frozen=True)
class Box:
    name: str
    endpoint: Endpoint
    version: str


def parse_reply(data, peer):
    if len(data)>8192:raise ConnectError('Discovery reply too large.')
    try:
        value=json.loads(data)
        if not isinstance(value,dict) or value.get('couchside') is not True:raise ValueError()
        # Use the actual responding address, never an advertised URL/IP that
        # could redirect a scan into an unrelated service.
        ipaddress.IPv4Address(peer)
        name=value.get('name')
        if not isinstance(name,str) or not 1<=len(name)<=80 or any(ord(c)<32 for c in name):raise ValueError()
        version=value.get('version','')
        if not isinstance(version,str) or len(version)>80:raise ValueError()
        endpoint=Endpoint(peer,value['tls_port'],value['tls_fp'])
        return Box(name,endpoint,version)
    except Exception:
        raise ConnectError('Invalid or non-TLS discovery reply.') from None


def scan(seconds=3, port=8787, targets=None):
    # No subnet sweep, mDNS dependency, credentials, configuration writes or
    # firewall change. Broadcast may not cross VLAN/VPN; manual entry remains.
    destinations=targets or ['255.255.255.255']
    found={}
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp:
        udp.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        udp.bind(('',0));udp.settimeout(.15)
        def probe():
            sent=False
            for target in destinations:
                try:udp.sendto(MAGIC,(target,port));sent=True
                except OSError:continue
            if not sent:
                raise ConnectError('Local network scan was blocked. Allow local network access for Computer Connect, or enter the PC address.')
        probe()
        retry=time.monotonic()+.5
        deadline=time.monotonic()+min(5,max(.1,seconds));packets=0
        while time.monotonic()<deadline and packets<256 and len(found)<32:
            if time.monotonic()>=retry:
                probe();retry=time.monotonic()+.5
            try:data,addr=udp.recvfrom(8193)
            except socket.timeout:continue
            packets+=1
            try:box=parse_reply(data,addr[0])
            except ConnectError:continue
            found.setdefault((box.endpoint.host,box.endpoint.port),box)
    return sorted(found.values(),key=lambda box:(box.name.casefold(),box.endpoint.host))


def inspect(host,port):
    # Validate address/port without a credential or trust decision. Discovery
    # isn't authentication: UI must compare the PC's identity before PIN finish.
    endpoint=Endpoint(host,port,'0'*64)
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    try:
        with socket.create_connection((endpoint.host,endpoint.port),8) as raw:
            with ctx.wrap_socket(raw,server_hostname=endpoint.host) as tls:
                return Endpoint(endpoint.host,endpoint.port,hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest())
    except Exception:
        raise ConnectError('Cannot find the encrypted agent at this address and port.') from None


def identity_code(fingerprint):
    return ' '.join(fingerprint[:32].upper()[i:i+4] for i in range(0,32,4))
