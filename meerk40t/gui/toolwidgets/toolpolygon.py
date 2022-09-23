from math import sqrt

import wx

from meerk40t.core.units import Length
from meerk40t.gui.laserrender import swizzlecolor
from meerk40t.gui.scene.sceneconst import (
    RESPONSE_ABORT,
    RESPONSE_CHAIN,
    RESPONSE_CONSUME,
)
from meerk40t.gui.toolwidgets.toolwidget import ToolWidget
from meerk40t.svgelements import Polygon


class PolygonTool(ToolWidget):
    """
    Polygon Drawing Tool.

    Adds polygon with clicks.
    """

    def __init__(self, scene):
        ToolWidget.__init__(self, scene)
        self.start_position = None
        self.point_series = []
        self.mouse_position = None

    def process_draw(self, gc: wx.GraphicsContext):
        if self.point_series:
            if self.scene.context.elements.default_stroke is None:
                self.pen.SetColour(wx.BLUE)
            else:
                self.pen.SetColour(
                    wx.Colour(swizzlecolor(self.scene.context.elements.default_stroke))
                )
            gc.SetPen(self.pen)
            if self.scene.context.elements.default_fill is None:
                gc.SetBrush(wx.TRANSPARENT_BRUSH)
            else:
                gc.SetBrush(
                    wx.Brush(
                        wx.Colour(
                            swizzlecolor(self.scene.context.elements.default_fill)
                        ),
                        wx.BRUSHSTYLE_SOLID,
                    )
                )
            points = list(self.point_series)
            if self.mouse_position is not None:
                points.append(self.mouse_position)
            points.append(points[0])
            gc.DrawLines(points)
            total_len = 0
            for idx in range(1, len(points)):
                x0 = points[idx][0]
                y0 = points[idx][1]
                x1 = points[idx - 1][0]
                y1 = points[idx - 1][1]
                total_len += sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0))
            s = "Pts: {pts}, Len={a}".format(
                pts=len(points) - 1,
                a=Length(amount=total_len, digits=2).length_mm,
            )
            self.scene.context.signal("statusmsg", s)

    def event(
        self,
        window_pos=None,
        space_pos=None,
        event_type=None,
        nearest_snap=None,
        modifiers=None,
        **kwargs,
    ):
        response = RESPONSE_CHAIN
        if event_type == "leftclick":
            if nearest_snap is None:
                self.point_series.append((space_pos[0], space_pos[1]))
            else:
                self.point_series.append((nearest_snap[0], nearest_snap[1]))
            response = RESPONSE_CONSUME
            if (
                len(self.point_series) > 2
                and abs(
                    complex(*self.point_series[0]) - complex(*self.point_series[-1])
                )
                < 5000
            ):
                self.end_tool()
                response = RESPONSE_ABORT
            if (
                len(self.point_series) > 2
                and abs(
                    complex(*self.point_series[-2]) - complex(*self.point_series[-1])
                )
                < 5000
            ):
                self.end_tool()
                response = RESPONSE_ABORT
            self.scene.tool_active = True
            response = RESPONSE_CONSUME
        elif event_type == "rightdown":
            was_already_empty = len(self.point_series) == 0
            self.scene.tool_active = False
            self.point_series = []
            self.mouse_position = None
            self.scene.request_refresh()
            if was_already_empty:
                self.scene.context("tool none\n")
            response = RESPONSE_ABORT
        elif event_type == "leftdown":
            self.scene.tool_active = True
            if nearest_snap is None:
                self.mouse_position = space_pos[0], space_pos[1]
            else:
                self.mouse_position = nearest_snap[0], nearest_snap[1]
            if self.point_series:
                self.scene.request_refresh()
            response = RESPONSE_CONSUME
        elif event_type in ("leftup", "move", "hover"):
            if nearest_snap is None:
                self.mouse_position = space_pos[0], space_pos[1]
            else:
                self.mouse_position = nearest_snap[0], nearest_snap[1]
            if self.point_series:
                self.scene.request_refresh()
                response = RESPONSE_CONSUME
        elif event_type == "doubleclick":
            self.end_tool()
            response = RESPONSE_ABORT
        elif event_type == "lost" or (event_type == "key_up" and modifiers == "escape"):
            if self.scene.tool_active:
                self.scene.tool_active = False
                self.scene.request_refresh()
                response = RESPONSE_CONSUME
            else:
                response = RESPONSE_CHAIN
            self.point_series = []
            self.mouse_position = None
        return response

    def end_tool(self):
        polyline = Polygon(*self.point_series)
        elements = self.scene.context.elements
        node = elements.elem_branch.add(shape=polyline, type="elem polyline", stroke_width=1000.0, stroke=self.scene.context.elements.default_stroke, fill=self.scene.context.elements.default_fill)
        if elements.classify_new:
            elements.classify([node])
        self.scene.tool_active = False
        self.point_series = []
        self.notify_created(node)
        self.mouse_position = None
