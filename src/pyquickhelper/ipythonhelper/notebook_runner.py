"""
@file
@brief Modified version of `runipy.notebook_runner <https://github.com/paulgb/runipy/blob/master/runipy/notebook_runner.py>`_.
"""

import base64
import os
import re
import time
import sys
import platform
import warnings
from queue import Empty
from time import sleep
from collections import Counter


try:
    from nbformat import NotebookNode
    from nbformat import writes
except ImportError:
    from IPython.nbformat.v3 import NotebookNode
    from IPython.nbformat import writes
from ..loghelper.flog import noLOG

if sys.version_info[0] == 2:
    from codecs import open
    from StringIO import StringIO
    BytesIO = StringIO
else:
    from io import StringIO, BytesIO


class NotebookError(Exception):

    """
    custom exception
    """
    pass


class NotebookRunner(object):

    """
    The kernel communicates with mime-types while the notebook
    uses short labels for different cell types. We'll use this to
    map from kernel types to notebook format types.

    This classes executes a notebook end to end.

    .. index:: kernel, notebook

    The class can use different kernels. The next links gives more
    information on how to create or test a kernel:

    * `jupyter_kernel_test <https://github.com/jupyter/jupyter_kernel_test>`_
    * `simple_kernel <https://github.com/dsblank/simple_kernel>`_

    .. faqref::
        :title: Do I need to shutdown the kernel after running a notebook?

        .. index:: travis

        If the class is instantiated with *kernel=True*, a kernel will
        be started. It must be shutdown otherwise the program might
        be waiting for it for ever. That is one of the reasons why the
        travis build does not complete. The build finished but cannot temrinate
        until all kernels are shutdown.
    """

    #. available output types
    MIME_MAP = {
        'image/jpeg': 'jpeg',
        'image/png': 'png',
        'image/gif': 'gif',
        'text/plain': 'text',
        'text/html': 'html',
        'text/latex': 'latex',
        'application/javascript': 'html',
        'image/svg+xml': 'svg',
    }

    def __init__(self, nb, profile_dir=None, working_dir=None,
                 comment="", fLOG=noLOG, theNotebook=None, code_init=None,
                 kernel_name="python", log_level="30", extended_args=None,
                 kernel=False, filename=None, replacements=None):
        """
        constuctor

        @param      nb              notebook as JSON
        @param      profile_dir     profile directory
        @param      working_dir     working directory
        @param      comment         additional information added to error message
        @param      theNotebook     if not None, populate the variable *theNotebook* with this value in the notebook
        @param      code_init       to initialize the notebook with a python code as if it was a cell
        @param      fLOG            logging function
        @param      log_level       Choices: (0, 10, 20, 30=default, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
        @param      kernel_name     kernel name, it can be None
        @param      extended_args   others arguments to pass to the command line ('--KernelManager.autorestar=True' for example),
                                    see :ref:`l-ipython_notebook_args` for a full list
        @param      kernel          *kernel* is True by default, the notebook can be run, if False,
                                    the notebook can be read but not run
        @param      filename        to add the notebook file if there is one in error messages
        @param      replacements    replacements to make in every cell before running it,
                                    dictionary ``{ string: string }``

        .. versionchanged:: 1.4
            Parameter *replacements* was added.
        """
        if kernel:
            try:
                from jupyter_client import KernelManager
            except ImportError:
                from ipykernel import KernelManager
            self.km = KernelManager(
                kernel_name=kernel_name) if kernel_name is not None else KernelManager()
        else:
            self.km = None
        self.fLOG = fLOG
        self.theNotebook = theNotebook
        self.code_init = code_init
        self._filename = filename if filename is not None else "memory"
        self.replacements = replacements
        self.init_args = dict(profile_dir=profile_dir, working_dir=working_dir,
                              comment=comment, fLOG=fLOG, theNotebook=theNotebook, code_init=code_init,
                              kernel_name="python", log_level="30", extended_args=None,
                              kernel=kernel, filename=filename, replacements=replacements)
        args = []

        if profile_dir:
            args.append('--profile-dir=%s' % os.path.abspath(profile_dir))
        if log_level:
            args.append('--log-level=%s' % log_level)

        if extended_args is not None and len(extended_args) > 0:
            for opt in extended_args:
                if not opt.startswith("--"):
                    raise SyntaxError(
                        "every option should start with '--': " + opt)
                if "=" not in opt:
                    raise SyntaxError(
                        "every option should be assigned a value: " + opt)
                args.append(opt)

        if kernel:
            cwd = os.getcwd()

            if working_dir:
                os.chdir(working_dir)

            if self.km is not None:
                if sys.version_info[0] == 2 and args is not None:
                    # I did not find a way to make it work
                    args = None
                    warnings.warn(
                        "args is not None: {0}, unable to use it in Python 2.7".format(args))
                    self.km.start_kernel()
                else:
                    try:
                        self.km.start_kernel(extra_arguments=args)
                    except Exception as e:
                        raise Exception(
                            "Failure with args: {0}\nand error:\n{1}".format(args, str(e))) from e

                if platform.system() == 'Darwin':
                    # see http://www.pypedia.com/index.php/notebook_runner
                    # There is sometimes a race condition where the first
                    # execute command hits the kernel before it's ready.
                    # It appears to happen only on Darwin (Mac OS) and an
                    # easy (but clumsy) way to mitigate it is to sleep
                    # for a second.
                    sleep(1)

            os.chdir(cwd)

            self.kc = self.km.client()
            self.kc.start_channels(stdin=False)
            # if it does not work, it probably means IPython < 3
            self.kc.wait_for_ready()
        else:
            self.km = None
            self.kc = None
        self.nb = nb
        self.comment = comment

    def to_json(self, filename=None, encoding="utf8"):
        """
        convert the notebook into json

        @param      filename        filename or stream
        @param      encoding        encoding
        @return                     Json string if filename is None, None otherwise

        .. versionchanged:: 1.4
            The function now returns the json string if filename is None.
        """
        if isinstance(filename, str  # unicode#
                      ):
            with open(filename, "w", encoding=encoding) as payload:
                self.to_json(payload)
        elif filename is None:
            st = StringIO()
            st.write(writes(self.nb))
            return st.getvalue()
        else:
            filename.write(writes(self.nb))

    @staticmethod
    def read_json(js, profile_dir=None, encoding="utf8",
                  working_dir=None, comment="", fLOG=noLOG, code_init=None,
                  kernel_name="python", log_level="30", extended_args=None,
                  kernel=False, replacements=None):
        """
        read a notebook from a JSON stream or string

        @param      js              string or stream
        @param      profile_dir     profile directory
        @param      encoding        encoding for the notebooks
        @param      kernel          to start a kernel or not when reading the notebook (to execute it)
        @param      working_dir     working directory
        @param      comment         additional information added to error message
        @param      code_init       to initialize the notebook with a python code as if it was a cell
        @param      fLOG            logging function
        @param      log_level       Choices: (0, 10, 20, 30=default, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
        @param      kernel_name     kernel name, it can be None
        @param      extended_args   others arguments to pass to the command line ('--KernelManager.autorestar=True' for example),
                                    see :ref:`l-ipython_notebook_args` for a full list
        @param      kernel          *kernel* is True by default, the notebook can be run, if False,
                                    the notebook can be read but not run
        @param      replacements    replacements to make in every cell before running it,
                                    dictionary ``{ string: string }``
        @return                     instance of @see cl NotebookRunner

        .. versionchanged:: 1.5
            Add constructor parameters.
        """
        if isinstance(js, str  # unicode#
                      ):
            st = StringIO(js)
        else:
            st = js
        from .notebook_helper import read_nb
        return read_nb(st, encoding=encoding, kernel=kernel,
                       profile_dir=profile_dir, working_dir=working_dir,
                       comment=comment, fLOG=fLOG, code_init=code_init,
                       kernel_name="python", log_level="30", extended_args=None,
                       replacements=replacements)

    def copy(self):
        """
        copy the notebook (just the content)

        @return         instance of @see cl NotebookRunner

        .. versionadded:: 1.1

        .. versionchanged:: 1.5
            Add constructor parameters.
        """
        st = StringIO()
        self.to_json(st)
        args = self.init_args.copy()
        for name in ["theNotebook", "filename"]:
            if name in args:
                del args[name]
        return NotebookRunner.read_json(st.getvalue(), **args)

    def __add__(self, nb):
        """
        merges two notebooks together, returns a new none

        @param      nb      notebook
        @return             new notebook
        """
        c = self.copy()
        c.merge_notebook(nb)
        return c

    def shutdown_kernel(self):
        """
        shut down kernel
        """
        self.fLOG('-- shutdown kernel')
        if self.kc is None:
            raise ValueError(
                "No kernel was started, specify kernel=True when initializing the instance.")
        self.kc.stop_channels()
        self.km.shutdown_kernel(now=True)

    def clean_code(self, code):
        """
        clean the code before running it, the function comment out
        instruction such as ``show()``

        @param      code        code (string)
        @return                 cleaned code

        .. versionchanged:: 1.4
            Do replacements.
        """
        has_bokeh = "bokeh." in code or "from bokeh" in code or "import bokeh" in code
        if code is None:
            return code
        else:
            lines = [_.strip("\n\r").rstrip(" \t") for _ in code.split("\n")]
            res = []
            show_is_last = False
            for line in lines:
                if line.replace(" ", "") == "show()":
                    line = line.replace("show", "#show")
                    show_is_last = True
                elif has_bokeh and line.replace(" ", "") == "output_notebook()":
                    line = line.replace("output_notebook", "#output_notebook")
                else:
                    show_is_last = False
                if self.replacements is not None:
                    for k, v in self.replacements.items():
                        line = line.replace(k, v)
                res.append(line)
                if show_is_last:
                    res.append('"nothing to show"')
            return "\n".join(res)

    @staticmethod
    def get_cell_code(cell):
        """
        return the code of a cell

        @param      cell        a cell or a string
        @return                 boolean (=iscell), string
        """
        if isinstance(cell, str  # unicode#
                      ):
            iscell = False
            return iscell, cell
        else:
            iscell = True
            try:
                return iscell, cell.source
            except AttributeError:
                return iscell, cell.input

    def run_cell(self, index_cell, cell, clean_function=None):
        '''
        Run a notebook cell and update the output of that cell in-place.

        @param      index_cell          index of the cell
        @param      cell                cell to execute
        @param      clean_function      cleaning function to apply to the code before running it
        @return                         output of the cell
        '''
        iscell, codei = NotebookRunner.get_cell_code(cell)

        self.fLOG('-- running cell:\n%s\n' % codei)

        code = self.clean_code(codei)
        if clean_function is not None:
            code = clean_function(code)
        if len(code) == 0:
            return ""
        if self.kc is None:
            raise ValueError(
                "No kernel was started, specify kernel=True when initializing the instance.")
        self.kc.execute(code)

        reply = self.kc.get_shell_msg()
        reason = None
        try:
            status = reply['content']['status']
        except KeyError:
            status = 'error'
            reason = "no status key in reply['content']"

        if status == 'error':
            ansi_escape = re.compile(r'\x1b[^m]*m')
            try:
                tr = [ansi_escape.sub('', _)
                      for _ in reply['content']['traceback']]
            except KeyError:
                tr = ["No traceback, available keys in reply['content']"] + \
                    [_ for _ in reply['content']]
            traceback_text = '\n'.join(tr)
            self.fLOG("ERR:\n", traceback_text)
        else:
            traceback_text = ''
            self.fLOG('-- cell returned')

        outs = list()
        nbissue = 0
        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
                if msg['msg_type'] == 'status':
                    if msg['content']['execution_state'] == 'idle':
                        break
            except Empty:
                # execution state should return to idle before the queue becomes empty,
                # if it doesn't, something bad has happened
                status = "error"
                reason = "exception Empty was raised"
                nbissue += 1
                if nbissue > 10:
                    # the notebook is empty
                    return ""
                else:
                    continue

            content = msg['content']
            msg_type = msg['msg_type']

            # IPython 3.0.0-dev writes pyerr/pyout in the notebook format but uses
            # error/execute_result in the message spec. This does the translation
            # needed for tests to pass with IPython 3.0.0-dev
            notebook3_format_conversions = {
                'error': 'pyerr',
                'execute_result': 'pyout'
            }
            msg_type = notebook3_format_conversions.get(msg_type, msg_type)

            out = NotebookNode(output_type=msg_type)

            if 'execution_count' in content:
                if iscell:
                    cell['prompt_number'] = content['execution_count']
                out.prompt_number = content['execution_count']

            if msg_type in ('status', 'pyin', 'execute_input'):
                continue

            elif msg_type == 'stream':
                out.stream = content['name']
                # in msgspec 5, this is name, text
                # in msgspec 4, this is name, data
                if 'text' in content:
                    out.text = content['text']
                else:
                    out.data = content['data']

            elif msg_type in ('display_data', 'pyout'):
                out.data = content['data']

            elif msg_type == 'pyerr':
                out.ename = content['ename']
                out.evalue = content['evalue']
                out.traceback = content['traceback']

            elif msg_type == 'clear_output':
                outs = list()
                continue

            elif msg_type == 'comm_open' or msg_type == 'comm_msg':
                # widgets in a notebook
                out.data = content["data"]
                out.comm_id = content["comm_id"]

            else:
                dcontent = "\n".join("{0}={1}".format(k, v)
                                     for k, v in sorted(content.items()))
                raise NotImplementedError(
                    'unhandled iopub message: %s' % msg_type + "\nCONTENT:\n" + dcontent)

            outs.append(out)

        if iscell:
            cell['outputs'] = outs

        raw = []
        for _ in outs:
            try:
                t = _.data
            except AttributeError:
                continue

            # see MIMEMAP to see the available output type
            for k, v in t.items():
                if k.startswith("text"):
                    raw.append(v)

        sraw = "\n".join(raw)
        self.fLOG(sraw)

        def reply2string(reply):
            sreply = []
            for k, v in sorted(reply.items()):
                if isinstance(v, dict):
                    temp = []
                    for _, __ in sorted(v.items()):
                        temp.append("    [{0}]={1}".format(_, str(__)))
                    v = "\n".join(temp)
                    sreply.append("reply['{0}']=dict\n{1}".format(k, v))
                else:
                    sreply.append("reply['{0}']={1}".format(k, str(v)))
            sreply = "\n".join(sreply)
            return sreply

        if status == 'error':
            sreply = reply2string(reply)
            if len(code) < 5:
                scode = [code]
            else:
                scode = ""
            mes = "FILENAME\n{10}:1:1\n{7}\nCELL status={8}, reason={9} -- {4} length={5} -- {6}:\n-----------------\n{0}" + \
                  "\n-----------------\nTRACE:\n{1}\nRAW:\n{2}REPLY:\n{3}"
            raise NotebookError(mes.format(
                code, traceback_text, sraw, sreply, index_cell, len(
                    code), scode, self.comment, status, reason,
                self._filename))
        return outs

    def iter_code_cells(self):
        '''
        Iterate over the notebook cells containing code.
        '''
        for cell in self.iter_cells():
            if cell.cell_type == 'code':
                yield cell

    def iter_cells(self):
        '''
        Iterate over the notebook cells.
        '''
        if hasattr(self.nb, "worksheets"):
            for ws in self.nb.worksheets:
                for cell in ws.cells:
                    yield cell
        else:
            for cell in self.nb.cells:
                yield cell

    def first_cell(self):
        """
        Returns the first cell.
        """
        for cell in self.iter_cells():
            return cell

    def _cell_container(self):
        """
        returns a cells container, it may change according to the format

        @return     cell container
        """
        if hasattr(self.nb, "worksheets"):
            last = None
            for ws in self.nb.worksheets:
                last = ws
            if last is None:
                raise NotebookError("no cell container")
            return last.cells
        else:
            return self.nb.cells

    def __len__(self):
        """
        return the number of cells, it iterates on cells
        to get this information and does cache the information

        @return         int

        .. versionadded:: 1.1
        """
        return sum(1 for _ in self.iter_cells())

    def cell_type(self, cell):
        """
        returns the cell type

        @param      cell        from @see me iter_cells
        @return                 type
        """
        return cell.cell_type

    def cell_metadata(self, cell):
        """
        returns the cell metadata

        @param      cell        cell
        @return                 metadata
        """
        return cell.metadata

    def _check_thumbnail_tuple(self, b):
        """
        checks types for a thumbnail

        @param      b       tuple   image, format
        @return             b

        The function raises an exception if the type is incorrect.
        """
        if not isinstance(b, tuple):
            raise TypeError("tuple expected, not {0}".format(type(b)))
        if len(b) != 2:
            raise TypeError(
                "tuple expected of lengh 2, not {0}".format(len(b)))
        if b[1] == "svg":
            if not isinstance(b[0], str):
                raise TypeError(
                    "str expected for svg, not {0}".format(type(b[0])))
        else:
            if not isinstance(b[0], bytes):
                raise TypeError(
                    "bytes expected for images, not {0}".format(type(b[0])))
        return b

    def create_picture_from(self, text, format, asbytes=True, context=None):
        """
        Creates a picture from text.

        @param      text        the text
        @param      format      text, json, ...
        @param      context     (str) indication on the content of text (error, ...)
        @param      asbytes     results as bytes or as an image
        @return                 tuple (picture, format) or PIL.Image (if asbytes is False)

        The picture will be bytes, the format png, bmp...
        The size of the picture will depend on the text.
        The longer, the bigger. The method relies on matplotlib
        and then convert the image into a PIL image.

        HTML could be rendered with QWebPage from PyQt (not implemented).
        """
        if not isinstance(text, (str, bytes)):
            text = str(text)
            if "\n" not in text:
                rows = []
                for i in range(0, len(text), 20):
                    end = min(i + 20, len(text))
                    rows.append(text[i:end])
                text = "\n".join(text)
        if len(text) > 200:
            text = text[:200]
        size = len(text) // 10
        figsize = (3 + size, 3 + size)
        lines = text.replace("\t", " ").replace("\r", "").split("\n")

        import matplotlib.pyplot as plt
        from matplotlib.textpath import TextPath
        from matplotlib.font_manager import FontProperties
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        fp = FontProperties(size=200)

        dx = 0
        dy = 0
        for i, line in enumerate(lines):
            if len(line.strip()) > 0:
                ax.text(0, -dy, line, fontproperties=fp, va='top')
                tp = TextPath((0, -dy), line, prop=fp)
                bb = tp.get_extents()
                dy += bb.height
                dx = max(dx, bb.width)

        ratio = abs(dx) / max(abs(dy), 1)
        ratio = max(min(ratio, 3), 1)
        fig.set_size_inches(int((1 + size) * ratio), 1 + size)
        ax.set_xlim([0, dx])
        ax.set_ylim([-dy, 0])
        ax.set_axis_off()
        sio = BytesIO()
        fig.savefig(sio, format="png")

        if asbytes:
            b = sio.getvalue(), "png"
            self._check_thumbnail_tuple(b)

            try:
                from PIL import Image
            except ImportError:
                import Image
            img = Image.open(sio)
            img.save("c:\\temp\\i{0}.png".format(id(img)))

            return b
        else:
            try:
                from PIL import Image
            except ImportError:
                import Image
            img = Image.open(sio)
            img.save("c:\\temp\\i{0}.png".format(id(img)))
            return img

    def cell_image(self, cell, image_from_text=False):
        """
        returns the cell image or None if not found

        @param      cell            cell to examine
        @param      image_from_text produce an image even if it is not one
        @return                     None for no image or a list of tuple (image as bytes, extension)
                                    for each output of the cell
        """
        kind = self.cell_type(cell)
        if kind != "code":
            return None
        results = []
        for output in cell.outputs:
            if output["output_type"] in {"execute_result", "display_data"}:
                data = output["data"]
                for k, v in data.items():
                    if k == "text/plain":
                        if image_from_text:
                            b = self.create_picture_from(
                                v, "text", context=output["output_type"])
                            results.append(b)
                    elif k == "application/javascript":
                        if image_from_text:
                            b = self.create_picture_from(v, "js")
                            results.append(b)
                    elif k == "application/json":
                        if image_from_text:
                            b = self.create_picture_from(v, "json")
                            results.append(b)
                    elif k == "image/svg+xml":
                        if not isinstance(v, str):
                            raise TypeError(
                                "This should be str not '{0}' (=SVG).".format(type(v)))
                        results.append((v, "svg"))
                    elif k == "text/html":
                        if image_from_text:
                            b = self.create_picture_from(v, "html")
                            results.append(b)
                    elif k == "text/latex":
                        if image_from_text:
                            b = self.create_picture_from(v, "latex")
                            results.append(b)
                    elif k in {"image/png", "image/jpg", "image/jpeg", "image/gif"}:
                        if not isinstance(v, bytes):
                            v = base64.b64decode(v)
                        if not isinstance(v, bytes):
                            raise TypeError(
                                "This should be bytes not '{0}' (=IMG:{1}).".format(type(v), k))
                        results.append((v, k.split("/")[-1]))
                    else:
                        raise NotImplementedError("cell type: {0}\nk={1}\nv={2}\nCELL:\n{3}".format(kind,
                                                                                                    k, v, cell))
            elif output["output_type"] == "error":
                vl = output["traceback"]
                if image_from_text:
                    for v in vl:
                        b = self.create_picture_from(
                            v, "text", context="error")
                        results.append(b)
            elif output["output_type"] == "stream":
                v = output["text"]
                if image_from_text:
                    b = self.create_picture_from(v, "text")
                    results.append(b)
            else:
                raise NotImplementedError("cell type: {0}\noutput type: {1}\nOUT:\n{2}\nCELL:\n{3}"
                                          .format(kind, output["output_type"], output, cell))
        if len(results) > 0:
            res = self._merge_images(results)
            self._check_thumbnail_tuple(res)
            return res
        else:
            return None

    def cell_height(self, cell):
        """
        approximate the height of a cell by its number of lines it contains

        @param      cell        cell
        @return                 number of cell
        """
        kind = self.cell_type(cell)
        if kind == "markdown":
            content = cell.source
            lines = content.split("\n")
            nbs = sum(1 + len(line) // 80 for line in lines)
            return nbs
        elif kind == "raw":
            content = cell.source
            lines = content.split("\n")
            nbs = sum(1 + len(line) // 80 for line in lines)
            return nbs
        elif kind == "code":
            content = cell.source
            lines = content.split("\n")
            nbl = len(lines)

            for output in cell.outputs:
                if output["output_type"] == "execute_result" or \
                        output["output_type"] == "display_data":
                    data = output["data"]
                    for k, v in data.items():
                        if k == "text/plain":
                            nbl += len(v.split("\n"))
                        elif k == "application/javascript":
                            # rough estimation
                            nbl += len(v.split("\n")) // 2
                        elif k == "application/json":
                            # rough estimation
                            try:
                                nbl += len(v.split("{"))
                            except AttributeError:
                                nbl += len(v) // 5 + 1
                        elif k == "image/svg+xml":
                            nbl += len(v) // 5
                        elif k == "text/html":
                            nbl += len(v.split("\n"))
                        elif k == "text/latex":
                            nbl += len(v.split("\\\\")) * 2
                        elif k in {"image/png", "image/jpg", "image/jpeg", "image/gif"}:
                            nbl += len(v) // 50
                        else:
                            raise NotImplementedError("cell type: {0}\nk={1}\nv={2}\nCELL:\n{3}".format(kind,
                                                                                                        k, v, cell))
                elif output["output_type"] == "stream":
                    v = output["text"]
                    nbl += len(v.split("\n"))
                elif output["output_type"] == "error":
                    v = output["traceback"]
                    nbl += len(v)
                else:
                    raise NotImplementedError("cell type: {0}\noutput type: {1}\nOUT:\n{2}\nCELL:\n{3}"
                                              .format(kind, output["output_type"], output, cell))

            return nbl

        else:
            raise NotImplementedError(
                "cell type: {0}\nCELL:\n{1}".format(kind, cell))

    def add_tag_slide(self, max_nb_cell=4, max_nb_line=25):
        """
        tries to add tags for a slide show when they are too few

        @param      max_nb_cell     maximum number of cells within a slide
        @param      max_nb_line     maximum number of lines within a slide
        @return                     list of modified cells { #slide: (kind, reason, cell) }
        """
        res = {}
        nbline = 0
        nbcell = 0
        for i, cell in enumerate(self.iter_cells()):
            meta = cell.metadata
            if "slideshow" in meta:
                st = meta["slideshow"]["slide_type"]
                if st in ["slide", "subslide"]:
                    nbline = 0
                    nbcell = 0
            else:
                if cell.cell_type == "markdown":
                    content = cell.source
                    if content.startswith("# ") or \
                       content.startswith("## ") or \
                       content.startswith("### "):
                        meta["slideshow"] = {'slide_type': 'slide'}
                        nbline = 0
                        nbcell = 0
                        res[i] = ("slide", "section", cell)

            dh = self.cell_height(cell)
            dc = 1
            new_nbline = nbline + dh
            new_cell = dc + nbcell
            if "slideshow" not in meta:
                if new_cell > max_nb_cell or \
                   new_nbline > max_nb_line:
                    res[i] = (
                        "subslide", "{0}-{1} <-> {2}-{3}".format(nbcell, nbline, dc, dh), cell)
                    nbline = 0
                    nbcell = 0
                    meta["slideshow"] = {'slide_type': 'subslide'}

            nbline += dh
            nbcell += dc

        return res

    def run_notebook(self,
                     skip_exceptions=False,
                     progress_callback=None,
                     additional_path=None,
                     valid=None,
                     clean_function=None):
        '''
        Run all the cells of a notebook in order and update
        the outputs in-place.

        If ``skip_exceptions`` is set, then if exceptions occur in a cell, the
        subsequent cells are run (by default, the notebook execution stops).

        @param      skip_exceptions     skip exception
        @param      progress_callback   call back function
        @param      additional_path     additional paths (as a list or None if none)
        @param      valid               if not None, valid is a function which returns whether
                                        or not the cell should be executed or not, if the function
                                        returns None, the execution of the notebooks and skip the execution
                                        of the other cells
        @param      clean_function      function which cleans a cell's code before executing it (None for None)
        @return                         dictionary with statistics

        .. versionchanged:: 1.1
            The function adds the local variable ``theNotebook`` with
            the absolute file name of the notebook.

        .. versionchanged:: 1.4
            Function *valid* can now return None to stop the execution of the notebook
            before this cell.
        '''
        # additional path
        if additional_path is not None:
            if not isinstance(additional_path, list):
                raise TypeError(
                    "additional_path should be a list not: " + str(additional_path))
            code = ["import sys"]
            for p in additional_path:
                code.append("sys.path.append(r'{0}')".format(p))
            cell = "\n".join(code)
            self.run_cell(-1, cell)

        # we add local variable theNotebook
        if self.theNotebook is not None:
            cell = "theNotebook = r'''{0}'''".format(self.theNotebook)
            self.run_cell(-1, cell)

        # initialisation with a code not inside the notebook
        if self.code_init is not None:
            self.run_cell(-1, self.code_init)

        # execution of the notebook
        nbcell = 0
        nbrun = 0
        nbnerr = 0
        cl = time.clock()
        for i, cell in enumerate(self.iter_code_cells()):
            nbcell += 1
            iscell, codei = NotebookRunner.get_cell_code(cell)
            if valid is not None:
                r = valid(codei)
                if r is None:
                    break
                elif not r:
                    continue
            try:
                nbrun += 1
                self.run_cell(i, cell, clean_function=clean_function)
                nbnerr += 1
            except Empty as er:
                raise Exception(
                    "{0}\nissue when executing:\n{1}".format(self.comment, codei)) from er
            except NotebookError as e:
                if not skip_exceptions:
                    raise
                else:
                    raise Exception(
                        "issue when executing:\n{0}".format(codei)) from e
            if progress_callback:
                progress_callback(i)
        etime = time.clock() - cl
        return dict(nbcell=nbcell, nbrun=nbrun, nbvalid=nbnerr, time=etime)

    def count_code_cells(self):
        '''
        @return the number of code cells in the notebook

        .. versionadded:: 1.1
        '''
        return sum(1 for _ in self.iter_code_cells())

    def merge_notebook(self, nb):
        """
        append notebook *nb* to this one

        @param      nb      notebook or list of notebook (@see cl NotebookRunner)
        @return             number of added cells

        .. faqref::
            :title: How to merge notebook?

            The following code merges two notebooks into the first one
            and stores the result unto a file.

            @code
            from pyquickhelper.ipythonhelper import read_nb
            nb1 = read_nb("<file1>", kernel=False)
            nb2 = read_nb("<file2>", kernel=False)
            nb1.merge_notebook(nb2)
            nb1.to_json(outfile)
            @endcode

        .. versionadded:: 1.1
        """
        if isinstance(nb, list):
            s = 0
            for n in nb:
                s += self.merge_notebook(n)
            return s
        else:
            last = self._cell_container()
            s = 0
            for cell in nb.iter_cells():
                last.append(cell)
                s += 1
            return s

    def get_description(self):
        """
        Get summary and description of this notebook.
        We expect the first cell to contain a title and a description
        of its content.

        @return             header, description

        .. versionadded:: 1.5
        """
        def split_header(s, get_header=True):
            s = s.lstrip().rstrip()
            parts = s.splitlines()
            if parts[0].startswith('#'):
                if get_header:
                    header = re.sub('#+\s*', '', parts.pop(0))
                    if not parts:
                        return header, ''
                else:
                    header = ''
                rest = '\n'.join(parts).lstrip().split('\n\n')
                desc = rest[0].replace('\n', ' ')
                return header, desc
            else:
                if get_header:
                    if parts[0].startswith(('=', '-')):
                        parts = parts[1:]
                    header = parts.pop(0)
                    if parts and parts[0].startswith(('=', '-')):
                        parts.pop(0)
                    if not parts:
                        return header, ''
                else:
                    header = ''
                rest = '\n'.join(parts).lstrip().split('\n\n')
                desc = rest[0].replace('\n', ' ')
                return header, desc

        first_cell = self.first_cell()

        if not first_cell['cell_type'] == 'markdown':
            raise ValueError("The first cell is not in markdown but '{0}'.".format(
                first_cell['cell_type']))

        header, desc = split_header(first_cell['source'])
        if not desc and len(self.nb['cells']) > 1:
            second_cell = self.nb['cells'][1]
            if second_cell['cell_type'] == 'markdown':
                _, desc = split_header(second_cell['source'], False)

        reg_link = "(\\[(.*)\\]\\(([^ ]*)\\))"
        reg = re.compile(reg_link)
        new_desc = reg.sub("\\2", desc)
        return header, new_desc.replace('"', "")

    def get_thumbnail(self, max_width=200, max_height=200):
        """
        Process the notebook and create one picture based on the outputs
        to illustrate a notebook.

        @param      max_width       maximum size of the thumbnail
        @param      max_height      maximum size of the thumbnail
        @return                     string (SVG) or Image (PIL)

        .. versionadded:: 1.5
        """
        images = []
        cells = list(self.iter_cells())
        cells.reverse()
        for cell in cells:
            c = self.cell_image(cell, False)
            if c is not None and len(c) > 0 and len(c[0]) > 0:
                self._check_thumbnail_tuple(c)
                images.append(c)
        if len(images) == 0:
            for cell in cells:
                c = self.cell_image(cell, True)
                if c is not None and len(c) > 0 and len(c[0]) > 0:
                    self._check_thumbnail_tuple(c)
                    images.append(c)
                    if len(c[0]) >= 1000:
                        break
        if len(images) == 0:
            # no image, we need to consider the default one
            no_image = os.path.join(
                os.path.dirname(__file__), 'no_image_nb.png')
            with open(no_image, "rb") as f:
                c = (f.read(), "png")
                self._check_thumbnail_tuple(c)
                images.append(c)

        # select the image
        if len(images) == 0:
            raise ValueError("There should be at least one image.")
        elif len(images) == 1:
            image = images[0]
        else:
            # maybe later we'll implement a different logic
            # we pick the last one
            image = images[0]

        # zoom
        if image[1] != "svg":
            img = self._scale_image(
                image[0], image[1], max_width=max_width, max_height=max_height)
            return img
        else:
            return image[0]

    def _scale_image(self, in_bytes, format=None, max_width=200, max_height=200):
        """
        Scales an image with the same aspect ratio centered in an
        image with a given max_width and max_height.

        @param      in_bytes        image as bytes
        @param      format          indication of the format (can be empty)
        @param      max_width       maximum size of the thumbnail
        @param      max_height      maximum size of the thumbnail
        @return                     Image (PIL)

        .. versionadded:: 1.5
        """
        # local import to avoid testing dependency on PIL:
        try:
            from PIL import Image
        except ImportError:
            import Image

        if isinstance(in_bytes, tuple):
            in_bytes = in_bytes[0]
        if not isinstance(in_bytes, bytes):
            raise TypeError("bytes expected, not {0}".format(type(in_bytes)))
        img = Image.open(BytesIO(in_bytes))
        width_in, height_in = img.size
        scale_w = max_width / float(width_in)
        scale_h = max_height / float(height_in)

        if height_in * scale_w <= max_height:
            scale = scale_w
        else:
            scale = scale_h

        if scale >= 1.0:
            return img

        width_sc = int(round(scale * width_in))
        height_sc = int(round(scale * height_in))

        # resize the image and center
        img.thumbnail((width_sc, height_sc), Image.ANTIALIAS)
        thumb = Image.new('RGB', (max_width, max_height), (255, 255, 255))
        pos_insert = ((max_width - width_sc) // 2,
                      (max_height - height_sc) // 2)
        thumb.paste(img, pos_insert)
        return thumb

    def _merge_images(self, results):
        """
        Merges images defined by (buffer, format).
        The method uses PIL to merge images when possible.

        @return                     [ (image, format) ]

        .. versionadded:: 1.5
        """
        if len(results) == 1:
            results = results[0]
            self._check_thumbnail_tuple(results)
            return results
        elif len(results) == 0:
            return None
        formats_counts = Counter(_[1] for _ in results)
        if len(formats_counts) == 1:
            format = results[0][1]
        else:
            items = sorted(((v, k) for k, v in formats_counts.items()), False)
            for it in items:
                format = it
                break

        results = [_ for _ in results if _[1] == format]
        if format == "svg":
            return ("\n".join(_[0] for _ in results), format)
        else:
            # local import to avoid testing dependency on PIL:
            try:
                from PIL import Image
            except ImportError:
                import Image

            dx = 0.
            dy = 0.
            over = 0.7
            imgs = []
            for in_bytes, f in results:
                img = Image.open(BytesIO(in_bytes))
                imgs.append(img)
                dx = max(dx, img.size[0])
                dy += img.size[1] * over

            new_im = Image.new('RGB', (int(dx), int(dy)), (220, 220, 220))
            for img in imgs:
                dy -= img.size[1] * over
                new_im.paste(img, (0, max(int(dy), 0)))

            image_buffer = BytesIO()
            new_im.save(image_buffer, "PNG")
            b = image_buffer.getvalue(), "png"
            return b
