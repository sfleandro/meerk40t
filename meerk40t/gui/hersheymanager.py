import os
from glob import glob
from math import isinf

import wx

from meerk40t.core.units import UNITS_PER_INCH, Length
from meerk40t.extra.hershey import (
    create_linetext_node,
    fonts_registered,
    update_linetext,
    validate_node,
)
from meerk40t.gui.icons import STD_ICON_SIZE, icons8_choose_font_50
from meerk40t.gui.mwindow import MWindow
from meerk40t.gui.wxutils import StaticBoxSizer
from meerk40t.kernel import get_safe_path

# begin wxGlade: dependencies
# end wxGlade

# begin wxGlade: extracode
# end wxGlade

_ = wx.GetTranslation


def create_preview_image(context, fontfile):
    simplefont = os.path.basename(fontfile)
    base, ext = os.path.splitext(fontfile)
    bmpfile = base + ".png"
    pattern = "The quick brown fox..."
    node = create_linetext_node(
        context, 0, 0, pattern, font=simplefont, font_size=Length("12pt")
    )
    if node is None:
        return False
    if node.bounds is None:
        return False
    make_raster = context.elements.lookup("render-op/make_raster")
    if make_raster is None:
        return False
    xmin, ymin, xmax, ymax = node.bounds
    if isinf(xmin):
        # No bounds for selected elements
        return False
    width = xmax - xmin
    height = ymax - ymin
    dpi = 150
    dots_per_units = dpi / UNITS_PER_INCH
    new_width = width * dots_per_units
    new_height = height * dots_per_units
    new_height = max(new_height, 1)
    new_width = max(new_width, 1)
    try:
        bitmap = make_raster(
            [node],
            bounds=node.bounds,
            width=new_width,
            height=new_height,
            bitmap=True,
        )
    except:
        # Invalid path or whatever...
        return False
    try:
        bitmap.SaveFile(bmpfile, wx.BITMAP_TYPE_PNG)
    except (OSError, RuntimeError, PermissionError, FileNotFoundError):
        return False
    return True


def load_create_preview_file(context, fontfile):
    bitmap = None
    base, ext = os.path.splitext(fontfile)
    bmpfile = base + ".png"
    if not os.path.exists(bmpfile):
        __ = create_preview_image(context, fontfile)
    if os.path.exists(bmpfile):
        bitmap = wx.Bitmap()
        bitmap.LoadFile(bmpfile, wx.BITMAP_TYPE_PNG)
    return bitmap


def fontdirectory(context):
    fontdir = ""
    safe_dir = os.path.realpath(get_safe_path(context.kernel.name))
    context.setting(str, "font_directory", safe_dir)
    fontdir = context.font_directory
    return fontdir


def remove_fontfile(fontfile):
    if os.path.exists(fontfile):
        try:
            os.remove(fontfile)
            base, ext = os.path.splitext(fontfile)
            bmpfile = base + ".png"
            if os.path.exists(bmpfile):
                os.remove(bmpfile)
        except (OSError, RuntimeError, PermissionError, FileNotFoundError):
            pass


class LineTextPropertPanel(wx.Panel):
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

        main_sizer = StaticBoxSizer(self, wx.ID_ANY, _("Vector-Text"), wx.VERTICAL)

        sizer_text = StaticBoxSizer(self, wx.ID_ANY, _("Content"), wx.HORIZONTAL)
        self.text_text = wx.TextCtrl(self, wx.ID_ANY, "")
        sizer_text.Add(self.text_text, 1, wx.EXPAND, 0)

        self.btn_bigger = wx.Button(self, wx.ID_ANY, "++")
        self.btn_bigger.SetToolTip(_("Increase the font-size"))
        sizer_text.Add(self.btn_bigger, 0, wx.EXPAND, 0)

        self.btn_smaller = wx.Button(self, wx.ID_ANY, "--")
        self.btn_smaller.SetToolTip(_("Decrease the font-size"))
        sizer_text.Add(self.btn_smaller, 0, wx.EXPAND, 0)

        sizer_fonts = StaticBoxSizer(
            self, wx.ID_ANY, _("Fonts (double-click to use)"), wx.VERTICAL
        )

        self.list_fonts = wx.ListBox(self, wx.ID_ANY)
        self.list_fonts.SetMinSize((-1, 140))
        self.list_fonts.SetToolTip(
            _("Select to preview the font, double-click to apply it")
        )
        sizer_fonts.Add(self.list_fonts, 0, wx.EXPAND, 0)

        self.bmp_preview = wx.StaticBitmap(self, wx.ID_ANY)
        self.bmp_preview.SetMinSize((-1, 70))
        sizer_fonts.Add(self.bmp_preview, 0, wx.EXPAND, 0)

        main_sizer.Add(sizer_text, 0, wx.EXPAND, 0)
        main_sizer.Add(sizer_fonts, 0, wx.EXPAND, 0)
        self.SetSizer(main_sizer)
        self.Layout()
        self.btn_bigger.Bind(wx.EVT_BUTTON, self.on_button_bigger)
        self.btn_smaller.Bind(wx.EVT_BUTTON, self.on_button_smaller)
        self.text_text.Bind(wx.EVT_TEXT, self.on_text_change)
        self.list_fonts.Bind(wx.EVT_LISTBOX, self.on_list_font)
        self.list_fonts.Bind(wx.EVT_LISTBOX_DCLICK, self.on_list_font_dclick)
        self.set_widgets(self.node)

    def pane_hide(self):
        pass

    def pane_show(self):
        pass

    def accepts(self, node):
        if (
            hasattr(node, "mkfont")
            and hasattr(node, "mkfontsize")
            and hasattr(node, "mktext")
        ):
            # Let's us the opportunity to check for incorrept types and fix them...
            validate_node(node)
            return True
        else:
            return False

    def set_widgets(self, node):
        self.node = node
        # print(f"set_widget for {self.attribute} to {str(node)}")
        if self.node is None or not self.accepts(node):
            self.Hide()
            return
        fontdir = fontdirectory(self.context)
        self.load_directory(fontdir)
        self.text_text.SetValue(node.mktext)
        self.Show()

    def load_directory(self, fontdir):
        self.fonts = []
        self.list_fonts.Clear()
        if os.path.exists(fontdir):
            self.context.font_directory = fontdir
            fontinfo = fonts_registered()
            for extension in fontinfo:
                ext = "*." + extension
                for p in glob(os.path.join(fontdir, ext.lower())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
                for p in glob(os.path.join(fontdir, ext.upper())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
        self.list_fonts.SetItems(self.fonts)
        # index = -1
        # lookfor = getattr(self.context, "sxh_preferred", "")

    def update_node(self):
        vtext = self.text_text.GetValue()
        update_linetext(self.context, self.node, vtext)
        self.context.signal("element_property_reload", self.node)
        self.context.signal("refresh_scene", "Scene")

    def on_button_bigger(self, event):
        if self.node is None:
            return
        self.node.mkfontsize *= 1.2
        self.update_node()

    def on_button_smaller(self, event):
        if self.node is None:
            return
        self.node.mkfontsize /= 1.2
        self.update_node()

    def on_text_change(self, event):
        self.update_node()

    def on_list_font_dclick(self, event):
        if self.node is None:
            return
        index = self.list_fonts.GetSelection()
        if index >= 0:
            fontname = self.fonts[index]
            self.node.mkfont = fontname
            self.update_node()

    def on_list_font(self, event):
        if self.list_fonts.GetSelection() >= 0:
            fontdir = fontdirectory(self.context)
            font_file = self.fonts[self.list_fonts.GetSelection()]
            full_font_file = os.path.join(fontdir, font_file)
            bmp = load_create_preview_file(self.context, full_font_file)
            # if bmp is not None:
            #     bmap_bundle = wx.BitmapBundle().FromBitmap(bmp)
            # else:
            #     bmap_bundle = wx.BitmapBundle()
            # self.bmp_preview.SetBitmap(bmap_bundle)
            if bmp is None:
                bmp = wx.NullBitmap
            self.bmp_preview.SetBitmap(bmp)


class PanelFontSelect(wx.Panel):
    def __init__(self, *args, context=None, **kwds):
        # begin wxGlade: clsLasertools.__init__
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        self.fonts = []

        sizer_fonts = StaticBoxSizer(
            self, wx.ID_ANY, _("Fonts (double-click to use)"), wx.VERTICAL
        )
        mainsizer.Add(sizer_fonts, 1, wx.EXPAND, 0)

        self.list_fonts = wx.ListBox(self, wx.ID_ANY)
        self.list_fonts.SetToolTip(
            _("Select to preview the font, double-click to apply it")
        )
        sizer_fonts.Add(self.list_fonts, 1, wx.EXPAND, 0)

        self.bmp_preview = wx.StaticBitmap(self, wx.ID_ANY)
        self.bmp_preview.SetMinSize((-1, 70))
        sizer_fonts.Add(self.bmp_preview, 0, wx.EXPAND, 0)

        sizer_buttons = wx.BoxSizer(wx.HORIZONTAL)
        sizer_fonts.Add(sizer_buttons, 0, wx.EXPAND, 0)

        self.btn_bigger = wx.Button(self, wx.ID_ANY, "++")
        self.btn_bigger.SetToolTip(_("Increase the font-size"))
        sizer_buttons.Add(self.btn_bigger, 0, wx.EXPAND, 0)

        self.btn_smaller = wx.Button(self, wx.ID_ANY, "--")
        self.btn_smaller.SetToolTip(_("Decrease the font-size"))
        sizer_buttons.Add(self.btn_smaller, 0, wx.EXPAND, 0)

        lbl_spacer = wx.StaticText(self, wx.ID_ANY, "")
        sizer_buttons.Add(lbl_spacer, 1, 0, 0)

        self.SetSizer(mainsizer)

        self.Layout()

        self.Bind(wx.EVT_LISTBOX, self.on_list_font, self.list_fonts)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.on_list_font_dclick, self.list_fonts)
        self.Bind(wx.EVT_BUTTON, self.on_btn_bigger, self.btn_bigger)
        self.Bind(wx.EVT_BUTTON, self.on_btn_smaller, self.btn_smaller)

        # end wxGlade
        fontdir = fontdirectory(self.context)
        self.load_directory(fontdir)

    def load_directory(self, fontdir):
        self.fonts = []
        self.list_fonts.Clear()
        if os.path.exists(fontdir):
            self.context.font_directory = fontdir
            fontinfo = fonts_registered()
            for extension in fontinfo:
                ext = "*." + extension
                for p in glob(os.path.join(fontdir, ext.lower())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
                for p in glob(os.path.join(fontdir, ext.upper())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
        self.list_fonts.SetItems(self.fonts)
        # index = -1
        # lookfor = getattr(self.context, "sxh_preferred", "")

    def on_btn_bigger(self, event):
        self.context.signal("linetext", "bigger")

    def on_btn_smaller(self, event):
        self.context.signal("linetext", "smaller")

    def on_list_font_dclick(self, event):
        index = self.list_fonts.GetSelection()
        if index >= 0:
            fontname = self.fonts[index]
            self.context.signal("linetext", "font", fontname)

    def on_list_font(self, event):
        if self.list_fonts.GetSelection() >= 0:
            font_file = self.fonts[self.list_fonts.GetSelection()]
            full_font_file = os.path.join(self.context.font_directory, font_file)
            bmp = load_create_preview_file(self.context, full_font_file)
            # if bmp is not None:
            #     bmap_bundle = wx.BitmapBundle().FromBitmap(bmp)
            # else:
            #     bmap_bundle = wx.BitmapBundle()
            # self.bmp_preview.SetBitmap(bmap_bundle)
            if bmp is None:
                bmp = wx.NullBitmap
            self.bmp_preview.SetBitmap(bmp)


class HersheyFontSelector(MWindow):
    def __init__(self, *args, **kwds):
        super().__init__(450, 550, submenu="", *args, **kwds)
        self.panel = PanelFontSelect(self, wx.ID_ANY, context=self.context)
        _icon = wx.NullIcon
        _icon.CopyFromBitmap(icons8_choose_font_50.GetBitmap(resize=25))
        # _icon.CopyFromBitmap(icons8_computer_support_50.GetBitmap())
        self.SetIcon(_icon)
        self.SetTitle(_("Font-Selection"))

    def window_open(self):
        pass

    def window_close(self):
        pass

    def delegates(self):
        yield self.panel

    @staticmethod
    def submenu():
        # Suppress = True
        return ("", "Font-Selector", True)


class PanelFontManager(wx.Panel):
    def __init__(self, *args, context=None, **kwds):
        # begin wxGlade: clsLasertools.__init__
        kwds["style"] = kwds.get("style", 0) | wx.TAB_TRAVERSAL
        wx.Panel.__init__(self, *args, **kwds)
        self.context = context

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        self.fonts = []

        self.text_info = wx.TextCtrl(
            self,
            wx.ID_ANY,
            _(
                "MeerK40t can use Hershey-Fonts or Autocad-86 shape fonts designed to be rendered purely with vectors.\n"
                + "They can be scaled, burned like any other vector shape and are therefore very versatile.\n"
                + "See more: https://en.wikipedia.org/wiki/Hershey_fonts , "
            ),
            style=wx.BORDER_NONE | wx.TE_MULTILINE | wx.TE_READONLY,
        )

        self.text_info.SetMinSize((-1, 90))
        sizer_info = StaticBoxSizer(self, wx.ID_ANY, _("Information"), wx.HORIZONTAL)
        mainsizer.Add(sizer_info, 0, wx.EXPAND, 0)
        sizer_info.Add(self.text_info, 1, wx.EXPAND, 0)

        sizer_directory = StaticBoxSizer(
            self, wx.ID_ANY, _("Font-Directory"), wx.HORIZONTAL
        )
        mainsizer.Add(sizer_directory, 0, wx.EXPAND, 0)

        self.text_fontdir = wx.TextCtrl(self, wx.ID_ANY, "")
        sizer_directory.Add(self.text_fontdir, 1, wx.EXPAND, 0)

        self.btn_dirselect = wx.Button(self, wx.ID_ANY, "...")
        sizer_directory.Add(self.btn_dirselect, 0, wx.EXPAND, 0)

        sizer_fonts = StaticBoxSizer(self, wx.ID_ANY, _("Fonts"), wx.VERTICAL)
        mainsizer.Add(sizer_fonts, 1, wx.EXPAND, 0)

        self.list_fonts = wx.ListBox(self, wx.ID_ANY)
        sizer_fonts.Add(self.list_fonts, 1, wx.EXPAND, 0)

        self.bmp_preview = wx.StaticBitmap(self, wx.ID_ANY)
        self.bmp_preview.SetMinSize((-1, 70))
        sizer_fonts.Add(self.bmp_preview, 0, wx.EXPAND, 0)

        sizer_buttons = wx.BoxSizer(wx.HORIZONTAL)
        sizer_fonts.Add(sizer_buttons, 0, wx.EXPAND, 0)

        self.btn_add = wx.Button(self, wx.ID_ANY, _("Import"))
        sizer_buttons.Add(self.btn_add, 0, wx.EXPAND, 0)

        self.btn_delete = wx.Button(self, wx.ID_ANY, _("Delete"))
        sizer_buttons.Add(self.btn_delete, 0, wx.EXPAND, 0)

        lbl_spacer = wx.StaticText(self, wx.ID_ANY, "")
        sizer_buttons.Add(lbl_spacer, 1, 0, 0)

        self.webresources = [
            "https://github.com/kamalmostafa/hershey-fonts/tree/master/hershey-fonts",
            "http://iki.fi/sol/hershey/index.html",
            "https://www.mepwork.com/2017/11/autocad-shx-fonts.html",
        ]
        choices = [
            _("Goto a font-source..."),
            _("Hershey Fonts - #1"),
            _("Hershey Fonts - #2"),
            _("Autocad-SHX-Fonts"),
        ]
        self.combo_webget = wx.ComboBox(
            self,
            wx.ID_ANY,
            choices=choices,
            style=wx.CB_DROPDOWN | wx.CB_READONLY,
        )
        self.combo_webget.SetSelection(0)
        sizer_buttons.Add(self.combo_webget, 0, wx.EXPAND, 0)

        self.SetSizer(mainsizer)

        self.Layout()

        self.Bind(wx.EVT_TEXT, self.on_text_directory, self.text_fontdir)
        self.Bind(wx.EVT_BUTTON, self.on_btn_directory, self.btn_dirselect)
        self.Bind(wx.EVT_LISTBOX, self.on_list_font, self.list_fonts)
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.on_list_font_dclick, self.list_fonts)
        self.Bind(wx.EVT_BUTTON, self.on_btn_import, self.btn_add)
        self.Bind(wx.EVT_BUTTON, self.on_btn_delete, self.btn_delete)
        self.Bind(wx.EVT_COMBOBOX, self.on_combo_webget, self.combo_webget)
        # end wxGlade
        fontdir = fontdirectory(self.context)
        self.text_fontdir.SetValue(fontdir)

    def on_text_directory(self, event):
        fontdir = self.text_fontdir.GetValue()
        self.fonts = []
        self.list_fonts.Clear()
        if os.path.exists(fontdir):
            self.context.font_directory = fontdir
            fontinfo = fonts_registered()
            for extension in fontinfo:
                ext = "*." + extension
                for p in glob(os.path.join(fontdir, ext.lower())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
                for p in glob(os.path.join(fontdir, ext.upper())):
                    fn = os.path.basename(p)
                    if fn not in self.fonts:
                        self.fonts.append(fn)
        self.list_fonts.SetItems(self.fonts)
        # Let the world know we have fonts
        self.context.signal("icons")

    def on_btn_directory(self, event):
        fontdir = self.text_fontdir.GetValue()
        dlg = wx.DirDialog(
            None,
            _("Choose font directory"),
            fontdir,
            style=wx.DD_DEFAULT_STYLE
            # | wx.DD_DIR_MUST_EXIST
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.text_fontdir.SetValue(dlg.GetPath())
        # Only destroy a dialog after you're done with it.
        dlg.Destroy()

    def on_list_font_dclick(self, event):
        if self.list_fonts.GetSelection() >= 0:
            font_file = self.fonts[self.list_fonts.GetSelection()]
            self.context.setting(str, "shx_preferred", None)
            self.context.shx_preferred = font_file

            # full_font_file = os.path.join(self.context.font_directory, font_file)
        #  print(f"Fontfile: {font_file}, full: {full_font_file}")

    def on_list_font(self, event):
        if self.list_fonts.GetSelection() >= 0:
            font_file = self.fonts[self.list_fonts.GetSelection()]
            full_font_file = os.path.join(self.context.font_directory, font_file)
            bmp = load_create_preview_file(self.context, full_font_file)
            # if bmp is not None:
            #     bmap_bundle = wx.BitmapBundle().FromBitmap(bmp)
            # else:
            #     bmap_bundle = wx.BitmapBundle()
            # self.bmp_preview.SetBitmap(bmap_bundle)
            if bmp is None:
                bmp = wx.NullBitmap
            self.bmp_preview.SetBitmap(bmp)

    def on_btn_import(self, event):
        fontinfo = fonts_registered()
        wildcard = "Vector-Fonts"
        idx = 0
        for extension in fontinfo:
            ext = "*." + extension
            if idx == 0:
                wildcard += "|"
            else:
                wildcard += ";"
            wildcard += ext.lower() + ";" + ext.upper()
            idx += 1
        for extension in fontinfo:
            ext = "*." + extension
            info = fontinfo[extension]
            wildcard += f"|{info[0]}-Fonts|{ext.lower()};{ext.upper()}"
        dlg = wx.FileDialog(
            self,
            message=_(
                "Select a font-file to be imported into the the font-directory {fontdir}"
            ).format(fontdir=self.context.font_directory),
            defaultDir="",
            defaultFile="",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        )
        font_files = None
        paths = None
        if dlg.ShowModal() == wx.ID_OK:
            font_files = dlg.GetPaths()
        # Only destroy a dialog after you're done with it.
        dlg.Destroy()
        stats = [0, 0]  # Successful, errors
        if font_files is None:
            return

        maxidx = len(font_files)
        progress_string = _("Fonts imported: {count}")
        progress = wx.ProgressDialog(
            _("Importing fonts..."),
            progress_string.format(count=0),
            maximum=maxidx,
            parent=None,
            style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT,
        )

        for idx, sourcefile in enumerate(font_files):
            basename = os.path.basename(sourcefile)
            destfile = os.path.join(self.context.font_directory, basename)
            # print (f"Source File: {sourcefile}\nTarget: {destfile}")
            try:
                with open(sourcefile, "rb") as f, open(destfile, "wb") as g:
                    while True:
                        block = f.read(1 * 1024 * 1024)  # work by blocks of 1 MB
                        if not block:  # end of file
                            break
                        g.write(block)
                isokay = create_preview_image(self.context, destfile)
                if isokay:
                    stats[0] += 1
                else:
                    # We delete this file again...
                    remove_fontfile(destfile)
                    stats[1] += 1

                keepgoing = progress.Update(
                    idx + 1, progress_string.format(count=idx + 1)
                )
                if not keepgoing:
                    break
            except (OSError, RuntimeError, PermissionError, FileNotFoundError):
                stats[1] += 1
        progress.Destroy()
        wx.MessageBox(
            _(
                "Font-Import completed.\nImported: {ok}\nFailed: {fail}\nTotal: {total}"
            ).format(ok=stats[0], fail=stats[1], total=stats[0] + stats[1]),
            _("Import completed"),
            wx.OK | wx.ICON_INFORMATION,
        )
        # Reload....
        self.on_text_directory(None)

    def on_btn_delete(self, event):
        if self.list_fonts.GetSelection() >= 0:
            font_file = self.fonts[self.list_fonts.GetSelection()]
            full_font_file = os.path.join(self.context.font_directory, font_file)
            if (
                wx.MessageBox(
                    _("Do you really want to delete this font: {font}").format(
                        font=font_file
                    ),
                    _("Confirm"),
                    wx.YES_NO | wx.CANCEL | wx.ICON_WARNING,
                )
                == wx.YES
            ):
                remove_fontfile(full_font_file)
                # Reload dir...
                self.on_text_directory(None)

    def on_combo_webget(self, event):
        idx = self.combo_webget.GetSelection() - 1
        if idx >= 0:
            url = self.webresources[idx]
            if (
                wx.MessageBox(
                    _(
                        "You will be led now to a source in the web, where you can download free fonts.\n"
                        + "Please be respect individual property rights!\nDestination: {url}\n"
                    ).format(url=url)
                    + _(
                        "Unpack the downloaded archive after the download and select the extracted files with help of the 'Import'-Button."
                    ),
                    _("Confirm"),
                    wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
                )
                == wx.YES
            ):
                import webbrowser

                webbrowser.open(url, new=0, autoraise=True)


# end of class FontManager


class HersheyFontManager(MWindow):
    def __init__(self, *args, **kwds):
        super().__init__(551, 234, submenu="", *args, **kwds)
        self.panel = PanelFontManager(self, wx.ID_ANY, context=self.context)
        _icon = wx.NullIcon
        _icon.CopyFromBitmap(icons8_choose_font_50.GetBitmap(resize=25))
        # _icon.CopyFromBitmap(icons8_computer_support_50.GetBitmap())
        self.SetIcon(_icon)
        self.SetTitle(_("Font-Manager"))

    def window_open(self):
        pass

    def window_close(self):
        pass

    def delegates(self):
        yield self.panel

    @staticmethod
    def submenu():
        return ("", "Font-Manager")


def register_hershey_stuff(kernel):
    kernel.root.register("path_attributes/linetext", LineTextPropertPanel)
    buttonsize = int(STD_ICON_SIZE)
    kernel.register(
        "button/config/HersheyFontManager",
        {
            "label": _("Font-Manager"),
            "icon": icons8_choose_font_50,
            "tip": _("Open the vector-font management window."),
            "action": lambda v: kernel.console("window toggle HersheyFontManager\n"),
            "size": buttonsize,
        },
    )
