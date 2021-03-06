import os
import tempfile
import bpy
from bpy.app.handlers import persistent
from ..bin import pyluxcore
from .. import utils
from ..utils import compatibility
from . import frame_change_pre
from ..utils.errorlog import LuxCoreErrorLog


def _init_persistent_cache_file_path(settings, suffix):
    if not settings.file_path:
        blend_name = utils.get_blendfile_name()
        if blend_name:
            pgi_path = "//" + blend_name + "." + suffix
        else:
            # Blend file was not saved yet
            pgi_path = os.path.join(tempfile.gettempdir(), "Untitled." + suffix)
        settings.file_path = pgi_path


@persistent
def handler(_):
    """ Note: the only argument Blender passes is always None """

    for scene in bpy.data.scenes:
        # Update OpenCL devices if .blend is opened on
        # a different computer than it was saved on
        updated = scene.luxcore.opencl.update_devices_if_necessary()

        if updated:
            # Set first GPU as film OpenCL device, or disable film OpenCL if no GPUs found
            scene.luxcore.config.film_opencl_enable = False
            scene.luxcore.config.film_opencl_device = "none"
            for i, device in enumerate(scene.luxcore.opencl.devices):
                # Intel GPU devices can lead to crashes, so disable them by default
                if device.type == "OPENCL_GPU" and not "intel" in device.name.lower():
                    try:
                        scene.luxcore.config.film_opencl_device = str(i)
                        scene.luxcore.config.film_opencl_enable = True
                        break
                    except TypeError:
                        pass

        if pyluxcore.GetPlatformDesc().Get("compile.LUXRAYS_DISABLE_OPENCL").GetBool():
            # OpenCL not available, make sure we are using CPU device
            scene.luxcore.config.device = "CPU"

        # Use Blender output path for filesaver by default
        if not scene.luxcore.config.filesaver_path:
            scene.luxcore.config.filesaver_path = scene.render.filepath

        _init_persistent_cache_file_path(scene.luxcore.config.photongi, "pgi")
        _init_persistent_cache_file_path(scene.luxcore.config.envlight_cache, "env")
        _init_persistent_cache_file_path(scene.luxcore.config.dls_cache, "dlsc")

    # Run converters for backwards compatibility
    compatibility.run()

    frame_change_pre.have_to_check_node_trees = False
    LuxCoreErrorLog.clear()
