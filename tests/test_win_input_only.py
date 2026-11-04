#!/usr/bin/env python3
"""Driver-free input must not change controller ownership, auth, or releases.

Real loopback HTTP/WebSocket sessions and real decoders; only Win32/ViGEm
backends are synthetic. These tests do not certify native Windows injection.
"""
import base64
import importlib.util
import json
import socket
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('win_input_only', ROOT/'agent/win/couchsided-win.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class Device:
    name = 'synthetic-pad'
    created = []

    def __init__(self):
        self.events = []
        self.destroyed = 0
        type(self).created.append(self)

    def emit(self, events):
        self.events.extend(events)

    def destroy(self):
        self.destroyed += 1


class Mouse(Device):
    created = []


class Keyboard(Device):
    created = []


class Client:
    def __init__(self, port, query):
        self.sock = socket.create_connection(('127.0.0.1', port), timeout=2)
        self.file = self.sock.makefile('rb')
        self.sock.sendall(('GET /ws/gamepad?%s HTTP/1.1\r\nHost: localhost\r\n'
            'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' %
            (query, base64.b64encode(b'0123456789abcdef').decode())).encode())
        self.status = int(self.file.readline().split()[1])
        while self.file.readline() not in (b'\r\n', b''):
            pass

    def recv(self):
        header = self.file.read(2)
        if not header:
            return None
        size = header[1] & 127
        if size == 126:
            size = int.from_bytes(self.file.read(2), 'big')
        elif size == 127:
            size = int.from_bytes(self.file.read(8), 'big')
        body = self.file.read(size)
        return json.loads(body) if header[0] & 15 == 1 else {'opcode': header[0] & 15}

    def send(self, data):
        body = json.dumps(data).encode()
        mask = b'abcd'
        length = bytes([128 | len(body)]) if len(body) < 126 else b'\xfe' + len(body).to_bytes(2, 'big')
        self.sock.sendall(b'\x81' + length + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(body)))

    def barrier(self):
        self.send({'t': 'ping'})
        return self.recv()

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.file.close()
        self.sock.close()


class InputOnlyTests(unittest.TestCase):
    def setUp(self):
        w.GAMEPAD_SESSIONS.clear()
        w.GAMEPAD_HOLDER = None
        for cls in (Device, Mouse, Keyboard):
            cls.created.clear()
        self.patches = [patch.object(w, 'ViGEmGamepad', Device),
                        patch.object(w, 'WinMouse', Mouse), patch.object(w, 'WinKeyboard', Keyboard),
                        patch.object(w, '_input_reachable', return_value=True),
                        patch.object(w, '_process_privilege', return_value={'elevated': False, 'uiaccess': False}),
                        patch.object(w, '_foreground_is_elevated', return_value=False)]
        for p in self.patches:
            p.start()
        class Handler(w.Handler):
            token = 'synthetic-test-token'
            mock = False
        self.server = w.QuietThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.clients = []

    def wait_for(self, predicate):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.005)
        self.fail('session lifecycle did not settle')

    def connect(self, query='mode=input&handoff=ask&name=Desktop', token=True):
        c = Client(self.server.server_port, ('token=synthetic-test-token&' if token else '') + query)
        self.clients.append(c)
        return c

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.wait_for(lambda: not w.GAMEPAD_SESSIONS)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        for p in reversed(self.patches):
            p.stop()

    def test_input_works_without_driver_and_never_allocates_pad(self):
        with patch.object(w, 'ViGEmGamepad', side_effect=RuntimeError('driver missing')) as pad:
            c = self.connect()
            self.assertEqual(c.status, 101)
            self.assertEqual(c.recv(), {'t': 'hello', 'dev': 'input', 'text': 'unicode', 'mode': 'input'})
            c.send({'t': 'm', 'dx': 7, 'dy': -3})
            c.send({'t': 'mb', 'k': 'l', 'v': 1})
            c.send({'t': 'mw', 'dy': 1})
            c.send({'t': 'kt', 'text': 'synthetic QA'})
            c.send({'t': 'k', 'key': 'enter'})
            self.assertEqual(c.barrier(), {'t': 'pong'})
            self.assertTrue(Mouse.created[0].events)
            self.assertTrue(Keyboard.created[0].events)
            pad.assert_not_called()
            with w.GAMEPAD_LOCK:
                entry = w.GAMEPAD_HOLDER
            c.close()
            self.wait_for(lambda: w.GAMEPAD_HOLDER is None)
            self.assertIn(('btn', 'l', 0), Mouse.created[0].events)
            self.assertEqual(Mouse.created[0].destroyed, 1)
            # Stale held state cannot cause a disconnected input client to emit.
            before = list(Mouse.created[0].events)
            entry['held'] = True
            h = object.__new__(w.Handler)
            h.mock = True
            self.assertTrue(h._gamepad_message(None, entry, b'{"t":"mb","k":"l","v":1}'))
            self.assertEqual(Mouse.created[0].events, before)

    def test_default_and_explicit_gamepad_keep_legacy_hello_and_driver_failure(self):
        for mode in ('', 'mode=gamepad&'):
            c = self.connect(mode + 'name=Phone')
            self.assertEqual(c.recv(), {'t': 'hello', 'dev': 'synthetic-pad', 'text': 'unicode'})
            c.send({'t': 'b', 'k': 'a', 'v': 1})
            self.assertEqual(c.barrier(), {'t': 'pong'})
            self.assertEqual(Device.created[-1].events, [('btn', 'a', 1)])
            c.close()
            self.wait_for(lambda: not w.GAMEPAD_SESSIONS)
        with patch.object(w, 'ViGEmGamepad', side_effect=RuntimeError('missing')):
            c = self.connect('name=OldPhone')
            self.assertEqual(c.recv()['t'], 'err')
            self.assertEqual(c.recv()['opcode'], 8)
            self.wait_for(lambda: w.GAMEPAD_HOLDER is None)

    def test_auth_and_invalid_mode_refused_before_upgrade(self):
        for query, token, status in [('mode=input', False, 401),
                ('mode=unknown', True, 400), ('mode=', True, 400),
                ('mode=input&mode=gamepad', True, 400)]:
            c = self.connect(query, token)
            self.assertEqual(c.status, status)
        self.assertFalse(w.GAMEPAD_SESSIONS)
        self.assertFalse(Device.created or Mouse.created or Keyboard.created)

    def test_controller_and_mode_change_messages_are_rejected(self):
        for msg in ({'t': 'b', 'k': 'a', 'v': 1}, {'t': 't', 'k': 'lt', 'v': 255},
                    {'t': 's', 'k': 'l', 'x': 1, 'y': 1}, {'t': 'mode', 'mode': 'gamepad'}):
            c = self.connect()
            self.assertEqual(c.recv()['mode'], 'input')
            c.send(msg)
            self.assertEqual(c.recv()['t'], 'err')
            self.assertEqual(c.recv()['opcode'], 8)
            self.wait_for(lambda: not w.GAMEPAD_SESSIONS)
        self.assertFalse(Device.created)

    def test_mixed_handoff_deny_grant_force_and_disconnect_promotion(self):
        phone = self.connect('name=Phone')
        self.assertEqual(phone.recv()['dev'], 'synthetic-pad')
        desktop = self.connect()
        self.assertEqual(desktop.recv()['t'], 'waiting')
        self.assertEqual(phone.recv()['t'], 'control_request')
        desktop.send({'t': 'kt', 'text': 'not holder'})
        self.assertEqual(desktop.barrier(), {'t': 'pong'})
        self.assertFalse(any(k.events for k in Keyboard.created))
        phone.send({'t': 'deny'})
        self.assertEqual(desktop.recv()['t'], 'denied')
        desktop.send({'t': 'request'})
        self.assertEqual(phone.recv()['t'], 'control_request')
        phone.send({'t': 'grant'})
        self.assertEqual(phone.recv()['t'], 'released')
        self.assertEqual(desktop.recv()['mode'], 'input')
        self.assertEqual(Device.created[0].destroyed, 1)
        desktop.send({'t': 'mb', 'k': 'l', 'v': 1})
        self.assertEqual(desktop.barrier(), {'t': 'pong'})
        mouse = w.GAMEPAD_HOLDER['mouse']
        phone.send({'t': 'force'})
        self.assertEqual(desktop.recv()['t'], 'released')
        self.assertEqual(phone.recv()['dev'], 'synthetic-pad')
        self.assertIn(('btn', 'l', 0), mouse.events)
        # A default takeover is still deliberate and replaces the holder.
        takeover = self.connect('mode=input&name=Takeover')
        self.assertEqual(phone.recv()['t'], 'released')
        self.assertEqual(takeover.recv()['mode'], 'input')
        desktop.send({'t': 'request'})
        self.assertEqual(takeover.recv()['t'], 'control_request')
        takeover.close()
        self.assertEqual(desktop.recv()['mode'], 'input')
        self.assertIs(w.GAMEPAD_HOLDER['mouse'], mouse)
        self.assertEqual(len(Device.created), 2)

    def test_handoff_waits_for_inflight_mouse_down_before_release(self):
        desktop = self.connect()
        self.assertEqual(desktop.recv()['mode'], 'input')
        phone = self.connect('name=Phone&handoff=ask')
        self.assertEqual(phone.recv()['t'], 'waiting')
        self.assertEqual(desktop.recv()['t'], 'control_request')
        entered, finish, force_started = threading.Event(), threading.Event(), threading.Event()
        mouse = w.GAMEPAD_HOLDER['mouse']
        emit = mouse.emit
        control = w.Handler._handle_control
        def slow_emit(events):
            if events == [('btn', 'l', 1)]:
                entered.set()
                if not finish.wait(2):
                    raise RuntimeError('test release timed out')
            emit(events)
        def observed_control(handler, entry, t):
            force_started.set()
            return control(handler, entry, t)
        with patch.object(mouse, 'emit', side_effect=slow_emit), patch.object(
                w.Handler, '_handle_control', observed_control):
            try:
                desktop.send({'t': 'mb', 'k': 'l', 'v': 1})
                self.assertTrue(entered.wait(2))
                phone.send({'t': 'force'})
                self.assertTrue(force_started.wait(2))
                # Force arrived while emission is blocked, but cannot release
                # a button before the old holder's in-flight down is finished.
                self.assertNotIn(('btn', 'l', 0), mouse.events)
            finally:
                finish.set()
            self.assertEqual(desktop.recv()['t'], 'released')
            self.assertEqual(phone.recv()['dev'], 'synthetic-pad')
        self.assertLess(mouse.events.index(('btn', 'l', 1)), mouse.events.index(('btn', 'l', 0)))
        before = list(mouse.events)
        desktop.send({'t': 'mb', 'k': 'l', 'v': 1})
        self.assertEqual(desktop.barrier(), {'t': 'pong'})
        self.assertEqual(mouse.events, before)

    def test_native_input_creation_failure_is_closed(self):
        with patch.object(w, 'WinKeyboard', side_effect=RuntimeError('no keyboard')):
            c = self.connect()
            self.assertEqual(c.recv()['t'], 'err')
            self.assertEqual(c.recv()['opcode'], 8)
            self.wait_for(lambda: w.GAMEPAD_HOLDER is None)
        self.assertFalse(Device.created)
        self.assertIn(('btn', 'l', 0), Mouse.created[0].events)

    def test_driver_disappears_during_grant_and_input_waiter_recovers(self):
        desktop = self.connect()
        self.assertEqual(desktop.recv()['mode'], 'input')
        phone = self.connect('name=Phone&handoff=ask')
        self.assertEqual(phone.recv()['t'], 'waiting')
        self.assertEqual(desktop.recv()['t'], 'control_request')
        with patch.object(w, 'ViGEmGamepad', side_effect=RuntimeError('driver missing')):
            desktop.send({'t': 'grant'})
            self.assertEqual(desktop.recv()['t'], 'released')
            self.assertEqual(phone.recv()['t'], 'err')
            self.assertEqual(desktop.recv()['mode'], 'input')
            self.assertEqual(desktop.barrier(), {'t': 'pong'})
        self.assertFalse(Device.created)

    def test_heartbeat_and_idle_reap_release_buttons(self):
        c = self.connect()
        self.assertEqual(c.recv()['mode'], 'input')
        c.send({'t': 'mb', 'k': 'l', 'v': 1})
        self.assertEqual(c.barrier(), {'t': 'pong'})
        mouse = w.GAMEPAD_HOLDER['mouse']
        w._gamepad_keepalive_tick()
        self.assertEqual(c.recv()['opcode'], w.WS_OP_PING)
        # A recv timeout uses the same finally cleanup as EOF. Inject it at
        # the real receive boundary, after waking the blocked current read.
        with patch.object(w, 'ws_recv_frame', return_value=None):
            self.assertEqual(c.barrier(), {'t': 'pong'})
            self.wait_for(lambda: w.GAMEPAD_HOLDER is None)
        self.assertIn(('btn', 'l', 0), mouse.events)
        self.assertEqual(mouse.destroyed, 1)

    def test_input_capability_is_independent_of_vigem(self):
        with patch.object(w, 'vigem_ready', return_value=False):
            w.set_caps(False)
            self.assertFalse(w.CAPS['gamepad'])
            self.assertTrue(w.CAPS['input_only'])
        w.set_caps(True)
        self.assertTrue(w.CAPS['input_only'])


if __name__ == '__main__':
    unittest.main()
