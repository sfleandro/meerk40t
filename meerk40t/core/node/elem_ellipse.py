from copy import copy
from math import sqrt

from meerk40t.core.node.mixins import Stroked
from meerk40t.core.node.node import Fillrule, Node
from meerk40t.svgelements import (
    SVG_ATTR_VECTOR_EFFECT,
    SVG_VALUE_NON_SCALING_STROKE,
    Circle,
    Ellipse,
    Matrix,
    Path,
    Point,
)


class EllipseNode(Node, Stroked):
    """
    EllipseNode is the bootstrapped node type for the 'elem ellipse' type.
    """

    def __init__(self, **kwargs):
        self.shape = None
        self.matrix = None
        self.fill = None
        self.stroke = None
        self.stroke_width = None
        self.stroke_scale = None
        self._stroke_zero = None
        self.fillrule = Fillrule.FILLRULE_EVENODD

        super().__init__(type="elem ellipse", **kwargs)
        self.__formatter = "{element_type} {id} {stroke}"
        assert isinstance(self.shape, (Ellipse, Circle))

        if self.matrix is None:
            self.matrix = self.shape.transform
        if self.fill is None:
            self.fill = self.shape.fill
        if self.stroke is None:
            self.stroke = self.shape.stroke
        if self.stroke_width is None:
            self.stroke_width = self.shape.implicit_stroke_width
        if self.stroke_scale is None:
            self.stroke_scale = (
                self.shape.values.get(SVG_ATTR_VECTOR_EFFECT)
                != SVG_VALUE_NON_SCALING_STROKE
            )
        if self._stroke_zero is None:
            # This defines the stroke-width zero point scale
            m = self.shape.values.get("viewport_transform")
            if m:
                self._stroke_zero = sqrt(abs(Matrix(m).determinant))
            else:
                self.stroke_width_zero()

        self.set_dirty_bounds()

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.type}', {str(self.shape)}, {str(self._parent)})"

    def __copy__(self):
        nd = self.node_dict
        nd["shape"] = copy(self.shape)
        nd["matrix"] = copy(self.matrix)
        nd["fill"] = copy(self.fill)
        nd["stroke_width"] = copy(self.stroke_width)
        return EllipseNode(**nd)

    def scaled(self, sx, sy, ox, oy):
        """
        This is a special case of the modified call, we are scaling
        the node without fundamentally altering it's properties
        """

        def apply_it(box):
            x0, y0, x1, y1 = box
            if sx != 1.0:
                d1 = x0 - ox
                d2 = x1 - ox
                x0 = ox + sx * d1
                x1 = ox + sx * d2
            if sy != 1.0:
                d1 = y0 - oy
                d2 = y1 - oy
                y0 = oy + sy * d1
                y1 = oy + sy * d2
            return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

        if self._bounds_dirty or self._bounds is None:
            # A pity but we need proper data
            self.modified()
            return

        self._bounds = apply_it(self._bounds)
        self._sync_svg()
        delta = float(self.implied_stroke_width) / 2.0
        self._paint_bounds = (
            self._bounds[0] - delta,
            self._bounds[1] - delta,
            self._bounds[2] + delta,
            self._bounds[3] + delta,
        )
        self.notify_scaled(self, sx=sx, sy=sy, ox=ox, oy=oy)

    def bbox(self, transformed=True, with_stroke=False):
        self._sync_svg()
        xmin, ymin, xmax, ymax = self.shape.bbox(
            transformed=transformed, with_stroke=False
        )
        if with_stroke:
            delta = float(self.implied_stroke_width) / 2.0
            return (
                xmin - delta,
                ymin - delta,
                xmax + delta,
                ymax + delta,
            )
        return xmin, ymin, xmax, ymax

    def preprocess(self, context, matrix, plan):
        self.stroke_scaled = False
        self.stroke_scaled = True
        self.matrix *= matrix
        self.stroke_scaled = False
        self._sync_svg()
        self.set_dirty_bounds()

    def default_map(self, default_map=None):
        default_map = super().default_map(default_map=default_map)
        default_map["element_type"] = "Ellipse"
        default_map.update(self.__dict__)
        return default_map

    def drop(self, drag_node, modify=True):
        # Dragging element into element.
        if drag_node.type.startswith("elem"):
            if modify:
                self.insert_sibling(drag_node)
            return True
        return False

    def revalidate_points(self):
        bounds = self.bounds
        if bounds is None:
            return
        self._points = []
        cx = (bounds[0] + bounds[2]) / 2
        cy = (bounds[1] + bounds[3]) / 2
        # self._points.append([bounds[0], bounds[1], "bounds top_left"])
        # self._points.append([bounds[2], bounds[1], "bounds top_right"])
        # self._points.append([bounds[0], bounds[3], "bounds bottom_left"])
        # self._points.append([bounds[2], bounds[3], "bounds bottom_right"])
        # self._points.append([cx, cy, "bounds center_center"])
        # self._points.append([cx, bounds[1], "bounds top_center"])
        # self._points.append([cx, bounds[3], "bounds bottom_center"])
        # self._points.append([bounds[0], cy, "bounds center_left"])
        # self._points.append([bounds[2], cy, "bounds center_right"])
        obj = self.shape
        npoints = [
            Point(obj.cx - obj.rx, obj.cy),
            Point(obj.cx, obj.cy - obj.ry),
            Point(obj.cx + obj.rx, obj.cy),
            Point(obj.cx, obj.cy + obj.ry),
        ]
        p1 = Point(obj.cx, obj.cy)
        if not obj.transform.is_identity():
            points = list(map(obj.transform.point_in_matrix_space, npoints))
            p1 = obj.transform.point_in_matrix_space(p1)
        else:
            points = npoints
        for pt in points:
            self._points.append([pt.x, pt.y, "point"])
        self._points.append([p1.x, p1.y, "bounds center_center"])

    def update_point(self, index, point):
        return False

    def add_point(self, point, index=None):
        return False

    def _sync_svg(self):
        self.shape.values[SVG_ATTR_VECTOR_EFFECT] = (
            SVG_VALUE_NON_SCALING_STROKE if not self.stroke_scale else ""
        )
        self.shape.transform = self.matrix
        self.shape.stroke_width = self.stroke_width
        self.shape.stroke = self.stroke
        try:
            del self.shape.values["viewport_transform"]
            # If we had transforming viewport that is no longer relevant
        except KeyError:
            pass

    def as_path(self):
        self._sync_svg()
        return abs(Path(self.shape))
