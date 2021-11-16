"""
Tkinter GUI progressbar decorator for iterators.

Usage:
>>> from tqdm.tk import trange, tqdm
>>> for i in trange(10):
...     ...
"""
from __future__ import absolute_import, division

import re
import sys
from warnings import warn

try:
    import tkinter
    import tkinter.ttk as ttk
except ImportError:
    import Tkinter as tkinter
    import ttk as ttk

from .std import TqdmExperimentalWarning, TqdmWarning
from .std import tqdm as std_tqdm
from .utils import _range

__author__ = {"github.com/": ["richardsheridan", "casperdcl"]}
__all__ = ['tqdm_tk', 'ttkrange', 'tqdm', 'trange']


def _tk_dispatching_helper():
    """determine if Tkinter mainloop is dispatching events"""
    codes = {tkinter.mainloop.__code__, tkinter.Misc.mainloop.__code__}
    for frame in sys._current_frames().values():
        while frame:
            if frame.f_code in codes:
                return True
            frame = frame.f_back
    return False


class TqdmWidget(ttk.Frame):
    def __init__(self, parent, tqdm, cancel_callback=None):
        super().__init__(parent, padding=5)
        self._tqdm = tqdm

        self._tk_n_var = tkinter.DoubleVar(self, value=0)
        self._tk_text_var = tkinter.StringVar(self)

        _tk_label = ttk.Label(self, textvariable=self._tk_text_var,
                              wraplength=600, anchor="center", justify="center")
        _tk_label.pack()

        self._tk_pbar = ttk.Progressbar(
            self, variable=self._tk_n_var, length=450)
        self._style = ttk.Style(self)
        self._style_name = "tqdm%s.Horizontal.TProgressbar" % self.generate_id()
        self._tk_pbar.configure(style=self._style_name)

        if self._tqdm.total is not None:
            self._tk_pbar.configure(maximum=self._tqdm.total)
        else:
            self._tk_pbar.configure(mode="indeterminate")

        self._tk_pbar.pack()

        if cancel_callback is not None:
            def _cancel():
                self._style.configure(self._style_name, background='#d8534e')
                cancel_callback()

            _tk_button = ttk.Button(self, text="Cancel", command=_cancel)
            _tk_button.pack()

    def generate_id(self):
        _id = id(self)

        # TODO - 1:1 map to unsigned int
        # Sure there's a better way to do this
        if _id >= 0:
            return str(2*_id)
        else:
            return str(1 - 2*_id)

    def display(self):
        self._tk_n_var.set(self._tqdm.n)
        d = self._tqdm.format_dict
        # remove {bar}
        d['bar_format'] = (d['bar_format'] or "{l_bar}<bar/>{r_bar}").replace(
            "{bar}", "<bar/>")
        msg = self._tqdm.format_meter(**d)
        if '<bar/>' in msg:
            msg = "".join(re.split(r'\|?<bar/>\|?', msg, 1))
        self._tk_text_var.set(msg)
        if self._tqdm.n == self._tqdm.total:
            self._style.configure(self._style_name, background='#5cb85c')

    def reset(self, total=None):
        if hasattr(self, '_tk_pbar'):
            if total is None:
                self._tk_pbar.configure(maximum=100, mode="indeterminate")
            else:
                self._tk_pbar.configure(maximum=total, mode="determinate")

    def close(self):
        pass


class TqdmWindowMixin:
    def __init__(self, tqdm, parent=None, cancel_callback=None, grab=False, desc=None):
        super().__init__(parent)
        self._tqdm = tqdm
        self.pbar_frame = TqdmWidget(self, tqdm, cancel_callback)

        self.protocol("WM_DELETE_WINDOW", cancel_callback)
        self.wm_title(desc)
        self.wm_attributes("-topmost", 1)
        self.after(0, lambda: self.wm_attributes("-topmost", 0))

        self.pbar_frame.pack()

        if grab:
            self.grab_set()

    def close(self):

        def _close():
            self.after('idle', self.destroy)
            if not self._tqdm._tk_dispatching:
                self.update()

        self.protocol("WM_DELETE_WINDOW", _close)

        # if leave is set but we are self-dispatching, the left window is
        # totally unresponsive unless the user manually dispatches
        if not self._tqdm.leave:
            _close()

        elif not self._tqdm._tk_dispatching:
            if self._tqdm._warn_leave:
                warn("leave flag ignored if not in tkinter mainloop",
                     TqdmWarning, stacklevel=2)
            _close()

    def display(self):
        self.pbar_frame.display()

    def reset(self, *args, **kwargs):
        self.pbar_frame.reset(*args, **kwargs)


class TqdmTk(TqdmWindowMixin, tkinter.Tk):
    pass


class TqdmToplevel(TqdmWindowMixin, tkinter.Toplevel):
    pass


class tqdm_tk(std_tqdm):  # pragma: no cover
    """
    Experimental Tkinter GUI version of tqdm!

    Note: Window interactivity suffers if `tqdm_tk` is not running within
    a Tkinter mainloop and values are generated infrequently. In this case,
    consider calling `tqdm_tk.refresh()` frequently in the Tk thread.
    """

    # TODO: @classmethod: write()?

    def __init__(self, *args, **kwargs):
        """
        This class accepts the following parameters *in addition* to
        the parameters accepted by `tqdm`.

        Parameters
        ----------
        grab  : bool, optional
            Grab the input across all windows of the process.
        tk_parent  : `tkinter.Wm`, optional
            Parent Tk window.
        cancel_callback  : Callable, optional
            Create a cancel button and set `cancel_callback` to be called
            when the cancel or window close button is clicked.
        """
        kwargs = kwargs.copy()
        kwargs['gui'] = True
        # convert disable = None to False
        kwargs['disable'] = bool(kwargs.get('disable', False))
        self._warn_leave = 'leave' in kwargs
        grab = kwargs.pop('grab', False)
        tk_parent = kwargs.pop('tk_parent', None)
        self._cancel_callback = kwargs.pop('cancel_callback', None)
        new_window = kwargs.pop('new_window', True)
        super(tqdm_tk, self).__init__(*args, **kwargs)

        if self.disable:
            return

        if tk_parent is None:  # Discover parent widget
            try:
                tk_parent = tkinter._default_root
            except AttributeError:
                raise AttributeError(
                    "`tk_parent` required when using `tkinter.NoDefaultRoot()`")
            if tk_parent is None:  # use new default root window as display
                self._tk_window = TqdmTk(self, grab=grab, cancel_callback=self.cancel)
            else:  # some other windows already exist
                self._tk_window = TqdmToplevel(self, grab=grab, cancel_callback=self.cancel)
        elif new_window:
            self._tk_window = TqdmToplevel(self, tk_parent, grab=grab, cancel_callback=self.cancel)
        else:
            self._tk_window = TqdmWidget(tk_parent, self, cancel_callback=self.cancel)
            self._tk_window.pack()

        warn("GUI is experimental/alpha", TqdmExperimentalWarning, stacklevel=2)
        self._tk_dispatching = _tk_dispatching_helper()

    def close(self):
        if self.disable:
            return

        self.disable = True

        with self.get_lock():
            self._instances.remove(self)

        self._tk_window.close()

    def cancel(self):
        """
        `cancel_callback()` followed by `close()`
        when close/cancel buttons clicked.
        """
        if self._cancel_callback is not None:
            self._cancel_callback()
        self.close()

    def clear(self, *_, **__):
        pass

    def display(self, *_, **__):
        def _display():
            self._tk_window.display()
        self._tk_window.after(1, _display)
        if not self._tk_dispatching:
            self._tk_window.update()

    def set_description(self, desc=None, refresh=True):
        self.set_description_str(desc, refresh)

    def set_description_str(self, desc=None, refresh=True):
        self.desc = desc
        if not self.disable:
            self._tk_window.wm_title(desc)
            if refresh and not self._tk_dispatching:
                self._tk_window.update()

    def reset(self, total=None):
        """
        Resets to 0 iterations for repeated use.

        Parameters
        ----------
        total  : int or float, optional. Total to use for the new bar.
        """
        self._tk_window.reset(total=total)
        super(tqdm_tk, self).reset(total=total)


def ttkrange(*args, **kwargs):
    """
    A shortcut for `tqdm.tk.tqdm(xrange(*args), **kwargs)`.
    On Python3+, `range` is used instead of `xrange`.
    """
    return tqdm_tk(_range(*args), **kwargs)


# Aliases
tqdm = tqdm_tk
trange = ttkrange
