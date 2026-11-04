"""Actual Tk bindings emit bounded protocol frames; no OS input is injected."""
import sys,tkinter as tk,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'computer-connect'))
from computer_connect.ui import App

class MouseWidgetTest(unittest.TestCase):
    def test_click_move_scroll(self):
        root=tk.Tk()
        try:
            app=App(root);root.update()
            frames=[];app.send=frames.append
            pad=app.trackpad
            pad.event_generate('<ButtonPress-1>',x=20,y=20)
            pad.event_generate('<ButtonRelease-1>',x=20,y=20)
            self.assertEqual(frames,[{'t':'mb','k':'l','v':1},{'t':'mb','k':'l','v':0}])
            frames.clear()
            pad.event_generate('<ButtonPress-1>',x=20,y=20)
            app.last_move_time-=.03
            pad.event_generate('<B1-Motion>',x=30,y=25)
            pad.event_generate('<ButtonRelease-1>',x=30,y=25)
            self.assertEqual(frames,[{'t':'m','dx':20,'dy':10}])
            frames.clear();pad.event_generate('<Button-3>',x=20,y=20)
            pad.event_generate('<MouseWheel>',delta=120)
            pad.event_generate('<MouseWheel>',delta=-120)
            self.assertEqual(frames,[{'t':'mb','k':'r','v':1},{'t':'mb','k':'r','v':0},{'t':'mw','dy':1},{'t':'mw','dy':-1}])
        finally:
            app.close()

if __name__=='__main__':unittest.main()
