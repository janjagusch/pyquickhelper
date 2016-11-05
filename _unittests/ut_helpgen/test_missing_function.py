"""
@brief      test log(time=8s)
@author     Xavier Dupre
"""

import sys
import os
import unittest
import warnings


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
from src.pyquickhelper.helpgen.utils_sphinx_config import ie_layout_html, NbImage, fix_ie_layout_html
from src.pyquickhelper.pycode import is_travis_or_appveyor


class TestMissingFunction(unittest.TestCase):

    def test_ie(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        if is_travis_or_appveyor() == "travis" or "anaconda" in sys.executable.lower() or sys.version_info[0] == 2 \
           or "yquickhelper_condavir" in sys.executable:
            warnings.warn(
                "skipping on travis and with anaconda or python 2.7: " + sys.executable)
            return

        if not ie_layout_html():
            fLOG("updating layout.html")
            r = fix_ie_layout_html()
            assert r

        try:
            assert ie_layout_html()
        except AttributeError:
            return

    def test_nb_image(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        r = NbImage("completion.png")
        assert r is not None


if __name__ == "__main__":
    unittest.main()
