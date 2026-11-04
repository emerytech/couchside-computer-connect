#!/usr/bin/env python3
"""Fresh MIT desktop client's pinning, credentials, control and image boundaries.

Real TLS and WSS against agent handlers; Windows injection remains synthetic.
"""
import importlib.util
import json
import os
from pathlib import Path
import queue
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'computer-connect'))
from computer_connect.transport import Agent, Endpoint, ConnectError
from computer_connect.session import Session
from computer_connect.store import Store
from computer_connect.discovery import parse_reply, scan, identity_code
from computer_connect.pin_rules import distribute
from computer_connect.images import decode_frame
spec=importlib.util.spec_from_file_location('connect_agent',ROOT/'agent/win/couchsided-win.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        w.Handler.mock=True;w.Handler.token='synthetic-secret-never-log'
        w.pair_show_on_box=lambda *_:None
        w.set_caps(True)
        cls.calls=[]
        cls.redirect=False
        cls.oversized=False
        class Handler(w.Handler):
            def _log(self,code,started):cls.calls.append(code)
            def do_GET(self):
                if cls.redirect and self.path.startswith('/ws/gamepad'):
                    self.send_response(302);self.send_header('Location','https://127.0.0.1:1/steal');self.send_header('Content-Length','0');self.end_headers();return
                if cls.oversized and self.path=='/api/status':
                    self.send_response(200);self.send_header('Content-Length','99999999');self.end_headers();return
                return super().do_GET()
        old=w.Handler;w.Handler=Handler
        try:cls.server=w._start_https('127.0.0.1',0,str(Path(cls.tmp.name)/'tls'))
        finally:w.Handler=old
        cls.endpoint=Endpoint('127.0.0.1',cls.server.server_port,w.TLS_ADVERT['fp'])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()

    def setUp(self):
        self.agent=Agent(self.endpoint,'synthetic-secret-never-log')
        self.sessions=[];type(self).redirect=False;type(self).oversized=False

    def tearDown(self):
        for s in self.sessions:s.close()
        self.until(lambda:not w.GAMEPAD_SESSIONS)

    def until(self,condition):
        end=time.monotonic()+3
        while time.monotonic()<end:
            if condition():return
            time.sleep(.01)
        self.fail('asynchronous condition did not settle')

    def session(self):
        messages=[]
        s=Session(self.agent,lambda kind,value:messages.append((kind,value)))
        self.sessions.append(s);s.start()
        return s,messages

    def test_real_pinned_https_and_image(self):
        self.assertTrue(self.agent.supported()['caps']['input_only'])
        image=decode_frame(self.agent.request('GET','/api/screen/frame',binary=True))
        self.assertGreater(image.width,0)
        with self.assertRaises(Exception):decode_frame(b'not an image')

    def test_wrong_pin_sends_no_credentials_or_http(self):
        before=len(self.calls)
        bad=Agent(Endpoint(self.endpoint.host,self.endpoint.port,'0'*64),'synthetic-secret-never-log')
        with self.assertRaises(ConnectError) as error:bad.supported()
        self.assertNotIn('synthetic-secret-never-log',str(error.exception))
        self.assertEqual(len(self.calls),before)
        with self.assertRaises(ConnectError):bad.pair_start()
        self.assertEqual(len(self.calls),before)

    def test_pairing_uses_tls_and_pin(self):
        agent=Agent(self.endpoint)
        agent.pair_start()
        pin=w.pair_pin_active()
        self.assertIsNotNone(pin)
        with self.assertRaises(ConnectError):agent.pair_finish('123')
        with self.assertRaises(ConnectError):agent.pair_finish('000000' if pin!='000000' else '111111')
        agent.pair_finish(pin)
        self.assertEqual(agent.token,self.agent.token)
        self.assertIsNone(w.pair_pin_active())

    def test_no_controller_fallback_for_old_agent(self):
        with patch.object(w,'mock_status',return_value={'caps':{'gamepad':True}}):
            with self.assertRaises(ConnectError):self.agent.socket()
        self.assertFalse(w.GAMEPAD_SESSIONS)

    def test_wss_requires_matching_pin_and_refuses_redirect(self):
        type(self).redirect=True
        with self.assertRaises(ConnectError) as error:self.agent.socket()
        self.assertNotIn(self.agent.token,str(error.exception))
        self.assertFalse(w.GAMEPAD_SESSIONS)

    def test_bounded_response_and_arbitrary_url_refusal(self):
        type(self).oversized=True
        with self.assertRaises(ConnectError):self.agent.supported()
        for path in ('https://evil.invalid','/api/update/apply','/api/launchers/../../actions/reboot'):
            with self.assertRaises(ConnectError):self.agent.request('POST',path,{})

    def test_real_wss_control_and_consent(self):
        first,events=self.session();self.until(lambda:first.held)
        second,other=self.session();self.until(lambda:any(k=='waiting' for k,_ in other))
        self.assertFalse(second.input({'t':'kt','text':'not holder'}))
        first.control('grant');self.until(lambda:second.held and not first.held)
        self.assertTrue(second.input({'t':'kt','text':'synthetic text'}))
        first.close();second.close()
        self.assertFalse(first.input({'t':'mb','k':'l','v':1}))

    def test_legacy_hello_and_unsupported_frames_close(self):
        s=Session(self.agent,lambda *_:None)
        with self.assertRaises(ConnectError):s.input({'t':'b','k':'a','v':1})
        class Fake:
            def recv_data(self,**_):return 1,b'{"t":"hello","dev":"pad"}'
            def abort(self):pass
        s.ws=Fake();s._receive();self.assertTrue(s.closed.is_set());self.assertFalse(s.held)

    def test_queue_overflow_and_old_epoch_discard(self):
        s=Session(self.agent,lambda *_:None);s.held=True
        for _ in range(64):self.assertTrue(s.input({'t':'m','dx':1,'dy':0}))
        self.assertFalse(s.input({'t':'mb','k':'l','v':0}))
        self.assertTrue(s.closed.is_set());self.assertTrue(s.outgoing.empty())
        s=Session(self.agent,lambda *_:None);s.held=True
        s.input({'t':'kt','text':'stale'});s.epoch+=1
        class Fake:
            calls=[]
            def send(self,data):self.calls.append(data);s.close()
            def abort(self):pass
        s.ws=Fake()
        s.outgoing.put((s.epoch,{'t':'ping'}));s._send()
        self.assertEqual(s.ws.calls,['{"t": "ping"}'])

    def test_store_has_no_plaintext_fallback_and_binds_identity(self):
        path=Path(self.tmp.name)/'credentials.json';store=Store(path)
        with patch('computer_connect.store.dpapi',side_effect=lambda data,decrypt=False:b'protected' if not decrypt else json.dumps({'host':self.endpoint.host,'port':self.endpoint.port,'fingerprint':self.endpoint.fingerprint,'token':self.agent.token}).encode()):
            store.save(self.endpoint,self.agent.token)
            self.assertNotIn(self.agent.token,path.read_text())
            self.assertNotIn(self.endpoint.fingerprint,path.read_text())
            ep,token=store.load();self.assertEqual(ep,self.endpoint);self.assertEqual(token,self.agent.token)
        with patch('computer_connect.store.dpapi',side_effect=ConnectError('cannot decrypt')):
            with self.assertRaises(ConnectError):store.load()
        store.forget();self.assertIsNone(store.load())

    def test_discovery_uses_responder_address_and_validates_tls(self):
        reply={'couchside':True,'name':'Test PC','ip':'evil.invalid','host':'evil.invalid','tls_port':self.endpoint.port,'tls_fp':self.endpoint.fingerprint,'version':'test-win'}
        box=parse_reply(json.dumps(reply).encode(),'127.0.0.1')
        self.assertEqual(box.endpoint.host,'127.0.0.1')
        self.assertEqual(len(identity_code(box.endpoint.fingerprint).replace(' ','')),32)
        for changed in ({'tls_port':True},{'name':'bad\nname'},{'tls_fp':'bad'},{'couchside':False}):
            with self.assertRaises(ConnectError):parse_reply(json.dumps(dict(reply,**changed)).encode(),'127.0.0.1')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp:
            udp.bind(('127.0.0.1',0));udp.settimeout(1)
            def responder():
                data,peer=udp.recvfrom(256)
                self.assertEqual(data,b'COUCHSIDE_DISCOVER?')
                udp.sendto(json.dumps(reply).encode(),peer)
            worker=threading.Thread(target=responder);worker.start()
            found=scan(seconds=.2,port=udp.getsockname()[1],targets=['127.0.0.1'])
            worker.join(2)
        self.assertEqual(found,[box])

    def test_pc_identity_is_opt_in_and_no_legacy_pin_change(self):
        plain=w.render_pin_page('123456')
        self.assertIn('Enter this PIN on your phone',plain)
        self.assertNotIn('PC identity:',plain)
        secure=w.render_pin_page('123456',True)
        self.assertIn(identity_code(self.endpoint.fingerprint),secure)
        self.assertIn('Enter this PIN in Computer Connect',secure)
        with patch.object(self.agent,'request',return_value={'ok':True}):
            with self.assertRaises(ConnectError):self.agent.pair_start()

    @unittest.skipUnless(os.name=='nt','Windows user-scoped DPAPI')
    def test_real_windows_dpapi_storage_and_tamper_refusal(self):
        path=Path(self.tmp.name)/'actual-dpapi.json';store=Store(path)
        store.save(self.endpoint,self.agent.token)
        self.assertNotIn(self.agent.token,path.read_text())
        self.assertEqual(store.load(),(self.endpoint,self.agent.token))
        outer=json.loads(path.read_text());import base64
        value=bytearray(base64.b64decode(outer['dpapi']));value[-1]^=1
        outer['dpapi']=base64.b64encode(value).decode();path.write_text(json.dumps(outer))
        with self.assertRaises(ConnectError):store.load()
        store.forget()

    @unittest.skipUnless(os.name=='nt','Windows native PowerShell JPEG encoder')
    def test_native_jpeg_encoder_submits_multiline_script(self):
        # Synthetic 2x2 BGR pixels; no screen or personal content is captured.
        bmp=w._bmp_bytes(2,2,bytes([0,0,255,0,255,0,0,0])*2)
        # Cold System.Drawing/PowerShell startup on hosted Windows can exceed
        # the interactive capture budget. Test encoding correctness separately
        # from scheduling; production keeps its bounded 8s fail-closed timeout.
        with patch.object(w,'SCREEN_CAPTURE_TIMEOUT_S',30):
            data=w._bmp_to_jpeg(bmp)
        self.assertIsNotNone(data)
        image=decode_frame(data);self.assertEqual(image.size,(2,2))

    def test_six_digit_pin_entry_typing_paste_and_invalid_input(self):
        digits=['']*6
        for i,char in enumerate('012345'):
            digits,focus=distribute(digits,i,char)
            self.assertEqual(focus,min(5,i+1))
        self.assertEqual(''.join(digits),'012345')
        self.assertEqual(distribute(digits,3,'987654'),(list('987654'),5))
        cleared,focus=distribute(digits,5,'')
        self.assertEqual(cleared[-1],'');self.assertEqual(focus,5)
        for value in ('１２３４５６','123 456','1234567','abc'):
            with self.assertRaises(ValueError):distribute(digits,0,value)
        with self.assertRaises(ValueError):distribute(digits,5,'12')

    def test_endpoint_and_token_validation(self):
        for host in ('https://pc/','pc\r\nAuthorization: test','user@pc','../pc','fe80::1%bad'):
            with self.assertRaises(ConnectError):Endpoint(host,8788,'0'*64)
        for port in (0,65536,True):
            with self.assertRaises(ConnectError):Endpoint('pc',port,'0'*64)
        self.assertEqual(Endpoint('::1',8788,'AB:'*31+'AB').authority,'[::1]:8788')
        with self.assertRaises(ConnectError):Agent(self.endpoint,'token\r\n')

    def test_pointer_metadata_degrades_closed_and_normalizes_virtual_desktop(self):
        with patch.object(w,'IS_WINDOWS',False):
            self.assertIsNone(w._screen_pointer())
        user=MagicMock()
        def position(point):
            import ctypes
            p=ctypes.cast(point,ctypes.POINTER(ctypes.c_long));p[0]=-50;p[1]=50;return 1
        user.GetCursorPos.side_effect=position
        values={76:-100,77:0,78:101,79:101}
        user.GetSystemMetrics.side_effect=lambda k:values[k]
        with patch.object(w,'IS_WINDOWS',True),patch.object(w,'_user32',user),patch.multiple(w,SM_XVIRTUALSCREEN=76,SM_YVIRTUALSCREEN=77,SM_CXVIRTUALSCREEN=78,SM_CYVIRTUALSCREEN=79,create=True):
            self.assertEqual(w._screen_pointer(),{'x':.5,'y':.5})
            values[78]=0;self.assertIsNone(w._screen_pointer())

    def test_capture_restores_thread_dpi_even_on_error(self):
        user=MagicMock();user.SetThreadDpiAwarenessContext.return_value=123
        @w._physical_desktop
        def failing():raise RuntimeError('synthetic capture error')
        with patch.object(w,'IS_WINDOWS',True),patch.object(w,'_user32',user):
            with self.assertRaises(RuntimeError):failing()
        calls=user.SetThreadDpiAwarenessContext.call_args_list
        self.assertEqual(calls[0].args[0].value,w.ctypes.c_void_p(-4).value)
        self.assertEqual(calls[1].args,(123,))

    def test_scan_retries_lost_first_datagram(self):
        udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',0));udp.settimeout(2)
        def respond():
            try:
                udp.recvfrom(100)  # deliberate packet loss
                _,peer=udp.recvfrom(100)
                udp.sendto(json.dumps({'couchside':True,'name':'retry-fixture','tls_port':8788,'tls_fp':'a'*64}).encode(),peer)
            finally:udp.close()
        t=threading.Thread(target=respond);t.start()
        found=scan(seconds=.9,port=udp.getsockname()[1],targets=['127.0.0.1'])
        t.join(2);self.assertEqual([b.name for b in found],['retry-fixture'])


if __name__=='__main__':unittest.main()
