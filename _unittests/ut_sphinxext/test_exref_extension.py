"""
@brief      test log(time=4s)
@author     Xavier Dupre
"""
import sys
import os
import unittest
from docutils.parsers.rst import directives

from pyquickhelper.loghelper.flog import fLOG
from pyquickhelper.pycode import get_temp_folder
from pyquickhelper.helpgen import rst2html
from pyquickhelper.sphinxext import ExRef, ExRefList
from pyquickhelper.sphinxext.sphinx_exref_extension import exref_node, visit_exref_node, depart_exref_node


class TestExRefExtension(unittest.TestCase):

    def test_post_parse_exref(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        directives.register_directive("exref", ExRef)
        directives.register_directive("exreflist", ExRefList)

    def test_exref(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        from docutils import nodes as skip_

        content = """
                    test a directive
                    ================

                    before

                    .. exref::
                        :title: first todo
                        :tag: bug
                        :lid: id3

                        this code shoud appear___

                    after
                    """.replace("                    ", "")
        if sys.version_info[0] >= 3:
            content = content.replace('u"', '"')

        tives = [("exref", ExRef, exref_node,
                  visit_exref_node, depart_exref_node)]

        html = rst2html(content,
                        writer="custom", keep_warnings=True,
                        directives=tives, extlinks={'issue': ('http://%s', '_issue_')})

        temp = get_temp_folder(__file__, "temp_exref")
        with open(os.path.join(temp, "out_exref.html"), "w", encoding="utf8") as f:
            f.write(html)

        t1 = "this code shoud appear"
        if t1 not in html:
            raise Exception(html)

        t1 = "after"
        if t1 not in html:
            raise Exception(html)

        t1 = "first todo"
        if t1 not in html:
            raise Exception(html)

    def test_exreflist(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        from docutils import nodes as skip_

        content = """
                    test a directive
                    ================

                    before

                    .. exref::
                        :title: first todo
                        :tag: freg
                        :lid: id3

                        this code shoud appear___

                    middle

                    .. exreflist::
                        :tag: freg
                        :sort: title

                    after
                    """.replace("                    ", "")
        if sys.version_info[0] >= 3:
            content = content.replace('u"', '"')

        tives = [("exref", ExRef, exref_node,
                  visit_exref_node, depart_exref_node)]

        html = rst2html(content,
                        writer="custom", keep_warnings=True,
                        directives=tives)
        if "admonition-exref exref_node admonition" not in html:
            raise html

        temp = get_temp_folder(__file__, "temp_exreflist")
        with open(os.path.join(temp, "out_exref.html"), "w", encoding="utf8") as f:
            f.write(html)

        t1 = "this code shoud appear"
        if t1 not in html:
            raise Exception(html)

        t1 = "after"
        if t1 not in html:
            raise Exception(html)

        t1 = "first todo"
        if t1 not in html:
            raise Exception(html)

    def test_exreflist_rst(self):
        fLOG(
            __file__,
            self._testMethodName,
            OutputPrint=__name__ == "__main__")

        from docutils import nodes as skip_

        content = """
                    test a directive
                    ================

                    before

                    .. exref::
                        :title: first todo
                        :tag: freg
                        :lid: id3

                        this code shoud appear___

                    middle

                    .. exreflist::
                        :tag: freg
                        :sort: title

                    after
                    """.replace("                    ", "")
        if sys.version_info[0] >= 3:
            content = content.replace('u"', '"')

        tives = [("exref", ExRef, exref_node,
                  visit_exref_node, depart_exref_node)]

        rst = rst2html(content,
                       writer="rst", keep_warnings=True,
                       directives=tives)

        self.assertNotEmpty(rst)


if __name__ == "__main__":
    unittest.main()
