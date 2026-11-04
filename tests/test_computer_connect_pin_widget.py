#!/usr/bin/env python3
"""Actual Tk PIN widget edits, using synthetic data and a withdrawn test root."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'computer-connect'))


@unittest.skipUnless(sys.platform in ('win32','darwin'),'desktop Tk widget test')
class PinWidgetTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from computer_connect.pin import PinEntry
        self.root=tk.Tk();self.root.withdraw()
        self.value=tk.StringVar()
        self.widget=PinEntry(self.root,self.value,'Courier')
        self.widget.pack();self.root.update_idletasks()

    def tearDown(self):self.root.destroy()

    def test_digit_typing_advances_and_leading_zero_survives(self):
        with patch.object(self.widget,'move') as move:
            for i,char in enumerate('012345'):
                self.assertEqual(self.widget.key(SimpleNamespace(char=char,state=0),i),'break')
            self.assertEqual([call.args[0] for call in move.call_args_list],[1,2,3,4,5,5])
        self.assertEqual(self.value.get(),'012345')
        self.assertEqual(self.widget.current(),list('012345'))

    def test_full_paste_and_backspace_across_boxes(self):
        with patch.object(self.widget,'clipboard_get',return_value='987654'):
            self.widget.paste(3)
        self.assertEqual(self.value.get(),'987654')
        self.widget.backspace(5)
        self.assertEqual(self.widget.current(),list('98765')+[''])
        self.widget.backspace(5)
        self.assertEqual(self.widget.current(),list('9876')+['',''])
        self.value.set('');self.assertEqual(self.widget.current(),['']*6)

    def test_invalid_paste_and_native_validation_are_bounded(self):
        with patch.object(self.widget,'clipboard_get',return_value='not a code'):
            self.widget.paste(0)
        self.assertEqual(self.value.get(),'')
        self.assertFalse(self.widget.validate(0,'123456'))
        self.root.update_idletasks()
        self.assertEqual(self.value.get(),'123456')
        self.assertEqual(self.widget.current(),list('123456'))
        self.assertFalse(self.widget.validate(0,'x'))
        self.root.update_idletasks()
        self.assertEqual(self.value.get(),'123456')


if __name__=='__main__':unittest.main()
