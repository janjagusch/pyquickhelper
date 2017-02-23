"""
@brief      test log(time=1s)
"""
import os
import sys
import unittest
import warnings

if sys.version_info[0] == 2:
    from Tkinter import TclError
else:
    from tkinter import TclError

try:
    import src
except ImportError:
    path = os.path.normpath(
        os.path.abspath(
            os.path.join(
                os.path.split(__file__)[0],
                "..",
                "..")))
    if path not in sys.path:
        sys.path.append(path)
    import src

from src.pyquickhelper.loghelper.flog import fLOG
from src.pyquickhelper.pycode import fix_tkinter_issues_virtualenv
from src.pyquickhelper.funcwin import open_window_params, open_window_function
from src.pyquickhelper.funcwin.function_helper import get_function_list, has_unknown_parameters, private_get_function


def my_tst_function(a, b):
    """
    return a+b
    @param      a   (float) float
    @param      b   (float) float
    @return         a+b
    """
    return (a or 1) + (b or 1)


class TestWindows (unittest.TestCase):

    def test_open_window_params(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")
        fix_tkinter_issues_virtualenv(fLOG=fLOG)
        params = dict(p1="p1", p2=3)
        try:
            win = open_window_params(params, do_not_open=True)
        except TclError as e:
            warnings.warn("TclError" + str(e))
            return
        fLOG(type(win))
        assert isinstance(
            win,
            src.pyquickhelper.funcwin.frame_params.FrameParams)

    def test_open_window_function(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")
        fix_tkinter_issues_virtualenv(fLOG=fLOG)
        func = my_tst_function
        try:
            win = open_window_function(func, do_not_open=True)
        except TclError as e:
            warnings.warn("TclError" + str(e))
            return
        fLOG(type(win))
        assert isinstance(
            win,
            src.pyquickhelper.funcwin.frame_function.FrameFunction)
        win.refresh()
        win.update()
        win.run_function(0, 1)

    def test_get_function_list(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")
        fix_tkinter_issues_virtualenv(fLOG=fLOG)
        funcs = get_function_list(src.pyquickhelper)
        assert isinstance(funcs, dict)
        assert len(funcs) > 0
        if "load_ipython_extension" not in funcs:
            raise Exception("\n".join(sorted(funcs.keys())))
        r = has_unknown_parameters(funcs["load_ipython_extension"])
        assert not r
        f = private_get_function("os.listdir")
        fLOG("**", f)


if __name__ == "__main__":
    unittest.main()
