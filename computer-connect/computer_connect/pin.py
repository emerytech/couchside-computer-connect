"""Six-digit pairing input with paste, arrow and Backspace navigation."""
import tkinter as tk
from tkinter import ttk


from .pin_rules import distribute


class PinEntry(ttk.Frame):
    def __init__(self,parent,variable,mono):
        super().__init__(parent,style='Card.TFrame')
        self.variable=variable
        self.values=[tk.StringVar() for _ in range(6)]
        self.entries=[];self.editing=False
        style=ttk.Style(parent)
        style.configure('Pin.TEntry',font=(mono,18),padding=(2,8))
        for i,value in enumerate(self.values):
            entry=ttk.Entry(self,textvariable=value,width=1,justify='center',style='Pin.TEntry',font=(mono,18))
            entry.grid(row=0,column=i,sticky='ew',padx=(0,10 if i==2 else 4 if i<5 else 0))
            self.columnconfigure(i,weight=1)
            entry.configure(validate='key',validatecommand=(self.register(lambda proposed,j=i:self.validate(j,proposed)),'%P'))
            entry.bind('<<Paste>>',lambda e,j=i:self.paste(j))
            entry.bind('<KeyPress>',lambda e,j=i:self.key(e,j))
            entry.bind('<FocusIn>',lambda e,j=i:self.entries[j].selection_range(0,'end'))
            entry.bind('<BackSpace>',lambda e,j=i:self.backspace(j))
            entry.bind('<Left>',lambda e,j=i:self.move(j-1))
            entry.bind('<Right>',lambda e,j=i:self.move(j+1))
            self.entries.append(entry)
        self.trace=variable.trace_add('write',self.external)

    def focus_set(self):
        self.entries[0].focus_set()

    def current(self):return [value.get() for value in self.values]

    def move(self,index):
        entry=self.entries[max(0,min(5,index))];entry.focus_set();entry.selection_range(0,'end')
        return 'break'

    def apply(self,values,focus):
        self.editing=True
        try:
            for value,char in zip(self.values,values):value.set(char)
            self.variable.set(''.join(values))
        finally:self.editing=False
        self.move(focus)

    def key(self,event,index):
        if event.char and event.char in '0123456789' and not event.state & 0xC:
            values,focus=distribute(self.current(),index,event.char)
            self.apply(values,focus)
            return 'break'
        return None

    def paste(self,index):
        # Clipboard is read only for this explicit paste gesture, never polled.
        try:values,focus=distribute(self.current(),index,self.clipboard_get())
        except (tk.TclError,ValueError):return 'break'
        self.apply(values,focus)
        return 'break'

    def validate(self,index,proposed):
        if self.editing:return True
        try:values,focus=distribute(self.current(),index,proposed)
        except ValueError:return False
        # Modifying textvariables during a Tk validation callback can disable
        # validation, so perform the accepted edit after this event completes.
        self.after_idle(lambda:self.apply(values,focus))
        return False

    def backspace(self,index):
        values=self.current()
        if not values[index] and index>0:index-=1
        values[index]='';self.apply(values,index)
        return 'break'

    def external(self,*_):
        if self.editing:return
        value=self.variable.get()
        self.editing=True
        try:
            for index,part in enumerate(self.values):part.set(value[index] if index<len(value) else '')
        finally:self.editing=False
