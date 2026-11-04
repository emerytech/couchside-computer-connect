"""Bounded background input connection; no automatic takeover or reconnect."""
import json
import queue
import threading
import time

from .transport import ConnectError


class Session:
    def __init__(self, agent, notify):
        self.agent = agent
        self.notify = notify
        self.ws = None
        self.held = False
        self.epoch = 0
        self.closed = threading.Event()
        self.outgoing = queue.Queue(maxsize=64)
        self.state_lock = threading.RLock()

    def start(self):
        try:
            ws = self.agent.socket()
            with self.state_lock:
                if self.closed.is_set():
                    ws.abort()
                    return
                self.ws = ws
            threading.Thread(target=self._receive, daemon=True).start()
            threading.Thread(target=self._send, daemon=True).start()
        except Exception as error:
            self.close()
            self.notify('error', str(error) if isinstance(error, ConnectError) else 'Input connection failed.')

    def input(self, data):
        if data.get('t') not in ('m', 'mb', 'mw', 'kt', 'k'):
            raise ConnectError('Unsupported input message.')
        with self.state_lock:
            if not self.held or self.closed.is_set():
                return False
            return self._enqueue(data)

    def control(self, kind):
        if kind not in ('request', 'grant', 'deny'):
            raise ConnectError('Unsupported control operation.')
        return self._enqueue({'t': kind})

    def _enqueue(self, data):
        if self.closed.is_set():
            return False
        try:
            self.outgoing.put_nowait((self.epoch, data))
            return True
        except queue.Full:
            # Never drop a release or retain queued input after overload.
            self.close()
            self.notify('error', 'Input queue is full. Disconnected safely; request control again.')
            return False

    def _send(self):
        last_ping = time.monotonic()
        try:
            while not self.closed.is_set():
                try:
                    epoch, data = self.outgoing.get(timeout=.1)
                    with self.state_lock:
                        # Inputs queued before a handoff cannot be replayed later.
                        if epoch != self.epoch:
                            continue
                        if data.get('t') not in ('request', 'grant', 'deny') and not self.held:
                            continue
                        if self.closed.is_set():
                            return
                        self.ws.send(json.dumps(data))
                except queue.Empty:
                    pass
                if time.monotonic() - last_ping >= 4:
                    self.ws.send('{"t":"ping"}')
                    last_ping = time.monotonic()
        except Exception:
            if not self.closed.is_set():
                self.notify('error', 'Input connection lost. Held inputs were released.')
            self.close()

    def _receive(self):
        import websocket
        last_seen = time.monotonic()
        try:
            while not self.closed.is_set():
                try:
                    opcode, raw = self.ws.recv_data(control_frame=True)
                except websocket.WebSocketTimeoutException:
                    if time.monotonic() - last_seen > 15:
                        raise ConnectError('Input heartbeat timed out.')
                    continue
                last_seen = time.monotonic()
                if opcode == websocket.ABNF.OPCODE_CLOSE:
                    raise ConnectError('Input session closed. Request control to reconnect.')
                if opcode != websocket.ABNF.OPCODE_TEXT:
                    continue
                if len(raw) > 16384:
                    raise ConnectError('Control response exceeds the size limit.')
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ConnectError('Invalid control response.')
                kind = data.get('t')
                with self.state_lock:
                    if kind == 'hello':
                        self.epoch += 1
                        if data.get('mode') != 'input' or data.get('dev') != 'input':
                            raise ConnectError('Agent did not confirm input-only mode. Disconnected.')
                        self.held = True
                    elif kind in ('waiting', 'released', 'denied'):
                        self.epoch += 1
                        self.held = False
                        # Flush input from the old ownership period.
                        while True:
                            try:self.outgoing.get_nowait()
                            except queue.Empty:break
                    elif kind == 'err':
                        raise ConnectError('Agent refused the input operation.')
                if kind in ('hello', 'waiting', 'released', 'denied', 'control_request', 'blocked', 'resumed'):
                    self.notify(kind, None)
        except Exception as error:
            if not self.closed.is_set():
                self.notify('error', str(error) if isinstance(error, ConnectError) else 'Input connection closed.')
            self.close()

    def close(self):
        with self.state_lock:
            if self.closed.is_set():
                return
            self.closed.set()
            self.epoch += 1
            self.held = False
            while True:
                try:self.outgoing.get_nowait()
                except queue.Empty:break
            ws = self.ws
        # Abrupt socket shutdown is intentional: it immediately activates the
        # agent's tested EOF/button-release path, even when receive is blocked.
        if ws:
            try:ws.abort()
            except Exception:pass
        self.notify('disconnected', None)
