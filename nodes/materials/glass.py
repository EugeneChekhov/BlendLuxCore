import bpy
from bpy.props import FloatProperty, BoolProperty
from ..base import LuxCoreNodeMaterial, Roughness
from ..sockets import LuxCoreSocketFloat
from ..output import get_active_output
from ...ui import icons
from ...utils import node as utils_node

CAUCHYC_DESCRIPTION = (
    "Dispersion strength (cauchy C coefficient)\n"
    "Realistic values range from 0.00354 to 0.01342\n"
    "Not supported by architectural and rough glass"
)

ARCHGLASS_DESCRIPTION = (
    "Use for thin sheets of glass like window panes, where refraction does not matter "
    "(skips refraction during transmission, propagates alpha and shadow rays).\n\n"
    "Note that instead of using this option, you can also set the shadow color in the "
    "output node to white, which achieves the same effect while keeping the refraction "
    "for camera rays, which looks better if the edges of the glass sheets are visible"
)


class LuxCoreSocketCauchyC(bpy.types.NodeSocket, LuxCoreSocketFloat):
    default_value: FloatProperty(name="Dispersion", default=0, min=0, soft_max=0.01342,
                                 step=0.1, precision=5, description=CAUCHYC_DESCRIPTION,
                                 update=utils_node.force_viewport_update)

    def draw(self, context, layout, node, text):
        if getattr(node, "architectural", False):
            # This socket is used on a glass node and is not exported because
            # archglass does not support dispersion
            layout.active = False

        if getattr(node, "rough", False):
            # This socket is used on a glass node and is not exported because
            # roughglass does not support dispersion
            layout.active = False

        super().draw(context, layout, node, text)


class LuxCoreNodeMatGlass(bpy.types.Node, LuxCoreNodeMaterial):
    """ Node for the three LuxCore materials glass, roughglass and archglass """
    bl_label = "Glass Material"
    bl_width_default = 160

    use_anisotropy: BoolProperty(name=Roughness.aniso_name,
                                  default=False,
                                  description=Roughness.aniso_desc,
                                  update=Roughness.update_anisotropy)
    rough: BoolProperty(name="Rough",
                         default=False,
                         description="Rough glass surface instead of a smooth one",
                         update=Roughness.toggle_roughness)
    architectural: BoolProperty(update=utils_node.force_viewport_update, name="Architectural",
                                 default=False,
                                 description=ARCHGLASS_DESCRIPTION)

    def init(self, context):
        self.add_input("LuxCoreSocketColor", "Transmission Color", (1, 1, 1))
        self.add_input("LuxCoreSocketColor", "Reflection Color", (1, 1, 1))
        self.add_input("LuxCoreSocketIOR", "IOR", 1.5)
        self.add_input("LuxCoreSocketCauchyC", "Dispersion", 0)

        Roughness.init(self, default=0.05, init_enabled=False)
        self.add_common_inputs()

        self.outputs.new("LuxCoreSocketMaterial", "Material")

    def draw_buttons(self, context, layout):
        column = layout.row()
        column.enabled = not self.architectural
        column.prop(self, "rough")

        if self.rough:
            Roughness.draw(self, context, layout)

        # Rough glass cannot be archglass
        row = layout.row()
        row.enabled = not self.rough
        row.prop(self, "architectural")

        if self.get_interior_volume():
            layout.label(text="Using IOR of interior volume", icon=icons.INFO)

    def sub_export(self, exporter, depsgraph, props, luxcore_name=None, output_socket=None):
        if self.rough:
            type = "roughglass"
        elif self.architectural:
            type = "archglass"
        else:
            type = "glass"

        definitions = {
            "type": type,
            "kt": self.inputs["Transmission Color"].export(exporter, depsgraph, props),
            "kr": self.inputs["Reflection Color"].export(exporter, depsgraph, props),
        }

        # Only use the glass node IOR socket if there is no interior volume
        if not self.get_interior_volume():
            definitions["interiorior"] = self.inputs["IOR"].export(exporter, depsgraph, props)

        cauchyc = self.inputs["Dispersion"].export(exporter, depsgraph, props)
        if self.inputs["Dispersion"].is_linked or cauchyc > 0:
            definitions["cauchyc"] = cauchyc

        if self.rough:
            Roughness.export(self, exporter, depsgraph, props, definitions)
        self.export_common_inputs(exporter, depsgraph, props, definitions)

        return self.create_props(props, definitions, luxcore_name)

    def get_interior_volume(self):
        node_tree = self.id_data
        active_output = get_active_output(node_tree)
        if active_output:
            return utils_node.get_linked_node(active_output.inputs["Interior Volume"])
        return False
