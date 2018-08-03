# -*- coding: utf-8 -*-
"""
@file
@brief Defines a sphinx extension which if all parameters are documented.

.. versionadded:: 1.5
"""
import inspect
from typing import Tuple
import warnings
import sys


class _Types:
    @property
    def prop(self):
        pass

    @staticmethod
    def stat(self):
        pass


def import_object(docname, kind, use_init=True, tried_function_before=False) -> Tuple[object, str]:
    """
    Extracts an object defined by its name including the module name.

    @param      docname                 full name of the object
                                        (example: ``pyquickhelper.sphinxext.sphinx_docassert_extension.import_object``)
    @param      kind                    ``'function'`` or ``'class'`` or ``'kind'``
    @param      use_init                return the constructor instead of the class
    @param      tried_function_before   ``ismethod`` is False and ``isfunction`` is True
                                        but it is definitively a method
    @return                             tuple(object, name)
    @raises                             :epkg:`*py:RuntimeError` if cannot be imported,
                                        :epkg:`*py:TypeError` if it is a method or a property,
                                        :epkg:`*py:ValueError` if *kind* is unknown.

    .. versionchanged:: 1.8
        Parameter *tried_function_before* was added.
    """
    spl = docname.split(".")
    name = spl[-1]
    if kind not in ("method", "property", "staticmethod"):
        modname = ".".join(spl[:-1])
        code = 'from {0} import {1}\nmyfunc = {1}'.format(modname, name)
        codeobj = compile(code, 'conf{0}.py'.format(kind), 'exec')
    else:
        modname = ".".join(spl[:-2])
        classname = spl[-2]
        code = 'from {0} import {1}\nmyfunc = {1}'.format(modname, classname)
        codeobj = compile(code, 'conf{0}2.py'.format(kind), 'exec')

    context = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            exec(codeobj, context, context)
        except Exception as e:
            raise RuntimeError(
                "Unable to compile and execute '{0}' due to \n{1}\ngiven:\n{2}".format(code.replace('\n', '\\n'), e, docname)) from e

    myfunc = context["myfunc"]
    if kind == "function":
        if not inspect.isfunction(myfunc):
            raise TypeError("'{0}' is not a function".format(docname))
        name = spl[-1]
    elif kind == "property":
        if not inspect.isclass(myfunc):
            raise TypeError("'{0}' is not a class".format(docname))
        myfunc = getattr(myfunc, spl[-1])
        if inspect.isfunction(myfunc) or inspect.ismethod(myfunc):
            raise TypeError(
                "'{0}' is not a property - {1}".format(docname, myfunc))
        if myfunc.__class__ is not _Types.prop.__class__:
            raise TypeError(
                "'{0}' is not a property(*) - {1}".format(docname, myfunc))
        if not isinstance(myfunc, property):
            raise TypeError(
                "'{0}' is not a static property(**) - {1}".format(docname, myfunc))
        name = spl[-1]
    elif kind == "method":
        if not inspect.isclass(myfunc):
            raise TypeError("'{0}' is not a class".format(docname))
        myfunc = getattr(myfunc, spl[-1])
        if not inspect.isfunction(myfunc) and not tried_function_before and not inspect.ismethod(myfunc):
            raise TypeError(
                "'{0}' is not a method - {1}".format(docname, myfunc))
        if isinstance(myfunc, staticmethod):
            raise TypeError(
                "'{0}' is not a method(*) - {1}".format(docname, myfunc))
        if hasattr(myfunc, "__code__") and sys.version_info >= (3, 4):
            if len(myfunc.__code__.co_varnames) == 0:
                raise TypeError(
                    "'{0}' is not a method(**) - {1}".format(docname, myfunc))
            elif myfunc.__code__.co_varnames[0] != 'self':
                raise TypeError(
                    "'{0}' is not a method(***) - {1}".format(docname, myfunc))
        name = spl[-1]
    elif kind == "staticmethod":
        if not inspect.isclass(myfunc):
            raise TypeError("'{0}' is not a class".format(docname))
        myfunc = getattr(myfunc, spl[-1])
        if not inspect.isfunction(myfunc) and not inspect.ismethod(myfunc):
            raise TypeError(
                "'{0}' is not a static method - {1}".format(docname, myfunc))
        if myfunc.__class__ is not _Types.stat.__class__:
            raise TypeError(
                "'{0}' is not a static method(*) - {1}".format(docname, myfunc))
        name = spl[-1]
    elif kind == "class":
        if not inspect.isclass(myfunc):
            raise TypeError("'{0}' is not a class".format(docname))
        name = spl[-1]
        myfunc = myfunc.__init__ if use_init else myfunc
    else:
        raise ValueError("Unknwon value for 'kind'")

    return myfunc, name


def import_any_object(docname, use_init=True) -> Tuple[object, str, str]:
    """
    Extracts an object defined by its name including the module name.

    :param docname: full name of the object
        (example: ``pyquickhelper.sphinxext.sphinx_docassert_extension.import_object``)
    :param use_init: return the constructor instead of the class
    :returns: tuple(object, name, kind)
    :raises: :epkg:`*py:ImportError` if unable to import

    Kind is among ``'function'`` or ``'class'`` or ``'kind'``.
    """
    myfunc = None
    name = None
    excs = []
    for kind in ("function", "method", "staticmethod", "property", "class"):
        try:
            myfunc, name = import_object(docname, kind, use_init=use_init,
                                         tried_function_before=kind == "method")
            return myfunc, name, kind
        except Exception as e:
            # not this kind
            excs.append((kind, e))

    sec = " ### ".join("{0}-{1}-{2}".format(k, type(e), e).replace("\n", " ")
                       for k, e in excs)
    raise ImportError(
        "Unable to import '{0}'. Exceptions met: {1}".format(docname, sec))


def import_path(obj, class_name=None):
    """
    Determines the import path which is
    the shortest way to import the function. In case the
    following ``from module.submodule import function``
    works, the import path will be ``module.submodule``.

    :param obj: object
    :param class_name: :epkg:`Python` does not really distinguish between
        static method and functions. If not None, this parameter
        should contain the name of the class which holds the static
        method given in *obj*
    :returns: import path
    :raises: :epkg:`*py:TypeError` if object is a property,
        :epkg:`*py:RuntimeError` if cannot be imported

    The function does not work for methods or properties.
    It raises an exception or returns irrelevant results.
    """
    try:
        _ = obj.__module__
    except AttributeError:
        # This is a method.
        raise TypeError("obj is a method or a property ({0})".format(obj))

    if class_name is None:
        name = obj.__name__
    else:
        name = class_name
    elements = obj.__module__.split('.')
    found = None
    for i in range(1, len(elements) + 1):
        path = '.'.join(elements[:i])
        code = 'from {0} import {1}'.format(path, name)
        codeobj = compile(code, 'import_path_{0}.py'.format(name), 'exec')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            context = {}
            try:
                exec(codeobj, context, context)
                found = path
                break
            except Exception:
                continue

    if found is None:
        raise RuntimeError("Unable to import object '{0}' ({1}). Full path: '{2}'".format(
            name, obj, '.'.join(elements)))
    return found
