"""Desktop rendering of Couchside's public brand, independently implemented.

Color values follow Midnight; assets are from the MIT brand/ directory, not
mobile components. Space Mono is bundled with its SIL OFL notice.
"""
import ctypes
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font as tkfont
from PIL import Image, ImageDraw, ImageTk

ASSETS=Path(__file__).resolve().parent/'assets'
BG='#0b1220';CARD='#141c2e';BORDER='#1e2942';INSET='#0e1526'
TEXT='#e5ecf8';DIM='#9ca6b9';FAINT='#7986a0';BLUE='#60a5fa';GREEN='#34d399'


def install(root):
    # FR_PRIVATE: available only to this process; no system font installation.
    if os.name=='nt':
        user=ctypes.WinDLL('gdi32')
        user.AddFontResourceExW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_void_p]
        user.AddFontResourceExW(str(ASSETS/'SpaceMono-Regular.ttf'),16,None)
    elif __import__('sys').platform=='darwin':
        try:
            cf=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            ct=ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
            cf.CFURLCreateFromFileSystemRepresentation.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_long,ctypes.c_bool]
            cf.CFURLCreateFromFileSystemRepresentation.restype=ctypes.c_void_p
            cf.CFRelease.argtypes=[ctypes.c_void_p]
            ct.CTFontManagerRegisterFontsForURL.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_void_p]
            ct.CTFontManagerRegisterFontsForURL.restype=ctypes.c_bool
            path=os.fsencode(ASSETS/'SpaceMono-Regular.ttf')
            url=cf.CFURLCreateFromFileSystemRepresentation(None,path,len(path),False)
            if url:
                ct.CTFontManagerRegisterFontsForURL(url,1,None)  # process scope
                cf.CFRelease(url)
        except Exception:
            pass  # Menlo fallback; never install a font system-wide
    available=set(tkfont.families(root))
    mono='Space Mono' if 'Space Mono' in available else ('Menlo' if 'Menlo' in available else 'Consolas')
    body='Segoe UI' if os.name=='nt' else 'Helvetica Neue'
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',background=CARD,foreground=TEXT,font=(body,10))
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background=CARD)
    style.configure('TLabel',background=CARD,foreground=TEXT)
    style.configure('Header.TLabel',background=BG,foreground=TEXT,font=(mono,18,'bold'))
    style.configure('Badge.TLabel',background=BG,foreground=GREEN,font=(mono,9))
    style.configure('Title.TLabel',background=CARD,foreground=TEXT,font=(mono,13,'bold'))
    style.configure('Section.TLabel',background=CARD,foreground=DIM,font=(mono,10,'bold'))
    style.configure('Muted.TLabel',background=CARD,foreground=DIM)
    style.configure('TEntry',fieldbackground=INSET,foreground=TEXT,insertcolor=TEXT,
                    bordercolor=BORDER,lightcolor=BORDER,darkcolor=BORDER,padding=7)
    style.map('TEntry',bordercolor=[('focus',BLUE)])
    style.configure('TCombobox',fieldbackground=INSET,background=CARD,foreground=TEXT,arrowcolor=DIM,padding=5)
    style.map('TCombobox',fieldbackground=[('readonly',INSET)],foreground=[('readonly',TEXT)])
    style.configure('TCheckbutton',background=CARD,foreground=DIM,font=(body,9),padding=3)
    style.map('TCheckbutton',background=[('active',CARD)],foreground=[('disabled',FAINT),('active',TEXT)])
    root.option_add('*TCombobox*Listbox.background',INSET)
    root.option_add('*TCombobox*Listbox.foreground',TEXT)
    root.option_add('*TCombobox*Listbox.selectBackground',BLUE)
    # Nine-sliced rounded images retain the corner radius as buttons stretch.
    root._button_images=[]
    for name,color,on,hover in [('Normal',CARD,TEXT,'#20304b'),('Accent',BLUE,BG,'#84baff')]:
        images=[]
        for fill,edge in [(color,BORDER),(hover,BLUE),(INSET,BORDER)]:
            image=Image.new('RGBA',(30,30),(0,0,0,0));draw=ImageDraw.Draw(image)
            draw.rounded_rectangle((0,0,29,29),radius=9,fill=fill,outline=edge,width=1)
            images.append(ImageTk.PhotoImage(image,master=root))
        root._button_images.extend(images)
        element='Couchside'+name+'.button'
        style.element_create(element,'image',images[0],('active',images[1]),('disabled',images[2]),border=8,sticky='nsew')
        target='TButton' if name=='Normal' else 'Accent.TButton'
        style.layout(target,[(element,{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
        style.configure(target,background=CARD,foreground=on,padding=(8,3),font=(body,10,'bold'),anchor='center')
        style.map(target,foreground=[('disabled',FAINT),('active',on)])
    return mono,body


class Card(tk.Frame):
    def __init__(self,parent,width=None):
        super().__init__(parent,bg=BG,width=width or 1)
        self.canvas=tk.Canvas(self,bg=BG,highlightthickness=0,bd=0)
        self.canvas.place(x=0,y=0,relwidth=1,relheight=1)
        self.content=ttk.Frame(self,style='Card.TFrame')
        self.content.place(x=14,y=14,relwidth=1,width=-28,relheight=1,height=-28)
        self.bind('<Configure>',self.paint)
    def paint(self,event):
        w,h=event.width,event.height;r=12
        self.canvas.delete('all')
        points=[r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        self.canvas.create_polygon(points,smooth=True,splinesteps=24,fill=CARD,outline=BORDER)
        self.canvas.create_line(18,1,w-18,1,fill='#2c4264')
