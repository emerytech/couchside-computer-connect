"""Native desktop UI. Networking and decoding run off the Tk event thread."""
from concurrent.futures import ThreadPoolExecutor
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import quote

from PIL import Image, ImageTk

from . import __version__
from .session import Session
from .store import Store
from .transport import Agent, ConnectError, Endpoint

from .images import decode_frame
from . import theme, foreground
from .discovery import scan, inspect, identity_code
from .pin import PinEntry


class App:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.events = queue.Queue(maxsize=32)
        self.generation = 0
        self.agent = None
        self.pending = None
        self.session = None
        self.photo = None
        self.image = None
        self.pointer = None
        self.preview_busy = False
        self.busy = False
        self.closing = False
        self.store = Store()
        self.last_move = None
        self.pad_origin = None
        self.pad_started = 0
        self.last_move_time = 0
        self.launchers = []
        self.dragging = tk.BooleanVar(value=False)
        self.preview = tk.BooleanVar(value=False)
        self.remember = tk.BooleanVar(value=False)
        self.boxes = []
        self.selected_endpoint = None
        self.manual = tk.BooleanVar(value=False)
        self.identity_confirmed = tk.BooleanVar(value=False)
        self.identity = tk.StringVar(value='PC identity appears when pairing starts')
        self.host = tk.StringVar()
        self.port = tk.StringVar(value='8788')
        self.fp = tk.StringVar()
        self.pin = tk.StringVar()
        self.status = tk.StringVar(value='Choose a PC to get started')
        self.control_status = tk.StringVar(value='View only · control is off')
        root.title('Couchside Computer Connect')
        root.geometry('1120x830')
        root.minsize(980, 740)
        root.configure(bg='#0b1220')
        mono,body_font=theme.install(root)
        shell=ttk.Frame(root,padding=18);shell.pack(fill='both',expand=True,padx=12,pady=12)
        header=ttk.Frame(shell);header.pack(fill='x',pady=(0,16))
        self.logo=ImageTk.PhotoImage(Image.open(theme.ASSETS/'wordmark.png').convert('RGBA').resize((194,48)))
        ttk.Label(header,image=self.logo,background=theme.BG).pack(side='left')
        ttk.Label(header,text='Computer Connect',style='Header.TLabel').pack(side='left',padx=16)
        ttk.Label(header,text='FREE LOCAL PREVIEW  '+__version__,style='Badge.TLabel').pack(side='right')
        body=ttk.Frame(shell);body.pack(fill='both',expand=True)
        rail_card=theme.Card(body,width=305);rail_card.pack(side='left',fill='y',padx=(0,14));rail=rail_card.content
        ttk.Label(rail,text='CONNECT TO YOUR PC',style='Section.TLabel').pack(anchor='w',pady=(0,12))
        ttk.Button(rail,text='Scan for boxes',command=self.scan_boxes,style='Accent.TButton').pack(fill='x',pady=(0,8))
        self.box_choice=ttk.Combobox(rail,state='readonly')
        self.box_choice.pack(fill='x',pady=(0,6));self.box_choice.set('Choose a PC')
        self.box_choice.bind('<<ComboboxSelected>>',self.select_box)
        ttk.Checkbutton(rail,text='Enter an address manually',variable=self.manual,command=self.toggle_manual).pack(anchor='w',pady=4)
        self.manual_frame=ttk.Frame(rail,style='Card.TFrame')
        ttk.Label(self.manual_frame,text='Hostname / IP').grid(row=0,column=0,sticky='w')
        ttk.Label(self.manual_frame,text='TLS port').grid(row=0,column=1,sticky='w')
        self.host_entry=ttk.Entry(self.manual_frame,textvariable=self.host,width=19)
        self.host_entry.grid(row=1,column=0,sticky='ew',padx=(0,6))
        ttk.Entry(self.manual_frame,textvariable=self.port,width=7).grid(row=1,column=1,sticky='ew')
        self.manual_frame.columnconfigure(0,weight=1)
        self.pair_button=ttk.Button(rail,text='1  Start secure pairing',command=self.pair_start,style='Accent.TButton');self.pair_button.pack(fill='x',pady=(8,0))
        ttk.Label(rail,textvariable=self.identity,wraplength=260,foreground=theme.BLUE,font=(mono,10)).pack(anchor='w',pady=(12,4))
        ttk.Checkbutton(rail,text='PC identity matches',variable=self.identity_confirmed).pack(anchor='w')
        ttk.Label(rail,text='PIN shown on the target PC').pack(anchor='w',pady=(14,4))
        self.pin_entry=PinEntry(rail,self.pin,mono);self.pin_entry.pack(fill='x',pady=4)
        self.finish_button=ttk.Button(rail,text='2  Confirm PIN',command=self.pair_finish);self.finish_button.pack(fill='x',pady=8)
        remember=ttk.Checkbutton(rail,text='Remember on this Windows account',variable=self.remember,command=self.toggle_remember)
        remember.pack(anchor='w',pady=4)
        if os.name!='nt':remember.state(['disabled'])
        connection_row=ttk.Frame(rail,style='Card.TFrame');connection_row.pack(fill='x',pady=(10,4))
        ttk.Button(connection_row,text='Reconnect',command=self.reconnect).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(connection_row,text='Disconnect',command=self.disconnect).pack(side='left',fill='x',expand=True)
        actions_row=ttk.Frame(rail,style='Card.TFrame');actions_row.pack(fill='x',pady=4)
        ttk.Button(actions_row,text='Forget pairing',command=self.forget).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(actions_row,text='Help',command=self.help).pack(side='left',fill='x',expand=True)
        ttk.Label(rail,textvariable=self.status,wraplength=260,foreground=theme.GREEN).pack(anchor='w',pady=12)
        right_card=theme.Card(body);right_card.pack(side='left',fill='both',expand=True);right=right_card.content
        bar=ttk.Frame(right,style='Card.TFrame');bar.pack(fill='x')
        ttk.Label(bar,text='DESKTOP PREVIEW',style='Section.TLabel').pack(side='left')
        ttk.Checkbutton(bar,text='Live preview · ~1 fps',variable=self.preview,command=self.preview_changed).pack(side='right')
        self.canvas=tk.Canvas(right,bg=theme.INSET,highlightthickness=1,highlightbackground=theme.BORDER,height=200)
        self.canvas.pack(fill='both',expand=True,pady=10)
        self.canvas.bind('<Configure>',lambda e:self.paint())
        self.clear_preview('Desktop preview is off\nEnable it to view your paired PC')
        controls=ttk.Frame(right,style='Card.TFrame');controls.pack(fill='x')
        ttk.Label(controls,textvariable=self.control_status).pack(side='left')
        ttk.Button(controls,text='Request control',command=self.request_control,style='Accent.TButton').pack(side='right')
        handoff=ttk.Frame(right,style='Card.TFrame');handoff.pack(fill='x',pady=6)
        ttk.Button(handoff,text='Pass control',command=lambda:self.control('grant')).pack(side='left')
        ttk.Button(handoff,text='Keep control',command=lambda:self.control('deny')).pack(side='left',padx=6)
        ttk.Button(handoff,text='Release control',command=self.release_control).pack(side='right')
        ttk.Checkbutton(handoff,text='Hold left to drag',variable=self.dragging,command=self.drag_toggle).pack(side='left',padx=6)
        self.trackpad=tk.Canvas(right,bg=theme.INSET,height=78,highlightthickness=1,highlightbackground=theme.BORDER,takefocus=True)
        self.trackpad.pack(fill='x',pady=(4,8))
        self.trackpad.create_text(14,20,anchor='w',fill=theme.TEXT,text='TRACKPAD  ·  drag to move  ·  click / right-click  ·  wheel to scroll')
        self.trackpad.create_text(14,46,anchor='w',fill=theme.DIM,text='Focus to type · Leaving Computer Connect releases control' )
        self.trackpad.bind('<ButtonPress-1>',self.pad_down)
        self.trackpad.bind('<B1-Motion>',self.pad_motion)
        self.trackpad.bind('<ButtonRelease-1>',self.pad_up)
        self.trackpad.bind('<Button-3>',lambda e:self.click('r'))
        self.trackpad.bind('<MouseWheel>',lambda e:self.send({'t':'mw','dy':1 if e.delta>0 else -1}))
        self.trackpad.bind('<Button-4>',lambda e:self.send({'t':'mw','dy':1}))
        self.trackpad.bind('<Button-5>',lambda e:self.send({'t':'mw','dy':-1}))
        self.trackpad.bind('<KeyPress>',self.pad_key)
        keys=ttk.Frame(right,style='Card.TFrame');keys.pack(fill='x')
        for label,key in [('Esc','esc'),('Tab','tab'),('Enter','enter'),('⌫','backspace'),('←','left'),('↑','up'),('↓','down'),('→','right')]:
            ttk.Button(keys,text=label,width=5,command=lambda k=key:self.send({'t':'k','key':k})).pack(side='left',padx=(0,3))
        textrow=ttk.Frame(right,style='Card.TFrame');textrow.pack(fill='x',pady=8)
        self.text=tk.StringVar()
        self.text_entry=ttk.Entry(textrow,textvariable=self.text);self.text_entry.pack(side='left',fill='x',expand=True)
        ttk.Button(textrow,text='Send text',command=self.send_text).pack(side='right',padx=(6,0))
        launch=ttk.Frame(right,style='Card.TFrame');launch.pack(fill='x')
        self.launch_choice=ttk.Combobox(launch,state='readonly');self.launch_choice.pack(side='left',fill='x',expand=True)
        ttk.Button(launch,text='Refresh apps',command=self.refresh_launchers).pack(side='left',padx=6)
        ttk.Button(launch,text='Launch',command=self.launch).pack(side='right')
        ttk.Label(right,text='Snapshot preview, not video streaming. No audio, file transfer or Internet relay.',style='Muted.TLabel').pack(anchor='w',pady=(8,0))
        menu=tk.Menu(root)
        connection_menu=tk.Menu(menu,tearoff=False)
        connection_menu.add_command(label='Scan for boxes',command=self.scan_boxes)
        self.box_menu=tk.Menu(connection_menu,tearoff=False)
        connection_menu.add_cascade(label='Choose a PC',menu=self.box_menu)
        connection_menu.add_command(label='Enter address…',command=self.address_focus)
        connection_menu.add_command(label='Start PIN pairing',command=self.pair_start)
        connection_menu.add_checkbutton(label='PC identity matches',variable=self.identity_confirmed)
        connection_menu.add_command(label='Enter PIN…',command=self.pin_entry.focus_set)
        connection_menu.add_command(label='Complete PIN pairing',command=self.pair_finish)
        connection_menu.add_separator()
        connection_menu.add_command(label='Reconnect',command=self.reconnect)
        connection_menu.add_command(label='Disconnect',command=self.disconnect)
        connection_menu.add_command(label='Forget saved pairing',command=self.forget)
        menu.add_cascade(label='Connection',menu=connection_menu)
        view_menu=tk.Menu(menu,tearoff=False)
        view_menu.add_checkbutton(label='Live desktop preview',variable=self.preview,command=self.preview_changed)
        menu.add_cascade(label='View',menu=view_menu)
        control_menu=tk.Menu(menu,tearoff=False)
        control_menu.add_command(label='Request control',command=self.request_control)
        control_menu.add_command(label='Pass control',command=lambda:self.control('grant'))
        control_menu.add_command(label='Keep control',command=lambda:self.control('deny'))
        control_menu.add_command(label='Release control',command=self.release_control)
        control_menu.add_separator()
        control_menu.add_command(label='Compose text…',command=self.text_entry.focus_set)
        control_menu.add_command(label='Send composed text',command=self.send_text)
        control_menu.add_separator()
        control_menu.add_command(label='Focus trackpad',command=self.trackpad.focus_set)
        mouse_menu=tk.Menu(control_menu,tearoff=False)
        for label,action in (
            ('Left click',lambda:self.click('l')),('Right click',lambda:self.click('r')),
            ('Scroll up',lambda:self.send({'t':'mw','dy':1})),
            ('Scroll down',lambda:self.send({'t':'mw','dy':-1})),
            ('Move left',lambda:self.send({'t':'m','dx':-30,'dy':0})),
            ('Move right',lambda:self.send({'t':'m','dx':30,'dy':0})),
            ('Move up',lambda:self.send({'t':'m','dx':0,'dy':-30})),
            ('Move down',lambda:self.send({'t':'m','dx':0,'dy':30}))):
            mouse_menu.add_command(label=label,command=action)
        control_menu.add_cascade(label='Mouse',menu=mouse_menu)
        menu.add_cascade(label='Control',menu=control_menu)
        help_menu=tk.Menu(menu,tearoff=False);help_menu.add_command(label='Help & limitations',command=self.help)
        menu.add_cascade(label='Help',menu=help_menu)
        root.config(menu=menu)
        root.bind('<FocusOut>',lambda e:root.after(120,self.focus_check),add='+')
        root.bind('<Unmap>',lambda e:self.release_control() if e.widget is root else None,add='+')
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(40,self.pump)
        root.after(1000,self.preview_tick)
        root.after(200,self.focus_poll)
        try:
            saved=self.store.load()
            if saved:
                endpoint,token=saved;self.agent=Agent(endpoint,token)
                self.host.set(endpoint.host);self.port.set(str(endpoint.port));self.fp.set(endpoint.fingerprint)
                self.remember.set(True);self.status.set('Saved pairing loaded. Reconnect when ready.')
        except ConnectError as error:self.status.set(str(error))

    def post(self, kind, payload, generation):
        if self.closing or generation!=self.generation:return
        try:self.events.put_nowait((kind,payload,generation))
        except queue.Full:
            # Control events must not vanish behind a backlog of images.
            if self.session:self.session.close()

    def work(self, fn, callback=None):
        generation=self.generation
        def task():
            try:value=fn()
            except Exception as error:
                value=str(error) if isinstance(error,ConnectError) else 'Operation failed. Check the connection and try again.'
                self.post('error',value,generation)
            else:self.post('callback',(callback,value),generation)
        self.pool.submit(task)

    def pump(self):
        try:
            while True:
                kind,payload,generation=self.events.get_nowait()
                if generation!=self.generation:continue
                if kind=='session':
                    session,kind,payload=payload
                    if self.session is not session:continue
                if kind=='callback':
                    callback,value=payload
                    if callback:
                        try:callback(value)
                        except Exception as error:
                            self.busy=False
                            self.status.set(str(error) if isinstance(error,ConnectError) else 'Operation could not finish. Check local storage permissions and reconnect.')
                elif kind=='error':
                    self.busy=False;self.status.set(payload)
                elif kind=='hello':self.control_status.set('You have control · trackpad and typing are active')
                elif kind=='waiting':self.control_status.set('Waiting for the current holder to pass control')
                elif kind=='released':
                    self.dragging.set(False);self.control_status.set('Control was passed · view only')
                elif kind=='denied':self.control_status.set('Control request declined')
                elif kind=='control_request':self.control_status.set('Another device requests control · Pass or Keep control')
                elif kind=='blocked':self.control_status.set('Windows input paused · unlock the PC / focus a normal app')
                elif kind=='resumed':self.control_status.set('You have control · Windows input resumed')
                elif kind=='disconnected':
                    self.dragging.set(False);self.control_status.set('View only · control is off')
        except queue.Empty:pass
        if not self.closing:self.root.after(40,self.pump)

    def scan_boxes(self):
        if self.busy:return
        self.busy=True;self.status.set('Looking for Couchside boxes on your local network…')
        def done(boxes):
            self.busy=False;self.boxes=boxes
            self.box_menu.delete(0,'end')
            for i,box in enumerate(boxes):
                self.box_menu.add_command(label=box.name+' · '+box.endpoint.host,command=lambda n=i:self.choose_box(n))
            self.box_choice['values']=[box.name+' · '+box.endpoint.host for box in boxes]
            self.box_choice.set('Choose a PC' if boxes else 'No boxes found')
            self.status.set('Choose a PC, then start PIN pairing.' if boxes else 'No encrypted boxes found. Check the PC is awake, or enter its address manually.')
        self.work(scan,done)

    def select_box(self,event=None):
        self.choose_box(self.box_choice.current())

    def choose_box(self,index):
        if not 0<=index<len(self.boxes):return
        self.box_choice.current(index)
        endpoint=self.boxes[index].endpoint
        self.disconnect();self.agent=None;self.selected_endpoint=endpoint
        self.host.set(endpoint.host);self.port.set(str(endpoint.port));self.fp.set(endpoint.fingerprint)
        self.identity_confirmed.set(False);self.identity.set('PC identity appears when pairing starts')
        self.status.set('Selected '+self.boxes[index].name+'. Start pairing to show its PIN.')

    def address_focus(self):
        self.manual.set(True);self.toggle_manual();self.host_entry.focus_set()

    def toggle_manual(self):
        if self.manual.get():self.manual_frame.pack(fill='x',pady=6,before=self.pair_button)
        else:self.manual_frame.pack_forget()
        self.pending=None;self.identity_confirmed.set(False)

    def pair_start(self):
        if self.busy:return
        if self.manual.get():
            try:port=int(self.port.get())
            except ValueError:self.status.set('Enter a numeric TLS port.');return
            host=self.host.get();self.busy=True
            def done(endpoint):self.busy=False;self.begin_pair(endpoint)
            self.work(lambda:inspect(host,port),done)
        elif self.selected_endpoint:self.begin_pair(self.selected_endpoint)
        else:self.status.set('Scan and choose a PC, or enter its address manually.')

    def begin_pair(self,endpoint):
        self.disconnect();self.agent=None;self.pending=Agent(endpoint);self.busy=True
        self.identity_confirmed.set(False)
        self.identity.set('COMPARE ON THE PC\n'+identity_code(endpoint.fingerprint))
        self.status.set('Showing a PIN on the target PC. Compare the PC identity on both screens.')
        pending=self.pending
        def done(_):self.busy=False;self.status.set('Confirm the PC identity matches, then enter its on-screen PIN.')
        self.work(pending.pair_start,done)

    def pair_finish(self):
        if self.busy:return
        if not self.pending:self.status.set('Start secure pairing first.');return
        if not self.identity_confirmed.get():self.status.set('Compare the PC identity on both screens, then confirm it matches before sending the PIN.');return
        pending=self.pending;pin=self.pin.get().strip();self.busy=True
        def finish():pending.pair_finish(pin);return pending.supported()
        def done(status):
            self.busy=False;self.pin.set('');self.agent=pending;self.pending=None
            if self.remember.get():
                try:self.store.save(self.agent.endpoint,self.agent.token)
                except ConnectError as error:self.status.set(str(error));return
            else:
                self.store.forget()
            self.connected(status)
        self.work(finish,done)

    def connected(self, status):
        self.status.set('Paired securely with '+self.agent.endpoint.host+'. Preview and control start only when you choose them.')
        self.refresh_launchers()

    def reconnect(self):
        if not self.agent:self.status.set('Pair with a PC first.');return
        agent=self.agent;self.work(agent.supported,self.connected)

    def release_control(self):
        if self.session:
            session=self.session;self.session=None;session.close()
        self.last_move=None;self.dragging.set(False)
        self.control_status.set('View only · control is off')

    def disconnect(self):
        self.generation+=1;self.release_control();self.preview.set(False)
        self.preview_busy=False;self.pending=None;self.busy=False;self.identity_confirmed.set(False)
        self.clear_preview('Disconnected\nDesktop images are cleared')
        self.status.set('Disconnected. Pairing remains available until forgotten.')

    def toggle_remember(self):
        try:
            if self.remember.get() and self.agent:self.store.save(self.agent.endpoint,self.agent.token)
            elif not self.remember.get():self.store.forget()
        except Exception:
            self.remember.set(False);self.status.set('Could not save or remove pairing. Check local storage permissions; no plaintext credential was written.')

    def forget(self):
        self.disconnect();self.agent=None;self.pin.set('')
        try:self.store.forget()
        except OSError:self.status.set('Could not remove the saved pairing. Check local storage permissions.');return
        self.remember.set(False)
        self.status.set('Local pairing forgotten. Other clients are unchanged; revoke the agent token on the PC to revoke all access.')

    def request_control(self):
        if not self.agent:self.status.set('Pair with a PC first.');return
        if self.session and not self.session.closed.is_set():
            if not self.session.held:self.session.control('request')
            return
        generation=self.generation
        session=Session(self.agent,lambda kind,value:self.post('session',(session,kind,value),generation))
        self.session=session
        self.control_status.set('Requesting input-only control…')
        self.pool.submit(self.session.start)

    def control(self, kind):
        if self.session:self.session.control(kind)

    def send(self, data):
        if not self.session or not self.session.input(data):
            self.control_status.set('Request control before sending input')

    def drag_toggle(self):
        if not self.session or not self.session.held:self.dragging.set(False);return
        self.send({'t':'mb','k':'l','v':1 if self.dragging.get() else 0})

    def click(self, key):
        self.send({'t':'mb','k':key,'v':1});self.send({'t':'mb','k':key,'v':0})

    def pad_down(self,e):
        self.trackpad.focus_set();self.last_move=(e.x,e.y);self.pad_origin=(e.x,e.y);self.pad_started=time.monotonic();self.last_move_time=self.pad_started

    def pad_motion(self,e):
        now=time.monotonic()
        if self.last_move and now-self.last_move_time>=.025:
            dx=e.x-self.last_move[0];dy=e.y-self.last_move[1]
            self.send({'t':'m','dx':dx*2,'dy':dy*2})
            self.last_move=(e.x,e.y);self.last_move_time=now

    def pad_up(self,e):
        if not self.dragging.get() and self.pad_origin and time.monotonic()-self.pad_started<.25 and abs(e.x-self.pad_origin[0])+abs(e.y-self.pad_origin[1])<5:self.click('l')
        self.last_move=self.pad_origin=None

    def pad_key(self,e):
        if e.keysym in ('Tab','ISO_Left_Tab'):
            return None  # retain local keyboard navigation; remote Tab has its own button
        keys={'Return':'enter','BackSpace':'backspace','Escape':'esc','Left':'left','Right':'right','Up':'up','Down':'down','Home':'home','End':'end'}
        if e.keysym in keys:self.send({'t':'k','key':keys[e.keysym]})
        elif e.char and e.char.isprintable() and not e.state & 0x4:self.send({'t':'kt','text':e.char})
        return 'break'

    def send_text(self):
        text=self.text.get()
        if text and len(text)<=4096 and self.session and self.session.held:
            self.send({'t':'kt','text':text});self.text.set('')
        else:self.status.set('Request control first. Text is limited to 4096 characters.')

    def focus_check(self):
        if not self.closing and not foreground.active(self.root):self.release_control()

    def focus_poll(self):
        if self.closing:return
        if self.session and not foreground.active(self.root):self.release_control()
        if self.root.state()=='iconic' and self.preview.get():
            self.preview.set(False);self.clear_preview('Preview paused while minimized')
        self.root.after(200,self.focus_poll)

    def refresh_launchers(self):
        if not self.agent:return
        agent=self.agent
        def done(data):
            values=data.get('launchers',[])
            self.launchers=[item for item in values[:2000] if isinstance(item,dict) and isinstance(item.get('id'),str) and isinstance(item.get('name',item.get('label')),str)] if isinstance(values,list) else []
            self.launch_choice['values']=[x.get('name',x.get('label'))[:100] for x in self.launchers]
            if self.launchers:self.launch_choice.current(0)
        self.work(lambda:agent.request('GET','/api/launchers'),done)

    def launch(self):
        index=self.launch_choice.current()
        if not self.agent or not 0<=index<len(self.launchers):return
        item=self.launchers[index]
        if not messagebox.askyesno('Launch on paired PC','Launch '+item.get('name',item.get('label'))+' on the paired PC?',parent=self.root):return
        agent=self.agent
        self.work(lambda:agent.request('POST','/api/launchers/'+quote(item['id'],safe=''),{}),lambda _:self.status.set('Launch requested on the paired PC.'))

    def clear_preview(self, message):
        self.image=self.photo=self.pointer=None;self.canvas.delete('all')
        self.canvas.create_text(24,35,text=message,anchor='nw',fill=theme.DIM,font=('Menlo' if os.name!='nt' else 'Consolas',12))

    def preview_changed(self):
        if not self.preview.get():self.clear_preview('Desktop preview is off')
        elif not self.agent:self.preview.set(False);self.status.set('Pair with a PC first.')

    def preview_tick(self):
        if not self.closing and self.preview.get() and self.agent and not self.preview_busy:
            self.preview_busy=True;agent=self.agent
            def fetch():
                try:
                    image=decode_frame(agent.request('GET','/api/screen/frame',binary=True))
                    info=agent.request('GET','/api/screen')
                    return image,info.get('pointer')
                except Exception:return None
            def done(frame):
                self.preview_busy=False
                if not self.preview.get():return
                if frame is None:self.clear_preview('Desktop unavailable · no stale image displayed');return
                self.image,self.pointer=frame;self.paint()
            self.work(fetch,done)
        if not self.closing:self.root.after(1000,self.preview_tick)

    def paint(self):
        if self.image is None:return
        image=self.image.copy();image.thumbnail((max(1,self.canvas.winfo_width()-4),max(1,self.canvas.winfo_height()-4)))
        self.photo=ImageTk.PhotoImage(image)
        self.canvas.delete('all');self.canvas.create_image(2,2,image=self.photo,anchor='nw')
        p=self.pointer
        if isinstance(p,dict) and all(type(p.get(k)) in (float,int) and 0<=p[k]<=1 for k in ('x','y')):
            x=2+p['x']*image.width;y=2+p['y']*image.height
            self.canvas.create_oval(x-5,y-5,x+5,y+5,fill=theme.GREEN,outline='black',width=2)

    def help(self):
        messagebox.showinfo('Couchside Computer Connect',
            'A free MIT-licensed desktop utility. Requires the matching Windows agent with input_only support.\n\n'
            'Pair: Scan for boxes, choose the PC, then Start secure pairing. Compare the PC identity shown on both screens, check PC identity matches, then enter the PC PIN. Discovery is not proof of identity. Never confirm a mismatch.\n\n'
            'If scan misses a VPN/VLAN box, enter its address manually. Its certificate identity still must match the target PC screen. Advanced verification: the full fp is available on the target at localhost:8787/api/tls/cert.\n\n'
            'View: enable Live preview. Snapshots are kept only in memory and cleared on disconnect. The green dot marks the reported cursor.\n\n'
            'Control: request consent from the current holder. Drag on the trackpad to move; tap to click. Use the text field or focus the trackpad to type. Changing apps or minimizing releases control.\n\n'
            'Windows can remember pairing with user-scoped DPAPI. Other platforms keep it in memory only. Forgetting locally does not revoke the PC-wide token.\n\n'
            'No cloud relay, audio/video stream, remote file transfer or screen recording. Do not port-forward the agent.\n\n'
            'Built with LLM assistance. Separate from the paid mobile app. No purchase or account required.',parent=self.root)

    def close(self):
        self.closing=True;self.disconnect();self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()


def main():
    if os.name=='nt':
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root=tk.Tk()
    if os.name=='nt':
        # Compact native desktop layout remains usable in a high-DPI RDP session.
        root.tk.call('tk','scaling',min(1.5,float(root.tk.call('tk','scaling'))))
    App(root);root.mainloop()
