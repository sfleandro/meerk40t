from meerk40t.svgelements import (
    Circle,
    Ellipse,
    Path,
    Point,
    Polygon,
    Polyline,
    Rect,
    SimpleLine,
    SVGImage,
)


def get_type_from_element(element):
    if isinstance(element, Path):
        return "elem path"
    elif isinstance(element, SVGImage):
        return "elem image"
    elif isinstance(element, Rect):
        return "elem rect"
    elif isinstance(element, SimpleLine):
        return "elem line"
    elif isinstance(element, (Ellipse, Circle)):
        return "elem ellipse"
    elif isinstance(element, (Polygon, Polyline)):
        return "elem polyline"
    elif isinstance(element, Point):
        return "elem point"


non_structural_nodes = (
    "op cut",
    "op raster",
    "op image",
    "op engrave",
    "op dots",
    "op hatch",
    "util console",
    "util wait",
    "util home",
    "util goto",
    "util origin",
    "util output",
    "util input",
    "reference",
    "lasercode",
    "cutcode",
    "blob",
    "elem ellipse",
    "elem image",
    "elem path",
    "elem point",
    "elem polyline",
    "elem rect",
    "elem line",
    "elem text",
    "file",
    "group",
)
op_parent_nodes = (
    "op cut",
    "op raster",
    "op image",
    "op engrave",
    "op dots",
    "op hatch",
)
op_nodes = (
    "op cut",
    "op raster",
    "op image",
    "op engrave",
    "op dots",
    "op hatch",
    "util console",
    "util wait",
    "util home",
    "util goto",
    "util origin",
    "util output",
    "util input",
)
elem_nodes = (
    "elem ellipse",
    "elem image",
    "elem path",
    "elem geomstr",
    "elem point",
    "elem polyline",
    "elem rect",
    "elem line",
    "elem text",
)
elem_group_nodes = (
    "elem ellipse",
    "elem image",
    "elem path",
    "elem geomstr",
    "elem point",
    "elem polyline",
    "elem rect",
    "elem line",
    "elem text",
    "group",
    "file",
)
elem_ref_nodes = (
    "elem ellipse",
    "elem image",
    "elem path",
    "elem geomstr",
    "elem point",
    "elem polyline",
    "elem rect",
    "elem line",
    "elem text",
    "reference",
)
