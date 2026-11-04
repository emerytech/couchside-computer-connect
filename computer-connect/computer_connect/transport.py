"""Pinned TLS is established before any PIN, bearer token or WS upgrade bytes."""
from dataclasses import dataclass
import hashlib
import hmac
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlencode


class ConnectError(Exception):
    """Safe, credential-free user-facing error."""


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    fingerprint: str

    def __post_init__(self):
        if not isinstance(self.host, str) or any(c in self.host for c in '/\\%?#@\r\n'):
            raise ConnectError('Enter a plain hostname or IP address.')
        host = self.host.strip()
        if host.startswith('[') and host.endswith(']'):
            host = host[1:-1]
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if len(host) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', x)
                                         for x in host.rstrip('.').split('.')):
                raise ConnectError('Enter a hostname or IP address, without a URL or path.') from None
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ConnectError('TLS port must be between 1 and 65535.')
        fp = re.sub(r'[:\s]', '', self.fingerprint).lower()
        if not re.fullmatch('[0-9a-f]{64}', fp):
            raise ConnectError('Enter the 64-digit SHA-256 certificate fingerprint from the target PC.')
        object.__setattr__(self, 'host', host)
        object.__setattr__(self, 'fingerprint', fp)

    @property
    def authority(self):
        return ('[' + self.host + ']' if ':' in self.host else self.host) + ':' + str(self.port)


def pinned_socket(endpoint, timeout=8):
    # The self-signed certificate is authenticated by an independently supplied
    # SHA-256 pin, not system PKI. Never send application bytes before comparison.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    raw = socket.create_connection((endpoint.host, endpoint.port), timeout)
    try:
        stream = context.wrap_socket(raw, server_hostname=endpoint.host)
    except Exception:
        raw.close()
        raise ConnectError('Cannot establish TLS with the target PC.') from None
    if not hmac.compare_digest(hashlib.sha256(stream.getpeercert(binary_form=True)).hexdigest(), endpoint.fingerprint):
        stream.close()
        raise ConnectError('Certificate changed or fingerprint is wrong. No credentials were sent. Verify on the target PC.')
    return stream


class PinnedConnection(http.client.HTTPSConnection):
    def __init__(self, endpoint):
        super().__init__(endpoint.host, endpoint.port, timeout=8)
        self.endpoint = endpoint

    def connect(self):
        self.sock = pinned_socket(self.endpoint)


def valid_token(token):
    if not isinstance(token, str) or not 1 <= len(token) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ConnectError('Invalid pairing credential. Pair again.')
    return token


class Agent:
    def __init__(self, endpoint, token=None):
        self.endpoint = endpoint
        self.token = valid_token(token) if token is not None else None

    def request(self, method, path, body=None, binary=False):
        # Callers select fixed routes. No URL, redirect, proxy, cookie or arbitrary
        # request header is accepted from the UI or a response.
        allowed = {'/api/status', '/api/screen', '/api/screen/frame', '/api/launchers',
                   '/api/pair/start', '/api/pair/finish'}
        if path not in allowed and not (method == 'POST' and re.fullmatch(r'/api/launchers/[A-Za-z0-9%_.:-]+', path)):
            raise ConnectError('Unsupported agent operation.')
        conn = PinnedConnection(self.endpoint)
        try:
            headers = {'Accept': 'application/json', 'User-Agent': 'CouchsideComputerConnect/0.1'}
            if self.token:
                headers['Authorization'] = 'Bearer ' + self.token
            payload = None if body is None else json.dumps(body).encode()
            if payload is not None:
                headers['Content-Type'] = 'application/json'
            conn.request(method, path, payload, headers)
            response = conn.getresponse()
            if response.status != 200:
                if response.status in (301, 302, 303, 307, 308):
                    raise ConnectError('Redirect refused. Connect directly to the paired PC.')
                if response.status == 401:
                    raise ConnectError('Pairing was revoked or expired. Pair again.')
                if path == '/api/pair/finish':
                    raise ConnectError('PIN refused or expired. Start pairing again on the target PC.')
                raise ConnectError('Agent operation unavailable (HTTP %d).' % response.status)
            limit = 8 * 1024 * 1024 if binary else 1024 * 1024
            length = response.getheader('Content-Length')
            if length and (not length.isdecimal() or int(length) > limit):
                raise ConnectError('Agent response exceeds the size limit.')
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ConnectError('Agent response exceeds the size limit.')
            if binary:
                if response.getheader('Content-Type', '').split(';')[0] not in ('image/jpeg', 'image/png'):
                    raise ConnectError('Unsupported desktop image format.')
                return data
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ConnectError('Invalid agent response.')
            return result
        except ConnectError:
            raise
        except Exception:
            # Library exceptions may contain a token-bearing URL. Do not expose.
            raise ConnectError('Secure request failed. Check the PC address, TLS port and connection.') from None
        finally:
            conn.close()

    def pair_start(self):
        result = self.request('POST', '/api/pair/start', {'client':'computer-connect'})
        if result.get('identity_shown') is not True:
            raise ConnectError('The PC needs the Computer Connect pairing update to show its identity. No PIN was sent.')

    def pair_finish(self, pin):
        if not re.fullmatch('[0-9]{6}', pin):
            raise ConnectError('Enter the six-digit PIN displayed on the target PC.')
        self.token = valid_token(self.request('POST', '/api/pair/finish', {'pin': pin}).get('token'))

    def supported(self):
        result = self.request('GET', '/api/status')
        caps = result.get('caps')
        if not isinstance(caps, dict) or caps.get('input_only') is not True:
            raise ConnectError('This agent needs the input-only update. No controller fallback was attempted.')
        return result

    def socket(self):
        import websocket
        self.supported()
        token = valid_token(self.token)
        stream = pinned_socket(self.endpoint)
        ws = websocket.WebSocket(enable_multithread=True)
        # Stop oversized individual frames before reading their payload. The
        # Couchside protocol sends unfragmented small JSON messages only.
        original_read = ws.frame_buffer.recv_strict
        def bounded_read(size):
            if size > 65536:
                raise ConnectError('Oversized control frame refused.')
            return original_read(size)
        ws.frame_buffer.recv_strict = bounded_read
        original_frame = ws.frame_buffer.recv_frame
        def bounded_frame():
            frame = original_frame()
            if not frame.fin or frame.opcode == websocket.ABNF.OPCODE_CONT:
                raise ConnectError('Fragmented control frames are not supported.')
            return frame
        ws.frame_buffer.recv_frame = bounded_frame
        try:
            ws.connect('wss://' + self.endpoint.authority + '/ws/gamepad?' + urlencode({
                'token': token, 'mode': 'input', 'handoff': 'ask', 'name': 'Computer Connect'}),
                socket=stream, timeout=1, redirect_limit=0, suppress_origin=True,
                http_no_proxy=['*'])
            if ws.getstatus() != 101:
                raise ConnectError('WebSocket redirect or upgrade refused.')
            return ws
        except Exception:
            ws.abort()
            stream.close()
            raise ConnectError('Secure input connection failed. No fallback was attempted.') from None
