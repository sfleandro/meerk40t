from math import sqrt

import wx

from meerk40t.core.units import Length
from meerk40t.gui.icons import icons8_lock_50, icons8_padlock_50
from meerk40t.gui.laserrender import swizzlecolor
from meerk40t.gui.wxutils import CheckBox, StaticBoxSizer, TextCtrl
from meerk40t.svgelements import Color

_ = wx.GetTranslation


class ColorPanel(wx.Panel):
    def __init__(
        self,
        *args,
        context=None,
        label=None,
        attribute=None,
        callback=None,
        node=None,
        **kwds,
    ):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.callback = callback
        if attribute is None:
            attribute = "stroke"
        self.attribute = attribute
        self.label = label
        self.node = node

        self.main_sizer = StaticBoxSizer(self, wx.ID_ANY, _(self.label), wx.VERTICAL)
        color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_sizer.Add(color_sizer, 0, wx.EXPAND, 0)
        self.btn_color = []
        self.underliner = []
        self.bgcolors = [
            0xFFFFFF,
            0x000000,
            0xFF0000,
            0x00FF00,
            0x0000FF,
            0xFFFF00,
            0xFF00FF,
            0x00FFFF,
            0xFFFFFF,
            None,
        ]
        self.last_col_idx = len(self.bgcolors) - 1
        for i in range(len(self.bgcolors)):
            self.underliner.append(wx.StaticBitmap(self, wx.ID_ANY))
            self.underliner[i].SetBackgroundColour(wx.BLUE)
            self.underliner[i].SetMaxSize(wx.Size(-1, 3))
            # self.lbl_color[i].SetMinSize((-1, 20))
            self.btn_color.append(wx.Button(self, wx.ID_ANY, ""))
            if i == 0:
                self.btn_color[i].SetForegroundColour(wx.RED)
                self.btn_color[i].SetLabel("X")
            elif i == len(self.bgcolors) - 1:
                self.btn_color[i].SetLabel(_("Custom"))
            else:
                self.btn_color[i].SetForegroundColour(wx.Colour(self.bgcolors[i]))
                colinfo = wx.Colour(self.bgcolors[i]).GetAsString(wx.C2S_NAME)
                self.btn_color[i].SetLabel(_(colinfo))
            self.btn_color[i].SetMinSize((10, 23))
            self.btn_color[i].SetBackgroundColour(wx.Colour(self.bgcolors[i]))
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.btn_color[i], 0, wx.EXPAND, 0)
            sizer.Add(self.underliner[i], 0, wx.EXPAND, 0)
            color_sizer.Add(sizer, 1, wx.EXPAND, 0)
            self.btn_color[i].Bind(wx.EVT_BUTTON, self.on_button)
        font = wx.Font(
            7,
            wx.FONTFAMILY_SWISS,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_BOLD,
        )
        self.btn_color[self.last_col_idx].SetFont(font)
        self.SetSizer(self.main_sizer)
        self.main_sizer.Fit(self)
        self.Layout()
        self.set_widgets(self.node)

    def on_button(self, event):
        value = None
        button = event.GetEventObject()
        bidx = None
        if button == self.btn_color[self.last_col_idx]:
            nodecol = None
            cvalue = getattr(self.node, self.attribute, None)
            if cvalue == "none":
                cvalue = None
            if cvalue is not None:
                nodecol = wx.Colour(swizzlecolor(cvalue))
            color_data = wx.ColourData()
            color_data.SetColour(wx.Colour(nodecol))
            # We try to prepopulate user defined colors from
            # the colors of the existing operations
            idx = 0
            for operation in self.context.elements.ops():
                if hasattr(operation, "color"):
                    if operation.color is not None and operation.color.argb is not None:
                        color_data.SetCustomColour(
                            idx, wx.Colour(swizzlecolor(operation.color))
                        )
                        idx += 1
                        # There are only 16 colors available
                        if idx > 15:
                            break
            dlg = wx.ColourDialog(self, color_data)
            if dlg.ShowModal() == wx.ID_OK:
                color_data = dlg.GetColourData()
                cvalue = color_data.GetColour()
                value = Color(swizzlecolor(cvalue.GetRGB()), 1.0)
                button.SetBackgroundColour(cvalue)
            else:
                return
        else:
            for bidx, sbtn in enumerate(self.btn_color):
                if sbtn == button:
                    value = None
                    if bidx == 0:
                        value = None
                    else:
                        if bidx < 0 or bidx >= len(self.btn_color):
                            bidx = -1
                        else:
                            bcolor = button.GetBackgroundColour()
                            rgb = bcolor.GetRGB()
                            color = swizzlecolor(rgb)
                            value = Color(color, 1.0)
                    break
        setattr(self.node, self.attribute, value)
        self.context.elements.signal("element_property_update", self.node)
        if self.callback is not None:
            self.callback()
        self.mark_color(bidx)
        self.node.focus()

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def accepts(self, node):
        return hasattr(node, self.attribute)

    def set_widgets(self, node):
        self.node = node
        # print(f"set_widget for {self.attribute} to {str(node)}")
        if self.node is None or not self.accepts(node):
            self.Hide()
            return
        self.mark_color(None)
        self.Show()

    def mark_color(self, idx):
        def countercolor(bgcolor):
            background = swizzlecolor(bgcolor)
            c1 = Color("Black")
            c2 = Color("White")
            if Color.distance(background, c1) > Color.distance(background, c2):
                textcolor = c1
            else:
                textcolor = c2
            wxcolor = wx.Colour(swizzlecolor(textcolor))
            return wxcolor

        if self.node is None:
            idx = -1
            self.btn_color[self.last_col_idx].SetBackgroundColour(None)
            self.bgcolors[self.last_col_idx] = None
        else:
            value = getattr(self.node, self.attribute, None)
            nodecol = None
            if value == "none":
                value = None

            colinfo = "None"
            if value is not None:
                nodecol = wx.Colour(swizzlecolor(value))
                self.bgcolors[self.last_col_idx] = nodecol
                self.btn_color[self.last_col_idx].SetBackgroundColour(
                    self.bgcolors[self.last_col_idx]
                )
                self.btn_color[self.last_col_idx].SetForegroundColour(
                    countercolor(self.bgcolors[self.last_col_idx])
                )
                s = ""
                try:
                    s = nodecol.GetAsString(wx.C2S_NAME)
                except AssertionError:
                    s = ""
                if s != "":
                    s = s + " = " + value.hexrgb
                else:
                    s = value.hexrgb
                colinfo = s
            self.main_sizer.SetLabel(_(self.label) + " (" + colinfo + ")")
            self.main_sizer.Refresh()

            if idx is None:  # Okay, we need to determine it ourselves
                idx = -1
                if value is None:
                    idx = 0
                else:
                    for i, btn in enumerate(self.btn_color):
                        if i == 0:  # We skip the none color...
                            continue
                        col = self.btn_color[i].GetBackgroundColour()
                        if nodecol == col:
                            idx = i
                            break

        for i, liner in enumerate(self.underliner):
            if i == idx:
                liner.Show(True)
            else:
                liner.Show(False)
        self.Layout()


class IdPanel(wx.Panel):
    def __init__(
        self, *args, context=None, node=None, showid=True, showlabel=True, **kwds
    ):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node
        # Shall we display id / label?
        self.showid = showid
        self.showlabel = showlabel
        self.text_id = TextCtrl(self, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)
        self.text_label = TextCtrl(self, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_id_label = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_id = StaticBoxSizer(self, wx.ID_ANY, _("Id"), wx.VERTICAL)
        self.sizer_id.Add(self.text_id, 1, wx.EXPAND, 0)
        self.sizer_label = StaticBoxSizer(self, wx.ID_ANY, _("Label"), wx.VERTICAL)
        self.sizer_label.Add(self.text_label, 1, wx.EXPAND, 0)
        sizer_id_label.Add(self.sizer_id, 1, wx.EXPAND, 0)
        sizer_id_label.Add(self.sizer_label, 1, wx.EXPAND, 0)

        main_sizer.Add(sizer_id_label, 0, wx.EXPAND, 0)

        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Layout()
        self.text_id.SetActionRoutine(self.on_text_id_change)
        self.text_label.SetActionRoutine(self.on_text_label_change)
        self.set_widgets(self.node)

    def on_text_id_change(self):
        try:
            self.node.id = self.text_id.GetValue()
            self.context.elements.signal("element_property_update", self.node)
        except AttributeError:
            pass

    def on_text_label_change(self):
        try:
            self.node.label = self.text_label.GetValue()
            self.context.elements.signal("element_property_update", self.node)
        except AttributeError:
            pass

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def set_widgets(self, node):
        def mklabel(value):
            res = ""
            if value is not None:
                res = str(value)
            return res

        self.node = node
        # print(f"set_widget for {self.attribute} to {str(node)}")
        vis1 = False
        vis2 = False
        if hasattr(self.node, "id") and self.showid:
            vis1 = True
            self.text_id.SetValue(mklabel(node.id))
        self.text_id.Show(vis1)
        self.sizer_id.Show(vis1)

        if hasattr(self.node, "label") and self.showlabel:
            vis2 = True
            self.text_label.SetValue(mklabel(node.label))
        self.text_label.Show(vis2)
        self.sizer_label.Show(vis2)

        if vis1 or vis2:
            self.Show()
        else:
            self.Hide()


class LinePropPanel(wx.Panel):
    def __init__(self, *args, context=None, node=None, **kwds):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node
        capchoices = (_("Butt"), _("Round"), _("Square"))
        joinchoices = (_("Arcs"), _("Bevel"), _("Miter"), _("Miter-Clip"), _("Round"))
        fillchoices = (_("Non-Zero"), _("Even-Odd"))
        self.combo_cap = wx.ComboBox(
            self, wx.ID_ANY, choices=capchoices, style=wx.CB_DROPDOWN | wx.CB_READONLY
        )
        self.combo_join = wx.ComboBox(
            self, wx.ID_ANY, choices=joinchoices, style=wx.CB_DROPDOWN | wx.CB_READONLY
        )
        self.combo_fill = wx.ComboBox(
            self, wx.ID_ANY, choices=fillchoices, style=wx.CB_DROPDOWN | wx.CB_READONLY
        )
        self.combo_cap.SetMaxSize(wx.Size(100, -1))
        self.combo_join.SetMaxSize(wx.Size(100, -1))
        self.combo_fill.SetMaxSize(wx.Size(100, -1))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        sizer_attributes = wx.BoxSizer(wx.HORIZONTAL)

        self.sizer_cap = StaticBoxSizer(self, wx.ID_ANY, _("Line-End"), wx.VERTICAL)
        self.sizer_cap.Add(self.combo_cap, 1, wx.EXPAND, 0)

        self.sizer_join = StaticBoxSizer(self, wx.ID_ANY, _("Line-Join"), wx.VERTICAL)
        self.sizer_join.Add(self.combo_join, 1, wx.EXPAND, 0)

        self.sizer_fill = StaticBoxSizer(self, wx.ID_ANY, _("Fillrule"), wx.VERTICAL)
        self.sizer_fill.Add(self.combo_fill, 1, wx.EXPAND, 0)

        sizer_attributes.Add(self.sizer_cap, 1, wx.EXPAND, 0)
        sizer_attributes.Add(self.sizer_join, 1, wx.EXPAND, 0)
        sizer_attributes.Add(self.sizer_fill, 1, wx.EXPAND, 0)

        main_sizer.Add(sizer_attributes, 0, wx.EXPAND, 0)

        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Layout()
        self.combo_cap.Bind(wx.EVT_COMBOBOX, self.on_cap)
        self.combo_join.Bind(wx.EVT_COMBOBOX, self.on_join)
        self.combo_fill.Bind(wx.EVT_COMBOBOX, self.on_fill)
        self.set_widgets(self.node)

    def on_cap(self, event):
        if self.node is None or self.node.lock:
            return
        id = self.combo_cap.GetSelection()
        try:
            self.node.linecap = id
            self.context.signal("element_property_update", self.node)
            self.context.signal("refresh_scene", "Scene")
        except AttributeError:
            pass

    def on_join(self, event):
        if self.node is None or self.node.lock:
            return
        id = self.combo_join.GetSelection()
        try:
            self.node.linejoin = id
            self.context.signal("element_property_update", self.node)
            self.context.signal("refresh_scene", "Scene")
        except AttributeError:
            pass

    def on_fill(self, event):
        if self.node is None or self.node.lock:
            return
        id = self.combo_fill.GetSelection()
        try:
            self.node.fillrule = id
            self.context.signal("element_property_update", self.node)
            self.context.signal("refresh_scene", "Scene")
        except AttributeError:
            pass

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def set_widgets(self, node):
        self.node = node
        # print(f"set_widget for {self.attribute} to {str(node)}")
        vis1 = False
        vis2 = False
        vis3 = False
        if hasattr(self.node, "linecap"):
            vis1 = True
            self.combo_cap.SetSelection(int(node.linecap))
        if hasattr(self.node, "linejoin"):
            vis2 = True
            self.combo_join.SetSelection(int(node.linejoin))
        if hasattr(self.node, "fillrule"):
            vis3 = True
            self.combo_fill.SetSelection(int(node.fillrule))

        self.combo_cap.Show(vis1)
        self.sizer_cap.Show(vis1)
        self.combo_join.Show(vis2)
        self.sizer_join.Show(vis2)
        self.combo_fill.Show(vis3)
        self.sizer_fill.Show(vis3)

        if vis1 or vis2 or vis3:
            self.Show()
        else:
            self.Hide()


class StrokeWidthPanel(wx.Panel):
    def __init__(self, *args, context=None, node=None, **kwds):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        s_sizer = StaticBoxSizer(self, wx.ID_ANY, _("Stroke-Width"), wx.HORIZONTAL)
        main_sizer.Add(s_sizer, 1, wx.EXPAND, 0)
        # Plus one combobox + value field for stroke width
        strokewidth_label = wx.StaticText(self, wx.ID_ANY, label=_("Width:"))
        self.text_width = wx.TextCtrl(
            self, wx.ID_ANY, value="0.10", style=wx.TE_PROCESS_ENTER
        )
        self.text_width.SetMaxSize(wx.Size(100, -1))

        self.unit_choices = ["px", "pt", "mm", "cm", "inch", "mil"]
        self.combo_units = wx.ComboBox(
            self,
            wx.ID_ANY,
            choices=self.unit_choices,
            style=wx.CB_DROPDOWN | wx.CB_READONLY,
        )
        self.combo_units.SetSelection(0)
        self.combo_units.SetMaxSize(wx.Size(100, -1))

        self.chk_scale = wx.CheckBox(self, wx.ID_ANY, _("Scale"))
        self.chk_scale.SetToolTip(
            _("Toggle the behaviour of stroke-growth.")
            + "\n"
            + _("Active: stroke width remains the same, regardless of the element size")
            + "\n"
            + _("Inactive: stroke grows/shrink with scaled element")
        )
        s_sizer.Add(strokewidth_label, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        s_sizer.Add(self.text_width, 1, wx.EXPAND, 0)
        s_sizer.Add(self.combo_units, 1, wx.EXPAND, 0)
        s_sizer.Add(self.chk_scale, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        self.Bind(wx.EVT_COMBOBOX, self.on_stroke_width, self.combo_units)
        self.Bind(wx.EVT_TEXT_ENTER, self.on_stroke_width, self.text_width)
        self.Bind(wx.EVT_CHECKBOX, self.on_chk_scale, self.chk_scale)
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Layout()
        self.set_widgets(self.node)

    def on_chk_scale(self, event):
        if self.node is None or self.node.lock:
            return
        flag = self.chk_scale.GetValue()
        try:
            if self.node.stroke_scaled != flag:
                self.node.stroke_scaled = flag
                self.context.signal("refresh_scene", "Scene")
                self.context.signal("element_property_update", self.node)
        except (ValueError, AttributeError):
            pass

    def on_stroke_width(self, event):
        if self.node is None or self.node.lock:
            return
        try:
            swidth = float(
                Length(
                    f"{self.text_width.GetValue()}{self.unit_choices[self.combo_units.GetSelection()]}"
                )
            )
            stroke_scale = (
                sqrt(abs(self.node.matrix.determinant))
                if self.node.stroke_scaled
                else 1.0
            )
            stroke_width = swidth / stroke_scale
            if self.node.stroke_width != stroke_width:
                self.node.stroke_width = stroke_width
                self.node.altered()
                self.context.signal("refresh_scene", "Scene")
                self.context.signal("element_property_update", self.node)
        except (ValueError, AttributeError):
            pass

    def set_widgets(self, node):
        self.node = node
        enable = False
        if self.node is None:
            self.text_width.SetValue("0")
            self.combo_units.SetSelection(0)
            self.chk_scale.SetValue(True)
        elif hasattr(self.node, "stroke_width") and hasattr(self.node, "stroke_scaled"):
            enable = True
            self.chk_scale.SetValue(self.node.stroke_scaled)
            # Lets establish which unit might be the best to represent the display
            found_something = False
            if self.node.stroke_width is None or self.node.stroke_width == 0:
                value = 0
                idxunit = 0  # px
                found_something = True
            else:
                best_post = 99999999
                delta = 0.99999999
                best_pre = 0
                # # We don't need to scale it here...
                # factor = (
                #     sqrt(abs(self.node.matrix.determinant))
                #     if self.node.stroke_scaled
                #     else 1.0
                # )
                factor = 1
                node_stroke_width = self.node.stroke_width * factor
                # print (f"Stroke-width={self.node.stroke_width} ({node_stroke_width}), scaled={self.node.stroke_scaled}")
                for idx, unit in enumerate(self.unit_choices):
                    std = float(Length(f"1{unit}"))
                    fraction = abs(round(node_stroke_width / std, 6))
                    if fraction == 0:
                        continue
                    curr_post = 0
                    curr_pre = int(fraction)
                    while fraction < 1:
                        curr_post += 1
                        fraction *= 10
                    fraction -= curr_pre
                    # print (f"unit={unit}, fraction={fraction}, digits={curr_post}, value={node_stroke_width / std}")
                    takespref = False
                    if fraction < delta:
                        takespref = True
                    elif fraction == delta and curr_pre > best_pre:
                        takespref = True
                    elif fraction == delta and curr_post < best_post:
                        takespref = True
                    if takespref:
                        best_pre = curr_pre
                        delta = fraction
                        best_post = curr_post
                        idxunit = idx
                        value = node_stroke_width / std
                        found_something = True

                if not found_something:
                    std = float(Length(f"1mm"))
                    if node_stroke_width / std < 0.1:
                        idxunit = 0  # px
                    else:
                        idxunit = 2  # mm
                    unit = self.unit_choices[idxunit]
                    std = float(Length(f"1{unit}"))
                    value = node_stroke_width / std
            self.text_width.SetValue(str(round(value, 6)))
            self.combo_units.SetSelection(idxunit)

        self.text_width.Enable(enable)
        self.combo_units.Enable(enable)
        self.chk_scale.Enable(enable)

    def pane_hide(self):
        pass

    def pane_show(self):
        pass


class PositionSizePanel(wx.Panel):
    def __init__(self, *args, context=None, node=None, **kwds):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node
        self.text_x = TextCtrl(
            self,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
            limited=True,
            check="length",
        )
        self.text_y = TextCtrl(
            self, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER, limited=True, check="length"
        )
        self.text_w = TextCtrl(
            self,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
            limited=True,
            check="length",
            nonzero=True,
        )
        self.text_h = TextCtrl(
            self,
            wx.ID_ANY,
            "",
            style=wx.TE_PROCESS_ENTER,
            limited=True,
            check="length",
            nonzero=True,
        )
        self.btn_lock_ratio = wx.ToggleButton(self, wx.ID_ANY, "")
        self.btn_lock_ratio.SetValue(True)
        self.bitmap_locked = icons8_lock_50.GetBitmap(resize=25, use_theme=False)
        self.bitmap_unlocked = icons8_padlock_50.GetBitmap(resize=25, use_theme=False)
        self.__set_properties()
        self.__do_layout()

        self.text_x.SetActionRoutine(self.on_text_x_enter)
        self.text_y.SetActionRoutine(self.on_text_y_enter)
        self.text_w.SetActionRoutine(self.on_text_w_enter)
        self.text_h.SetActionRoutine(self.on_text_h_enter)
        self.btn_lock_ratio.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_ratio)

        self.set_widgets(self.node)

    def __do_layout(self):
        # begin wxGlade: PositionPanel.__do_layout
        sizer_main = wx.BoxSizer(wx.VERTICAL)
        sizer_h = StaticBoxSizer(self, wx.ID_ANY, _("Height:"), wx.HORIZONTAL)
        sizer_w = StaticBoxSizer(self, wx.ID_ANY, _("Width:"), wx.HORIZONTAL)
        sizer_opt = wx.BoxSizer(wx.VERTICAL)
        sizer_y = StaticBoxSizer(self, wx.ID_ANY, "Y:", wx.HORIZONTAL)
        sizer_x = StaticBoxSizer(self, wx.ID_ANY, "X:", wx.HORIZONTAL)

        sizer_x.Add(self.text_x, 1, wx.EXPAND, 0)
        sizer_y.Add(self.text_y, 1, wx.EXPAND, 0)
        sizer_w.Add(self.text_w, 1, wx.EXPAND, 0)
        sizer_h.Add(self.text_h, 1, wx.EXPAND, 0)

        self.btn_lock_ratio.SetMinSize((32, 32))
        self.btn_lock_ratio.SetToolTip(
            _("Lock the ratio of width / height to the original values")
        )
        # Set Bitmap
        self.on_toggle_ratio(None)

        sizer_opt.Add(self.btn_lock_ratio, 0, wx.ALIGN_CENTER_HORIZONTAL, 0)

        sizer_h_xy = wx.BoxSizer(wx.HORIZONTAL)
        sizer_h_xy.Add(sizer_x, 1, wx.EXPAND, 0)
        sizer_h_xy.Add(sizer_y, 1, wx.EXPAND, 0)

        self.sizer_h_wh = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer_h_wh.Add(sizer_w, 1, wx.EXPAND, 0)
        self.sizer_h_wh.Add(sizer_h, 1, wx.EXPAND, 0)

        sizer_h_dimensions = wx.BoxSizer(wx.HORIZONTAL)

        self.sizer_v_xywh = wx.BoxSizer(wx.VERTICAL)
        self.sizer_v_xywh.Add(sizer_h_xy, 0, wx.EXPAND, 0)
        self.sizer_v_xywh.Add(self.sizer_h_wh, 0, wx.EXPAND, 0)
        sizer_h_dimensions.Add(self.sizer_v_xywh, 1, wx.EXPAND, 0)
        sizer_h_dimensions.Add(sizer_opt, 0, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_main.Add(sizer_h_dimensions, 0, wx.EXPAND, 0)

        self.SetSizer(sizer_main)
        sizer_main.Fit(self)
        self.Layout()

    def __set_properties(self):
        # begin wxGlade: PositionPanel.__set_properties
        self.text_h.SetToolTip(_("New height (enter to apply)"))
        self.text_w.SetToolTip(_("New width (enter to apply)"))
        self.text_x.SetToolTip(
            _("New X-coordinate of left top corner (enter to apply)")
        )
        self.text_y.SetToolTip(
            _("New Y-coordinate of left top corner (enter to apply)")
        )

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def _set_widgets_hidden(self):
        self.text_x.SetValue("")
        self.text_y.SetValue("")
        self.text_w.SetValue("")
        self.text_h.SetValue("")
        self.Hide()

    def show_hide_wh(self, displaythem):
        self.text_w.Show(show=displaythem)
        self.text_h.Show(show=displaythem)
        self.sizer_h_wh.ShowItems(displaythem)
        self.sizer_v_xywh.Layout()
        self.Layout()

    def set_widgets(self, node):
        self.node = node
        try:
            bb = node.bounds
        except:
            # Node is none or bounds threw an error.
            bb = None

        if bb is None:
            # Bounds was genuinely none, or node threw an error.
            self._set_widgets_hidden()
            return

        en_xy = (
            not getattr(self.node, "lock", False)
            or self.context.elements.lock_allows_move
        )
        en_wh = not getattr(self.node, "lock", False)
        x = bb[0]
        y = bb[1]
        w = bb[2] - bb[0]
        h = bb[3] - bb[1]
        units = self.context.units_name
        if units in ("inch", "inches"):
            units = "in"

        self.text_x.SetValue(
            f"{Length(amount=x, preferred_units=units, digits=4).preferred_length}"
        )
        self.text_y.SetValue(
            f"{Length(amount=y, preferred_units=units, digits=4).preferred_length}"
        )
        self.text_w.SetValue(
            f"{Length(amount=w, preferred_units=units, digits=4).preferred_length}"
        )
        self.text_h.SetValue(
            f"{Length(amount=h, preferred_units=units, digits=4).preferred_length}"
        )
        self.text_x.Enable(en_xy)
        self.text_y.Enable(en_xy)
        self.text_w.Enable(en_wh)
        self.text_h.Enable(en_wh)
        self.show_hide_wh(node.type != "elem point")
        self.Show()

    def translate_it(self):
        if (
            getattr(self.node, "lock", False)
            and not self.context.elements.lock_allows_move
        ):
            return
        bb = self.node.bounds
        try:
            newx = float(Length(self.text_x.GetValue()))
            newy = float(Length(self.text_y.GetValue()))
        except (ValueError, AttributeError):
            return
        dx = newx - bb[0]
        dy = newy - bb[1]
        if dx != 0 or dy != 0:
            self.node.matrix.post_translate(dx, dy)
            # self.node.modified()
            self.node.translated(dx, dy)
            self.context.elements.signal("element_property_update", self.node)

    def scale_it(self, was_width):
        if getattr(self.node, "lock", False):
            return
        bb = self.node.bounds
        keep_ratio = self.btn_lock_ratio.GetValue()
        try:
            neww = float(Length(self.text_w.GetValue()))
            newh = float(Length(self.text_h.GetValue()))
        except (ValueError, AttributeError):
            return
        if bb[2] != bb[0]:
            sx = neww / (bb[2] - bb[0])
        else:
            sx = 1
        if bb[3] != bb[1]:
            sy = newh / (bb[3] - bb[1])
        else:
            sy = 1
        if keep_ratio:
            if was_width:
                sy = sx
            else:
                sx = sy
        if sx != 1.0 or sy != 1.0:
            self.node.matrix.post_scale(sx, sy, bb[0], bb[1])
            self.node.scaled(sx=sx, sy=sy, ox=bb[0], oy=bb[1])
            # self.node.modified()
            bb = self.node.bounds
            w = bb[2] - bb[0]
            h = bb[3] - bb[1]
            units = self.context.units_name
            if units in ("inch", "inches"):
                units = "in"
            self.text_w.SetValue(
                f"{Length(amount=w, preferred_units=units, digits=4).preferred_length}"
            )
            self.text_h.SetValue(
                f"{Length(amount=h, preferred_units=units, digits=4).preferred_length}"
            )

            self.context.elements.signal("element_property_update", self.node)

    def on_toggle_ratio(self, event):
        if self.btn_lock_ratio.GetValue():
            self.btn_lock_ratio.SetBitmap(self.bitmap_locked)
        else:
            self.btn_lock_ratio.SetBitmap(self.bitmap_unlocked)

    def on_text_x_enter(self):
        self.translate_it()

    def on_text_y_enter(self):
        self.translate_it()

    def on_text_w_enter(self):
        self.scale_it(True)

    def on_text_h_enter(self):
        self.scale_it(False)


class PreventChangePanel(wx.Panel):
    def __init__(self, *args, context=None, node=None, **kwds):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node
        self.check_lock = CheckBox(self, wx.ID_ANY, _("Lock element"))
        self.__set_properties()
        self.__do_layout()
        self.check_lock.Bind(wx.EVT_CHECKBOX, self.on_check_lock)
        self.set_widgets(self.node)

    def __do_layout(self):
        # begin wxGlade: PositionPanel.__do_layout
        sizer_main = wx.BoxSizer(wx.VERTICAL)
        sizer_lock = StaticBoxSizer(
            self, wx.ID_ANY, _("Prevent changes:"), wx.HORIZONTAL
        )
        sizer_lock.Add(self.check_lock, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        sizer_main.Add(sizer_lock, 0, wx.EXPAND, 0)

        self.SetSizer(sizer_main)
        sizer_main.Fit(self)
        self.Layout()

    def __set_properties(self):
        self.check_lock.SetToolTip(
            _(
                "If active then this element is effectively prevented from being modified"
            )
        )

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def _set_widgets_hidden(self):
        self.Hide()

    def set_widgets(self, node):
        self.node = node
        if hasattr(self.node, "lock"):
            self.check_lock.Enable(True)
            self.check_lock.SetValue(self.node.lock)
        else:
            self.check_lock.SetValue(False)
            self.check_lock.Enable(False)
        self.Show()

    def on_check_lock(self, event):
        flag = self.check_lock.GetValue()
        if hasattr(self.node, "lock"):
            self.node.lock = flag
            self.context.elements.signal("element_property_update", self.node)
            self.set_widgets(self.node)


class RoundedRectPanel(wx.Panel):
    def __init__(
        self,
        *args,
        context=None,
        node=None,
        **kwds,
    ):
        # begin wxGlade: LayerSettingPanel.__init__
        kwds["style"] = kwds.get("style", 0)
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context
        self.node = node
        self.fonts = []

        main_sizer = StaticBoxSizer(
            self, wx.ID_ANY, _("Rounded Corners"), wx.HORIZONTAL
        )
        sizer_x = StaticBoxSizer(self, wx.ID_ANY, _("X:"), wx.HORIZONTAL)
        sizer_y = StaticBoxSizer(self, wx.ID_ANY, _("Y:"), wx.HORIZONTAL)
        # Wxpython seems to have issues with drawing a roundedrect with values
        # beyond 50%, so let's limit it (makes sense anyway)..
        self.slider_x = wx.Slider(
            self,
            wx.ID_ANY,
            value=0,
            minValue=0,
            maxValue=50,
            style=wx.SL_LABELS | wx.SL_HORIZONTAL,
        )
        self.slider_x.SetToolTip(_("Ratio of X-Radius compared to width (in %)"))

        self.slider_y = wx.Slider(
            self,
            wx.ID_ANY,
            value=0,
            minValue=0,
            maxValue=50,
            style=wx.SL_LABELS | wx.SL_HORIZONTAL,
        )
        self.slider_y.SetToolTip(_("Ratio of Y-Radius compared to height (in %)"))
        self.btn_lock_ratio = wx.ToggleButton(self, wx.ID_ANY, "")
        self.btn_lock_ratio.SetValue(True)
        self.btn_lock_ratio.SetMinSize((32, 32))
        self.btn_lock_ratio.SetToolTip(_("Lock the radii of X- and Y-axis"))
        # Set Bitmap
        self.bitmap_locked = icons8_lock_50.GetBitmap(resize=25, use_theme=False)
        self.bitmap_unlocked = icons8_padlock_50.GetBitmap(resize=25, use_theme=False)

        sizer_x.Add(self.slider_x, 1, wx.EXPAND, 0)
        sizer_y.Add(self.slider_y, 1, wx.EXPAND, 0)
        sizer_y.Add(self.btn_lock_ratio, 0, wx.ALIGN_CENTER_VERTICAL, 0)
        main_sizer.Add(sizer_x, 1, wx.EXPAND, 0)
        main_sizer.Add(sizer_y, 1, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Layout()
        self.set_widgets(self.node)
        self.slider_x.Bind(wx.EVT_SLIDER, self.on_slider_x)
        self.slider_y.Bind(wx.EVT_SLIDER, self.on_slider_y)
        self.btn_lock_ratio.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_ratio)
        self.set_widgets(node)

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def accepts(self, node):
        if node.type == "elem rect":
            return True
        else:
            return False

    def set_widgets(self, node):
        self.node = node
        # print(f"set_widget for {self.attribute} to {str(node)}")
        if self.node is None or not self.accepts(node):
            self.Hide()
            return
        # Set values for rx and ry
        bb = self.node.bbox()
        width = self.node.shape.width
        height = self.node.shape.height
        if self.node.shape.rx is None:
            rx = 0
        else:
            rx = self.node.shape.rx
        if self.node.shape.ry is None:
            ry = 0
        else:
            ry = self.node.shape.ry
        flag = bool(rx == ry)
        self.btn_lock_ratio.SetValue(flag)
        self.on_toggle_ratio(None)
        if width == 0:
            int_rx = 0
        else:
            int_rx = int(100.0 * rx / width)

        if height == 0:
            int_ry = 0
        else:
            int_ry = int(100.0 * ry / height)

        max_val_x = self.slider_x.GetMax()
        max_val_y = self.slider_x.GetMax()
        self.slider_x.SetValue(min(max_val_x, int_rx))
        self.slider_y.SetValue(min(max_val_y, int_ry))
        self.Show()

    def set_values(self, axis, value):
        sync = self.btn_lock_ratio.GetValue()
        width = self.node.shape.width
        height = self.node.shape.height
        if axis == 0:  # x
            rx = value / 100 * width
            self.node.shape.rx = rx
            if sync:
                self.node.shape.ry = rx
                max_val_y = self.slider_x.GetMax()
                int_ry = int(100.0 * rx / height)
                self.slider_y.SetValue(min(max_val_y, int_ry))
        else:
            ry = value / 100 * height
            self.node.shape.ry = ry
            if sync:
                self.node.shape.rx = ry
                max_val_x = self.slider_x.GetMax()
                int_rx = int(100.0 * ry / width)
                self.slider_x.SetValue(min(max_val_x, int_rx))

        self.node.altered()
        self.context.elements.signal("element_property_update", self.node)
        self.context.signal("refresh_scene", "Scene")

    def on_slider_x(self, event):
        if self.node is None:
            return
        value = self.slider_x.GetValue()
        self.set_values(0, value)

    def on_slider_y(self, event):
        if self.node is None:
            return
        value = self.slider_y.GetValue()
        self.set_values(1, value)

    def on_toggle_ratio(self, event):
        if self.btn_lock_ratio.GetValue():
            self.btn_lock_ratio.SetBitmap(self.bitmap_locked)
            self.slider_y.Enable(False)
        else:
            self.btn_lock_ratio.SetBitmap(self.bitmap_unlocked)
            self.slider_y.Enable(True)
