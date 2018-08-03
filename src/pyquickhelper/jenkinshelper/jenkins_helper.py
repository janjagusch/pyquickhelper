"""
@file
@brief Helpers to prepare a local Jenkins server.
"""
import sys
from ..loghelper import noLOG


def get_platform(platform=None):
    """
    Returns *platform* if not *None*, ``sys.platform`` otherwise.

    @param      platform    default values for which OS or
                            ``sys.platform``.
    @return                 platform

    This documentation was generated with a machine using the
    following *OS* (among the
    `possible values <https://docs.python.org/3/library/sys.html#sys.platform>`_).

    .. runpython::
        :showcode:

        from pyquickhelper.jenkinshelper.jenkins_helper import get_platform
        print(get_platform())

    .. versionadded:: 1.8
    """
    return platform or sys.platform


def default_engines(platform=None):
    """
    Returns a dictionary with default values for Jenkins server,
    you should update the path if the proposed path are not good.

    @param      platform    default values for which OS or
                            ``get_platform(platform)``.
    @return                 dictionary

    .. warning::

        Virtual environment with conda must be created on the same disk
        as the original interpreter. The other scenario is not supported
        by Anaconda.

    It returns:

    .. runpython::

        from pyquickhelper.jenkinshelper import default_engines
        print(default_engines())
    """
    platform = get_platform(platform)
    if platform == "win32":
        res = dict(Anaconda2="d:\\Anaconda",
                   Anaconda3="d:\\Anaconda3",
                   Python37="c:\\Python37_x64",
                   Python36="c:\\Python36_x64",
                   Python35="c:\\Python35_x64",
                   Python34="c:\\Python34_x64",
                   Python27="c:\\Python27",
                   WinPython37="c:\\APythonENSAE\\python37",
                   WinPython36="c:\\APythonENSAE\\python36",
                   WinPython35="c:\\APythonENSAE\\python35")
    elif platform == "linux":
        res = dict(Anaconda3="/usr/local/miniconda3",
                   Python37="/usr/local/python37",
                   Python36="/usr/local/python36")
    else:
        raise ValueError("Unknown value for platform '{0}'.".format(platform))

    return res


def default_jenkins_jobs():
    """
    Example of a list of jobs for parameter *module*
    of function @see fn setup_jenkins_server_yml.
    It returns:

    .. runpython::

        from pyquickhelper.jenkinshelper import default_jenkins_jobs
        print(default_jenkins_jobs())
    """
    pattern = "https://raw.githubusercontent.com/sdpython/%s/master/.local.jenkins.win.yml"
    yml = []
    for i, c in enumerate(["pyquickhelper"]):
        yml.append(('yml', pattern % c, 'H H(5-6) * * %d' % (i % 7)))
    return yml


def setup_jenkins_server_yml(js, github="sdpython", modules=None,
                             overwrite=False, location=None, prefix="",
                             delete_first=False, disable_schedule=False,
                             fLOG=noLOG, **kwargs):
    """
    Sets up many jobs on :epkg:`Jenkins`.

    @param      js                      @see cl JenkinsExt, jenkins server
    @param      github                  github account if it does not start with *http://*,
                                        the link to git repository of the project otherwise,
                                        we assume the job comes from the same repository,
                                        otherwise the function will have to called several times
    @param      modules                 modules for which to generate the Jenkins job (see @see fn default_jenkins_jobs)
    @param      overwrite               do not create the job if it already exists
    @param      location                None for default or a local folder
    @param      prefix                  add a prefix to the name
    @param      delete_first            removes all jobs before adding new ones
    @param      disable_schedule        disable scheduling for all jobs
    @param      fLOG                    logging function
    @param      kwargs                  see method @see me setup_jenkins_server
    @return                             list of created jobs

    Example::

        from pyquickhelper.jenkinshelper import JenkinsExt, setup_jenkins_server_yml, default_jenkins_jobs, default_engines

        js = JenkinsExt('http://localhost:8080/', None, None)
        modules = default_jenkins_jobs()
        engines = default_engines()
        setup_jenkins_server_yml(js, github="sdpython", modules=modules, fLOG=print,
                            overwrite = True, delete_first=True, engines=engines,
                            location = "d:\\\\jenkins\\\\pymy")

    See `.local.jenkins.win.yml <https://github.com/sdpython/pyquickhelper/blob/master/.local.jenkins.win.yml>`_
    about the syntax of a :epkg:`yml` job description.
    If *modules* is None, it is replaced by the results of
    @see fn default_jenkins_jobs.
    The platform is stored in *srv*.
    """
    if modules is None:
        modules = default_jenkins_jobs()
    if delete_first:
        js.delete_all_jobs()
    r = js.setup_jenkins_server(github=github, modules=modules, overwrite=overwrite,
                                location=location, prefix=prefix, disable_schedule=disable_schedule,
                                **kwargs)
    return r


def jenkins_final_postprocessing(xml_job, py27):
    """
    Postprocesses a job produced by :epkg:`Jenkins`.

    @param      xml_job     xml definition
    @param      py27        is it for Python 27
    @return                 new xml job
    """
    if py27:
        # options are not allowed
        xml_job = xml_job.replace(
            "python -X faulthandler -X showrefcount", "python")
    return xml_job
