import imp
import hashlib
import re
import sys
import subprocess
import os


def get_adhoc_module(path):
    name = re.sub('\W+', '__', path) + '_' + hashlib.md5(path).hexdigest()[:8]
    try:
        return sys.modules[name]
    except KeyError:
        return imp.load_source(name, path)


def get_func_name(spec):
    if isinstance(spec, basestring):
        return spec
    return '%s.%s' % (getattr(spec, '__module__', '__module__'), getattr(spec, '__name__', str(spec)))


def get_func(spec):

    if not isinstance(spec, basestring):
        return spec
    
    m = re.match(r'([\w\.]+):([\w]+)$', spec)
    if m:
        mod_name, func_name = m.groups()
        mod = __import__(mod_name, fromlist=['.'])
        return getattr(mod, func_name)

    m = re.match(r'(.+):([\w]+)$', spec)
    if m:
        path, func_name = m.groups()
        if '/' in path:
            module = get_adhoc_module(path)
            return getattr(module, func_name)

    raise ValueError('spec must be like "/path/to/module.py:func_name" or "package.module:func_name"; got %r' % spec)


def envvars_for_event(event, prefix='SGEVENT'):
    envvars = {}
    for k, v in event.iteritems():
        k = prefix + '_' + re.sub('\W+', '_', k.upper())
        if isinstance(v, dict):
            envvars.update(envvars_for_event(v, k))
        else:
            envvars[k] = str(v)
    return envvars


def get_command_prefix(envvars):
    if 'VEE_EXEC_ARGS' in envvars or 'KS_DEV_ARGS' in envvars:
        # These both have a "dev" command with a "--bootstrap" which do
        # the same thing.
        return ['dev', '--bootstrap']
    else:
        return []