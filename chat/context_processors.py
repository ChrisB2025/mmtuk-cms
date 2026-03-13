from mmtuk_cms.version import VERSION


def cms_version(request):
    return {'cms_version': VERSION}
