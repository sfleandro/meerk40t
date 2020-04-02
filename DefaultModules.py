import os
from base64 import b64encode
from io import BytesIO
from xml.etree.cElementTree import Element, ElementTree, SubElement

from EgvParser import parse_egv
from K40Controller import K40Controller
from Kernel import Spooler, Module, Backend, Device, Pipe
from LaserCommandConstants import *
from LhymicroInterpreter import LhymicroInterpreter
from svgelements import *

MILS_PER_MM = 39.3701


class K40StockDevice(Device):
    def __init__(self, uid=None):
        Device.__init__(self)
        self.uid = uid

    def __repr__(self):
        return "K40StockDevice(uid='%s')" % str(self.uid)

    def initialize(self, kernel, name=''):
        self.kernel = kernel
        self.uid = name
        self.setting(int, 'usb_index', -1)
        self.setting(int, 'usb_bus', -1)
        self.setting(int, 'usb_address', -1)
        self.setting(int, 'usb_serial', -1)
        self.setting(int, 'usb_version', -1)

        self.setting(bool, 'mock', False)
        self.setting(bool, 'quit', False)
        self.setting(int, 'packet_count', 0)
        self.setting(int, 'rejected_count', 0)
        self.setting(int, "buffer_max", 900)
        self.setting(bool, "buffer_limit", True)
        self.setting(bool, "autolock", True)
        self.setting(bool, "autohome", False)
        self.setting(bool, "autobeep", True)
        self.setting(bool, "autostart", True)

        self.setting(str, "board", 'M2')
        self.setting(bool, "rotary", False)
        self.setting(float, "scale_x", 1.0)
        self.setting(float, "scale_y", 1.0)
        self.setting(int, "_stepping_force", None)
        self.setting(float, "_acceleration_breaks", float("inf"))
        self.setting(int, "bed_width", 320)
        self.setting(int, "bed_height", 220)

        self.signal("bed_size", (self.bed_width, self.bed_height))

        self.add_control("Emergency Stop", self.emergency_stop)
        self.add_control("Debug Device", self._start_debugging)

        kernel.add_device(name, self)
        self.open()

    def emergency_stop(self):
        self.spooler.realtime(COMMAND_RESET, 1)

    def open(self):
        self.pipe = K40Controller(self)
        self.interpreter = LhymicroInterpreter(self)
        self.spooler = Spooler(self)
        self.hold_condition = lambda v: self.buffer_limit and len(self.pipe) > self.buffer_max

    def close(self):
        self.spooler.clear_queue()
        self.emergency_stop()
        self.pipe.close()


class K40StockBackend(Module, Backend):
    def __init__(self):
        Module.__init__(self)
        Backend.__init__(self, uid='K40Stock')
        self.autolock = True
        self.mock = True

    def initialize(self, kernel, name='K40Stock'):
        self.kernel = kernel
        self.kernel.add_backend(name, self)
        self.kernel.setting(str, 'device_list', '')
        self.kernel.setting(str, 'device_primary', '')
        for device in kernel.device_list.split(';'):
            self.create_device(device)
            if device == kernel.device_primary:
                self.kernel.activate_device(device)

    def shutdown(self, kernel):
        self.kernel.remove_backend(self.uid)
        self.kernel.remove_module(self.uid)

    def create_device(self, uid):
        device = K40StockDevice()
        device.initialize(self.kernel, uid)


class GRBLEmulator(Module):

    def __init__(self):
        Module.__init__(self)
        self.home_adjust = None
        self.flip_x = 1  # Assumes the GCode is flip_x, -1 is flip, 1 is normal
        self.flip_y = 1  # Assumes the Gcode is flip_y,  -1 is flip, 1 is normal
        self.scale = MILS_PER_MM  # Initially assume mm mode 39.4 mils in an mm. G20 DEFAULT
        self.feed_convert = lambda s: s / (self.scale * 60.0)  # G94 DEFAULT, mm mode
        self.feed_invert = lambda s: self.scale * 60.0 * s
        self.move_mode = 0
        self.home = None
        self.home2 = None
        self.on_mode = 1
        self.read_info = b"Grbl 1.1e ['$' for help]\r\n"
        self.buffer = ''
        self.grbl_set_re = re.compile(r'\$(\d+)=([-+]?[0-9]*\.?[0-9]*)')
        self.code_re = re.compile(r'([A-Za-z])')
        self.float_re = re.compile(r'[-+]?[0-9]*\.?[0-9]*')
        self.settings = {
            0: 10,  # step pulse microseconds
            1: 25,  # step idle delay
            2: 0,  # step pulse invert
            3: 0,  # step direction invert
            4: 0,  # invert step enable pin, boolean
            5: 0,  # invert limit pins, boolean
            6: 0,  # invert probe pin
            10: 255,  # status report options
            11: 0.010,  # Junction deviation, mm
            12: 0.002,  # arc tolerance, mm
            13: 0,  # Report in inches
            20: 0,  # Soft limits enabled.
            21: 0,  # hard limits enabled
            22: 0,  # Homing cycle enable
            23: 0,  # Homing direction invert
            24: 25.000,  # Homing locate feed rate, mm/min
            25: 500.000,  # Homing search seek rate, mm/min
            26: 250,  # Homing switch debounce delay, ms
            27: 1.000,  # Homing switch pull-off distance, mm
            30: 1000,  # Maximum spindle speed, RPM
            31: 0,  # Minimum spindle speed, RPM
            32: 1,  # Laser mode enable, boolean
            100: 250.000,  # X-axis steps per millimeter
            101: 250.000,  # Y-axis steps per millimeter
            102: 250.000,  # Z-axis steps per millimeter
            110: 500.000,  # X-axis max rate mm/min
            111: 500.000,  # Y-axis max rate mm/min
            112: 500.000,  # Z-axis max rate mm/min
            120: 10.000,  # X-axis acceleration, mm/s^2
            121: 10.000,  # Y-axis acceleration, mm/s^2
            122: 10.000,  # Z-axis acceleration, mm/s^2
            130: 200.000,  # X-axis max travel mm.
            131: 200.000,  # Y-axis max travel mm
            132: 200.000  # Z-axis max travel mm.
        }

    def close(self):
        pass

    def open(self):
        pass

    def initialize(self, kernel, name=None):
        Module.initialize(kernel, name)
        self.kernel = kernel
        self.name = name

    def shutdown(self, kernel):
        Module.shutdown(self, kernel)

    def realtime_write(self, bytes_to_write):
        interpreter = self.kernel.device.interpreter
        if bytes_to_write == '?':  # Status report
            # Idle, Run, Hold, Jog, Alarm, Door, Check, Home, Sleep
            if interpreter.state == 0:
                state = 'Idle'
            else:
                state = 'Busy'
            x = self.kernel.device.current_x / self.scale
            y = self.kernel.device.current_y / self.scale
            z = 0.0
            parts = list()
            parts.append(state)
            parts.append('MPos:%f,%f,%f' % (x, y, z))
            f = self.feed_invert(self.kernel.device.interpreter.speed)
            s = self.kernel.device.interpreter.power
            parts.append('FS:%f,%d' % (f, s))
            self.read_info = "<%s>\r\n" % '|'.join(parts)
        elif bytes_to_write == '~':  # Resume.
            interpreter.realtime_command(COMMAND_RESUME)
        elif bytes_to_write == '!':  # Pause.
            interpreter.realtime_command(COMMAND_PAUSE)
        elif bytes_to_write == '\x18':  # Soft reset.
            interpreter.realtime_command(COMMAND_RESET)

    def read(self, size=-1):
        r = self.read_info
        self.read_info = None
        return r

    def write(self, data):
        self.read_info = ''
        if isinstance(data, bytes):
            data = data.decode()
        if '?' in data:
            data = data.replace('?', '')
            self.realtime_write('?')
        if '~' in data:
            data = data.replace('$', '')
            self.realtime_write('~')
        if '!' in data:
            data = data.replace('!', '')
            self.realtime_write('!')
        if '\x18' in data:
            data = data.replace('\x18', '')
            self.realtime_write('\x18')
        self.buffer += data
        while '\b' in self.buffer:
            self.buffer = re.sub('.\b', '', self.buffer, count=1)
            if self.buffer.startswith('\b'):
                self.buffer = re.sub('\b+', '', self.buffer)

        while '\n' in self.buffer:
            pos = self.buffer.find('\n')
            command = self.buffer[0:pos].strip('\r')
            self.buffer = self.buffer[pos + 1:]
            cmd = self.commandline(command)
            if cmd == 0:  # Execute GCode.
                self.read_info += "ok\r\n"
            else:
                self.read_info += "error:%d\r\n" % cmd

    def _tokenize_code(self, code_line):
        code = None
        for x in self.code_re.split(code_line):
            x = x.strip()
            if len(x) == 0:
                continue
            if len(x) == 1 and x.isalpha():
                if code is not None:
                    yield code
                code = [x.lower()]
                continue
            if code is not None:
                code.extend([float(v) for v in self.float_re.findall(x) if len(v) != 0])
                yield code
            code = None
        if code is not None:
            yield code

    def commandline(self, data):
        spooler = self.kernel.device.spooler
        pos = data.find('(')
        commands = {}
        while pos != -1:
            end = data.find(')')
            if 'comment' not in commands:
                commands['comment'] = []
            commands['comment'].append(data[pos + 1:end])
            data = data[:pos] + data[end + 1:]
            pos = data.find('(')
        pos = data.find(';')
        if pos != -1:
            if 'comment' not in commands:
                commands['comment'] = []
            commands['comment'].append(data[pos + 1:])
            data = data[:pos]
        if data.startswith('$'):
            if data == '$':
                self.read_info += "[HLP:$$ $# $G $I $N $x=val $Nx=line $J=line $SLP $C $X $H ~ ! ? ctrl-x]\r\n"
                return 0
            elif data == '$$':
                for s in self.settings:
                    v = self.settings[s]
                    if isinstance(v, int):
                        self.read_info += "$%d=%d\r\n" % (s, v)
                    elif isinstance(v, float):
                        self.read_info += "$%d=%.3f\r\n" % (s, v)
                return 0
            if self.grbl_set_re.match(data):
                settings = list(self.grbl_set_re.findall(data))[0]
                print(settings)
                try:
                    c = self.settings[int(settings[0])]
                except KeyError:
                    return 3
                if isinstance(c, float):
                    self.settings[int(settings[0])] = float(settings[1])
                else:
                    self.settings[int(settings[0])] = int(settings[1])
                return 0
            elif data == '$I':
                pass
            elif data == '$G':
                pass
            elif data == '$N':
                pass
            elif data == '$H':
                spooler.add_command(COMMAND_HOME)
                if self.home_adjust is not None:
                    spooler.add_command(COMMAND_RAPID_MOVE, (self.home_adjust[0], self.home_adjust[1]))
                return 0
                # return 5  # Homing cycle not enabled by settings.
            return 3  # GRBL '$' system command was not recognized or supported.
        if data.startswith('cat'):
            return 2
        for c in self._tokenize_code(data):
            g = c[0]
            if g not in commands:
                commands[g] = []
            if len(c) >= 2:
                commands[g].append(c[1])
            else:
                commands[g].append(None)
        return self.command(commands)

    def command(self, gc):
        spooler = self.kernel.device.spooler
        if 'm' in gc:
            for v in gc['m']:
                if v == 0 or v == 1:
                    spooler.add_command(COMMAND_MODE_DEFAULT_SET)
                    spooler.add_command(COMMAND_WAIT_BUFFER_EMPTY)
                elif v == 2:
                    return 0
                elif v == 30:
                    return 0
                elif v == 3 or v == 4:
                    self.on_mode = True
                elif v == 5:
                    self.on_mode = False
                    spooler.add_command(COMMAND_LASER_OFF)
                elif v == 7:
                    #  Coolant control.
                    pass
                elif v == 8:
                    spooler.add_command(COMMAND_SIGNAL, ('coolant', True))
                elif v == 9:
                    spooler.add_command(COMMAND_SIGNAL, ('coolant', False))
                elif v == 56:
                    pass  # Parking motion override control.
                elif v == 911:
                    pass  # Set TMC2130 holding currents
                elif v == 912:
                    pass  # M912: Set TMC2130 running currents
                else:
                    return 20
            del gc['m']
        if 'g' in gc:
            for v in gc['g']:
                if v is None:
                    return 2
                elif v == 0.0:
                    self.move_mode = 0
                elif v == 1.0:
                    self.move_mode = 1
                elif v == 2.0:  # CW_ARC
                    self.move_mode = 2
                elif v == 3.0:  # CCW_ARC
                    self.move_mode = 3
                elif v == 4.0:  # DWELL
                    t = 0
                    if 'p' in gc:
                        t = float(gc['p'].pop()) / 1000.0
                        if len(gc['p']) == 0:
                            del gc['p']
                    if 's' in gc:
                        t = float(gc['s'].pop())
                        if len(gc['s']) == 0:
                            del gc['s']
                    spooler.add_command(COMMAND_MODE_DEFAULT_SET)
                    spooler.add_command(COMMAND_WAIT, t)
                elif v == 10.0:
                    if 'l' in gc:
                        l = float(gc['l'].pop(0))
                        if len(gc['l']) == 0:
                            del gc['l']
                        if l == 2.0:
                            pass
                        elif l == 20:
                            pass
                elif v == 17:
                    pass  # Set XY coords.
                elif v == 18:
                    return 2  # Set the XZ plane for arc.
                elif v == 19:
                    return 2  # Set the YZ plane for arc.
                elif v == 20.0 or v == 70.0:
                    self.scale = 1000.0  # g20 is inch mode. 1000 mils in an inch
                elif v == 21.0 or v == 71.0:
                    self.scale = 39.3701  # g20 is mm mode. 39.3701 mils in a mm
                elif v == 28.0:
                    spooler.add_command(COMMAND_MODE_DEFAULT_SET)
                    spooler.add_command(COMMAND_HOME)
                    if self.home_adjust is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, (self.home_adjust[0], self.home_adjust[1]))
                    if self.home is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, self.home)
                elif v == 28.1:
                    if 'x' in gc and 'y' in gc:
                        x = gc['x'].pop(0)
                        if len(gc['x']) == 0:
                            del gc['x']
                        y = gc['y'].pop(0)
                        if len(gc['y']) == 0:
                            del gc['y']
                        if x is None:
                            x = 0
                        if y is None:
                            y = 0
                        self.home = (x, y)
                elif v == 28.2:
                    # Run homing cycle.
                    spooler.add_command(COMMAND_MODE_DEFAULT)
                    spooler.add_command(COMMAND_HOME)
                    if self.home_adjust is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, (self.home_adjust[0], self.home_adjust[1]))
                elif v == 28.3:
                    spooler.add_command(COMMAND_MODE_DEFAULT)
                    spooler.add_command(COMMAND_HOME)
                    if self.home_adjust is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, (self.home_adjust[0], self.home_adjust[1]))
                    if 'x' in gc:
                        x = gc['x'].pop(0)
                        if len(gc['x']) == 0:
                            del gc['x']
                        if x is None:
                            x = 0
                        spooler.add_command(COMMAND_RAPID_MOVE, (x, 0))
                    if 'y' in gc:
                        y = gc['y'].pop(0)
                        if len(gc['y']) == 0:
                            del gc['y']
                        if y is None:
                            y = 0
                        spooler.add_command(COMMAND_RAPID_MOVE, (0, y))
                elif v == 30.0:
                    # Goto predefined position. Return to secondary home position.
                    if 'p' in gc:
                        p = float(gc['p'].pop(0))
                        if len(gc['p']) == 0:
                            del gc['p']
                    else:
                        p = None
                    spooler.add_command(COMMAND_MODE_DEFAULT)
                    spooler.add_command(COMMAND_HOME)
                    if self.home_adjust is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, (self.home_adjust[0], self.home_adjust[1]))
                    if self.home2 is not None:
                        spooler.add_command(COMMAND_RAPID_MOVE, self.home2)
                elif v == 30.1:
                    # Stores the current absolute position.
                    if 'x' in gc and 'y' in gc:
                        x = gc['x'].pop(0)
                        if len(gc['x']) == 0:
                            del gc['x']
                        y = gc['y'].pop(0)
                        if len(gc['y']) == 0:
                            del gc['y']
                        if x is None:
                            x = 0
                        if y is None:
                            y = 0
                        self.home2 = (x, y)
                elif v == 38.1:
                    # Touch Plate
                    pass
                elif v == 38.2:
                    # Straight Probe
                    pass
                elif v == 38.3:
                    # Prope towards workpiece
                    pass
                elif v == 38.4:
                    # Probe away from workpiece, signal error
                    pass
                elif v == 38.5:
                    # Probe away from workpiece.
                    pass
                elif v == 40.0:
                    pass  # Compensation Off
                elif v == 43.1:
                    pass  # Dynamic tool Length offsets
                elif v == 49:
                    # Cancel tool offset.
                    pass  # Dynamic tool length offsets
                elif v == 53:
                    pass  # Move in Absolute Coordinates
                elif 54 <= v <= 59:
                    # Fixure offset 1-6, G10 and G92
                    system = v - 54
                    pass  # Work Coordinate Systems
                elif v == 61:
                    # Exact path control mode. GRBL required
                    pass
                elif v == 80:
                    # Motion mode cancel. Canned cycle.
                    pass
                elif v == 90.0:
                    spooler.add_command(COMMAND_SET_ABSOLUTE)
                elif v == 91.0:
                    spooler.add_command(COMMAND_SET_INCREMENTAL)
                elif v == 91.1:
                    # Offset mode for certain cam. Incremental distance mode for arcs.
                    pass  # ARC IJK Distance Modes # TODO Implement
                elif v == 92:
                    # Change the current coords without moving.
                    pass  # Coordinate Offset TODO: Implement
                elif v == 92.1:
                    # Clear Coordinate offset set by 92.
                    pass  # Clear Coordinate offset TODO: Implement
                elif v == 93.0:
                    # Feed Rate in Minutes / Unit
                    self.feed_convert = lambda s: (self.scale * 60.0) / s
                    self.feed_invert = lambda s: (self.scale * 60.0) / s
                elif v == 94.0:
                    # Feed Rate in Units / Minute
                    self.feed_convert = lambda s: s / (self.scale * 60.0)
                    self.feed_invert = lambda s:  s * (self.scale * 60.0)
                    # units to mm, seconds to minutes.
                else:
                    return 20  # Unsupported or invalid g-code command found in block.
            del gc['g']
        if 'comment' in gc:
            del gc['comment']
        if 'f' in gc:  # Feed_rate
            for v in gc['f']:
                if v is None:
                    return 2  # Numeric value format is not valid or missing an expected value.
                feed_rate = self.feed_convert(v)
                spooler.add_command(COMMAND_SET_SPEED, feed_rate)
            del gc['f']
        if 's' in gc:
            for v in gc['s']:
                if v is None:
                    return 2 # Numeric value format is not valid or missing an expected value.
                if 0.0 < v <= 1.0:
                    v *= 1000  # numbers between 0-1 are taken to be in range 0-1.
                spooler.add_command(COMMAND_SET_POWER, v)
            del gc['s']
        if 'x' in gc or 'y' in gc:
            if self.move_mode == 0:
                spooler.add_command(COMMAND_LASER_OFF)
                spooler.add_command(COMMAND_MODE_DEFAULT)
            elif self.move_mode == 1 or self.move_mode == 2 or self.move_mode == 3:
                spooler.add_command(COMMAND_MODE_COMPACT_SET)
            if 'x' in gc:
                x = gc['x'].pop(0)
                if x is None:
                    x = 0
                else:
                    x *= self.scale * self.flip_x
                if len(gc['x']) == 0:
                    del gc['x']
            else:
                x = 0
            if 'y' in gc:
                y = gc['y'].pop(0)
                if y is None:
                    y = 0
                else:
                    y *= self.scale * self.flip_y
                if len(gc['y']) == 0:
                    del gc['y']
            else:
                y = 0
            if self.move_mode == 0:
                spooler.add_command(COMMAND_LASER_OFF)
                spooler.add_command(COMMAND_MOVE, (x, y))
            elif self.move_mode == 1:
                if self.on_mode:
                    spooler.add_command(COMMAND_LASER_ON)
                spooler.add_command(COMMAND_MOVE, (x, y))
            elif self.move_mode == 2:
                spooler.add_command(COMMAND_MOVE, (x, y))  # TODO: Implement CW_ARC
            elif self.move_mode == 3:
                spooler.add_command(COMMAND_MOVE, (x, y))  # TODO: Implement CCW_ARC
        return 0


class Console(Module, Pipe):
    def __init__(self):
        Module.__init__(self)
        self.delegate = None
        self.read_info = None
        self.buffer = ''

    def initialize(self, kernel, name=None):
        Module.initialize(kernel, name)
        self.kernel = kernel
        self.name = name

    def shutdown(self, kernel):
        Module.shutdown(self, kernel)

    def close(self):
        pass

    def open(self):
        pass

    def realtime_write(self, bytes_to_write):
        if self.delegate is not None:
            self.delegate.realtime_write(bytes_to_write)

    def read(self, size=-1):
        if self.delegate is not None:
            return self.delegate.read(size)
        r = self.read_info
        self.read_info = None
        return r

    def write(self, data):
        if data == 'exit\n':  # process first to quit a delegate.
            self.delegate = None
            self.read_info += "Exited Mode.\n"
            return
        if self.delegate is not None:
            self.delegate.write(data)
        self.read_info = ''
        if isinstance(data, bytes):
            data = data.decode()
        self.buffer += data
        while '\n' in self.buffer:
            pos = self.buffer.find('\n')
            command = self.buffer[0:pos].strip('\r')
            self.buffer = self.buffer[pos + 1:]
            self.commandline(command)

    def commandline(self, command):
        if command == "grbl":
            self.delegate = self.kernel.modules['GrblEmulator']
            self.read_info += "GRBL Mode.\n"
            return
        elif command == "set":
            for attr in dir(self.kernel.device):
                v = getattr(self.kernel.device, attr)
                if attr.startswith('_') or not isinstance(v, (int, float, str, bool)):
                    continue
                self.read_info += '"%s" := %s\n' % (attr, str(v))
        elif command.startswith('set '):
            var = list(command.split(' '))
            if len(var) >= 3:
                attr = var[1]
                value = var[2]
                if hasattr(self.kernel.device, attr):
                    v = getattr(self.kernel.device, attr)
                    if isinstance(v, bool):
                        if value == 'False' or value == 'false' or value == 0:
                            setattr(self.kernel.device, attr, False)
                        else:
                            setattr(self.kernel.device, attr, True)
                    elif isinstance(v, int):
                        setattr(self.kernel.device, attr, int(value))
                    elif isinstance(v, float):
                        setattr(self.kernel.device, attr, float(value))
                    elif isinstance(v, str):
                        setattr(self.kernel.device, attr, str(value))
        elif command == 'control':
            for control_name in self.kernel.controls:
                self.read_info += '%s\n' % control_name
        elif command.startswith('control '):
            control_name = command[len('control '):]
            if control_name in self.kernel.controls:
                self.kernel.device.execute(control_name)
                self.read_info += "Executed '%s'\n" % control_name
            else:
                self.read_info += "Control '%s' not found.\n" % control_name
        elif command == 'refresh':
            self.kernel.signal('refresh_scene')
            self.read_info += "Refreshed.\n"
        else:
            self.read_info += "Error.\n"


class SVGWriter:
    def __init__(self):
        self.kernel = None

    def initialize(self, kernel, name=None):
        self.kernel = kernel
        kernel.add_saver("SVGWriter", self)

    def shutdown(self, kernel):
        self.kernel = None
        del kernel.modules['SVGWriter']

    def save_types(self):
        yield "Scalable Vector Graphics", "svg", "image/svg+xml"

    def versions(self):
        yield 'default'

    def create_svg_dom(self):
        root = Element(SVG_NAME_TAG)
        root.set(SVG_ATTR_VERSION, SVG_VALUE_VERSION)
        root.set(SVG_ATTR_XMLNS, SVG_VALUE_XMLNS)
        root.set(SVG_ATTR_XMLNS_LINK, SVG_VALUE_XLINK)
        root.set(SVG_ATTR_XMLNS_EV, SVG_VALUE_XMLNS_EV)
        root.set("xmlns:meerK40t", "https://github.com/meerk40t/meerk40t/wiki/Namespace")
        # Native unit is mils, these must convert to mm and to px
        mils_per_mm = 39.3701
        mils_per_px = 1000.0 / 96.0
        px_per_mils = 96.0 / 1000.0
        if self.kernel.device is None:
            self.kernel.setting(int, "bed_width", 320)
            self.kernel.setting(int, "bed_height", 220)
            mm_width = self.kernel.bed_width
            mm_height = self.kernel.bed_height
        else:
            self.kernel.device.setting(int, "bed_width", 320)
            self.kernel.device.setting(int, "bed_height", 220)
            mm_width = self.kernel.device.bed_width
            mm_height = self.kernel.device.bed_height
        root.set(SVG_ATTR_WIDTH, '%fmm' % mm_width)
        root.set(SVG_ATTR_HEIGHT, '%fmm' % mm_height)
        px_width = mm_width * mils_per_mm * px_per_mils
        px_height = mm_height * mils_per_mm * px_per_mils

        viewbox = '%d %d %d %d' % (0, 0, round(px_width), round(px_height))
        scale = 'scale(%f)' % px_per_mils
        root.set(SVG_ATTR_VIEWBOX, viewbox)
        elements = self.kernel.elements
        for element in elements:
            if isinstance(element, Path):
                subelement = SubElement(root, SVG_TAG_PATH)
                subelement.set(SVG_ATTR_DATA, element.d())
                subelement.set(SVG_ATTR_TRANSFORM, scale)
                for key, val in element.values.items():
                    if key in ('stroke-width', 'fill-opacity', 'speed',
                               'overscan', 'power', 'id', 'passes',
                               'raster_direction', 'raster_step', 'd_ratio'):
                        subelement.set(key, str(val))
            elif isinstance(element, SVGText):
                subelement = SubElement(root, SVG_TAG_TEXT)
                subelement.text = element.text
                t = Matrix(element.transform)
                t *= scale
                subelement.set('transform', 'matrix(%f, %f, %f, %f, %f, %f)' % (t.a, t.b, t.c, t.d, t.e, t.f))
                for key, val in element.values.items():
                    if key in ('stroke-width', 'fill-opacity', 'speed',
                               'overscan', 'power', 'id', 'passes',
                               'raster_direction', 'raster_step', 'd_ratio',
                               'font-family', 'font-size', 'font-weight'):
                        subelement.set(key, str(val))
            else:  # Image.
                subelement = SubElement(root, SVG_TAG_IMAGE)
                stream = BytesIO()
                element.image.save(stream, format='PNG')
                png = b64encode(stream.getvalue()).decode('utf8')
                subelement.set('xlink:href', "data:image/png;base64,%s" % (png))
                subelement.set(SVG_ATTR_X, '0')
                subelement.set(SVG_ATTR_Y, '0')
                subelement.set(SVG_ATTR_WIDTH, str(element.image.width))
                subelement.set(SVG_ATTR_HEIGHT, str(element.image.height))
                subelement.set(SVG_ATTR_TRANSFORM, scale)
                t = Matrix(element.transform)
                t *= scale
                subelement.set('transform', 'matrix(%f, %f, %f, %f, %f, %f)' % (t.a, t.b, t.c, t.d, t.e, t.f))
                for key, val in element.values.items():
                    if key in ('stroke-width', 'fill-opacity', 'speed',
                               'overscan', 'power', 'id', 'passes',
                               'raster_direction', 'raster_step', 'd_ratio'):
                        subelement.set(key, str(val))
            stroke = str(element.stroke)
            fill = str(element.fill)
            if stroke == 'None':
                stroke = SVG_VALUE_NONE
            if fill == 'None':
                fill = SVG_VALUE_NONE
            subelement.set(SVG_ATTR_STROKE, stroke)
            subelement.set(SVG_ATTR_FILL, fill)
        return ElementTree(root)

    def save(self, f, version='default'):
        tree = self.create_svg_dom()
        tree.write(f)


class SVGLoader:
    def __init__(self):
        self.kernel = None

    def initialize(self, kernel, name=None):
        self.kernel = kernel
        kernel.setting(int, "bed_width", 320)
        kernel.setting(int, "bed_height", 220)
        kernel.add_loader("SVGLoader", self)

    def shutdown(self, kernel):
        self.kernel = None
        del kernel.modules['SVGLoader']

    def load_types(self):
        yield "Scalable Vector Graphics", ("svg",), "image/svg+xml"

    def load(self, pathname):
        elements = []
        basename = os.path.basename(pathname)
        scale_factor = 1000.0 / 96.0
        svg = SVG.parse(source=pathname,
                        width='%fmm' % (self.kernel.bed_width),
                        height='%fmm' % (self.kernel.bed_height),
                        ppi=96.0,
                        transform='scale(%f)' % scale_factor)
        for element in svg.elements():
            if isinstance(element, SVGText):
                elements.append(element)
            elif isinstance(element, Path):
                elements.append(element)
            elif isinstance(element, Shape):
                e = Path(element)
                e.reify()  # In some cases the shape could not have reified, the path must.
                elements.append(e)
            elif isinstance(element, SVGImage):
                try:
                    element.load(os.path.dirname(pathname))
                    if element.image is not None:
                        elements.append(element)
                except OSError:
                    pass
        return elements, pathname, basename


class EgvLoader:
    def __init__(self):
        self.kernel = None

    def initialize(self, kernel, name=None):
        self.kernel = kernel
        kernel.add_loader("EGVLoader", self)

    def shutdown(self, kernel):
        self.kernel = None
        del kernel.modules['EgvLoader']

    def load_types(self):
        yield "Engrave Files", ("egv",), "application/x-egv"

    def load(self, pathname):
        elements = []
        basename = os.path.basename(pathname)

        for event in parse_egv(pathname):
            path = event['path']
            if len(path) > 0:
                elements.append(path)
                if 'speed' in event:
                    path.values['speed'] = event['speed']
            if 'raster' in event:
                raster = event['raster']
                image = raster.get_image()
                if image is not None:
                    elements.append(image)
                    if 'speed' in event:
                        image.values['speed'] = event['speed']
        return elements, pathname, basename


class ImageLoader:
    def __init__(self):
        self.kernel = None

    def initialize(self, kernel, name=None):
        self.kernel = kernel
        kernel.add_loader("ImageLoader", self)

    def shutdown(self, kernel):
        self.kernel = None
        del kernel.modules['ImageLoader']

    def load_types(self):
        yield "Portable Network Graphics", ("png",), "image/png"
        yield "Bitmap Graphics", ("bmp",), "image/bmp"
        yield "EPS Format", ("eps",), "image/eps"
        yield "GIF Format", ("gif",), "image/gif"
        yield "Icon Format", ("ico",), "image/ico"
        yield "JPEG Format", ("jpg", "jpeg", "jpe"), "image/jpeg"
        yield "Webp Format", ("webp",), "image/webp"

    def load(self, pathname):
        basename = os.path.basename(pathname)

        image = SVGImage({'href': pathname, 'width': "100%", 'height': "100%"})
        image.load()
        return [image], pathname, basename


class DxfLoader:
    def __init__(self):
        self.kernel = None

    def initialize(self, kernel, name=None):
        self.kernel = kernel
        kernel.add_loader("DxfLoader", self)

    def shutdown(self, kernel):
        self.kernel = None
        del kernel.modules['DxfLoader']

    def load_types(self):
        yield "Drawing Exchange Format", ("dxf",), "image/vnd.dxf"

    def load(self, pathname):
        """"
        Load dxf content. Requires ezdxf which tends to also require Python 3.6 or greater.

        Dxf data has an origin point located in the lower left corner. +y -> top
        """
        import ezdxf

        basename = os.path.basename(pathname)
        dxf = ezdxf.readfile(pathname)
        elements = []
        for entity in dxf.entities:

            try:
                entity.transform_to_wcs(entity.ocs())
            except AttributeError:
                pass
            if entity.dxftype() == 'CIRCLE':
                element = Circle(center=entity.dxf.center, r=entity.dxf.radius)
            elif entity.dxftype() == 'ARC':
                circ = Circle(center=entity.dxf.center,
                              r=entity.dxf.radius)
                element = Path(circ.arc_angle(Angle.degrees(entity.dxf.start_angle),
                                              Angle.degrees(entity.dxf.end_angle)))
            elif entity.dxftype() == 'ELLIPSE':
                # TODO: needs more math, axis is vector, ratio is to minor.
                element = Ellipse(center=entity.dxf.center,
                                  # major axis is vector
                                  # ratio is the ratio of major to minor.
                                  start_point=entity.start_point,
                                  end_point=entity.end_point,
                                  start_angle=entity.dxf.start_param,
                                  end_angle=entity.dxf.end_param)
            elif entity.dxftype() == 'LINE':
                #  https://ezdxf.readthedocs.io/en/stable/dxfentities/line.html
                element = SimpleLine(x1=entity.dxf.start[0], y1=entity.dxf.start[1],
                                     x2=entity.dxf.end[0], y2=entity.dxf.end[1])
            elif entity.dxftype() == 'LWPOLYLINE':
                # https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html
                points = list(entity)
                if entity.closed:
                    element = Polygon(*[(p[0], p[1]) for p in points])
                else:
                    element = Polyline(*[(p[0], p[1]) for p in points])
                # TODO: If bulges are defined they should be included as arcs.
            elif entity.dxftype() == 'HATCH':
                # https://ezdxf.readthedocs.io/en/stable/dxfentities/hatch.html
                element = Path()
                if entity.bgcolor is not None:
                    Path.fill = Color(entity.bgcolor)
                for p in entity.paths:
                    if p.path_type_flags & 2:
                        for v in p.vertices:
                            element.line(v[0], v[1])
                        if p.is_closed:
                            element.closed()
                    else:
                        for e in p.edges:
                            if type(e) == "LineEdge":
                                # https://ezdxf.readthedocs.io/en/stable/dxfentities/hatch.html#ezdxf.entities.LineEdge
                                element.line(e.start, e.end)
                            elif type(e) == "ArcEdge":
                                # https://ezdxf.readthedocs.io/en/stable/dxfentities/hatch.html#ezdxf.entities.ArcEdge
                                circ = Circle(center=e.center,
                                              radius=e.radius, )
                                element += circ.arc_angle(Angle.degrees(e.start_angle), Angle.degrees(e.end_angle))
                            elif type(e) == "EllipseEdge":
                                # https://ezdxf.readthedocs.io/en/stable/dxfentities/hatch.html#ezdxf.entities.EllipseEdge
                                element += Arc(radius=e.radius,
                                               start_angle=Angle.degrees(e.start_angle),
                                               end_angle=Angle.degrees(e.end_angle),
                                               ccw=e.is_counter_clockwise)
                            elif type(e) == "SplineEdge":
                                # https://ezdxf.readthedocs.io/en/stable/dxfentities/hatch.html#ezdxf.entities.SplineEdge
                                if e.degree == 3:
                                    for i in range(len(e.knot_values)):
                                        control = e.control_values[i]
                                        knot = e.knot_values[i]
                                        element.quad(control, knot)
                                elif e.degree == 4:
                                    for i in range(len(e.knot_values)):
                                        control1 = e.control_values[2 * i]
                                        control2 = e.control_values[2 * i + 1]
                                        knot = e.knot_values[i]
                                        element.cubic(control1, control2, knot)
                                else:
                                    for i in range(len(e.knot_values)):
                                        knot = e.knot_values[i]
                                        element.line(knot)
            elif entity.dxftype() == 'IMAGE':
                bottom_left_position = entity.insert
                size = entity.image_size
                imagedef = entity.image_def_handle
                element = SVGImage(href=imagedef.filename,
                                   x=bottom_left_position[0],
                                   y=bottom_left_position[1] - size[1],
                                   width=size[0],
                                   height=size[1])
            elif entity.dxftype() == 'MTEXT':
                insert = entity.dxf.insert
                element = SVGText(x=insert[0], y=insert[1], text=entity.dxf.text)
            elif entity.dxftype() == 'TEXT':
                insert = entity.dxf.insert
                element = SVGText(x=insert[0], y=insert[1], text=entity.dxf.text)
            elif entity.dxftype() == 'POLYLINE':
                if entity.is_2d_polyline:
                    if entity.is_closed:
                        element = Polygon([(p[0], p[1]) for p in entity.points()])
                    else:
                        element = Polyline([(p[0], p[1]) for p in entity.points()])
            elif entity.dxftype() == 'SOLID' or entity.dxftype() == 'TRACE':
                # https://ezdxf.readthedocs.io/en/stable/dxfentities/solid.html
                element = Path()
                element.move((entity[0][0], entity[0][1]))
                element.line((entity[1][0], entity[1][1]))
                element.line((entity[2][0], entity[2][1]))
                element.line((entity[3][0], entity[3][1]))
                element.closed()
                element.fill = Color('Black')
            elif entity.dxftype() == 'SPLINE':
                element = Path()
                # TODO: Additional research.
                # if entity.dxf.degree == 3:
                #     element.move(entity.knots[0])
                #     print(entity.dxf.n_control_points)
                #     for i in range(1, entity.dxf.n_knots):
                #         print(entity.knots[i])
                #         print(entity.control_points[i-1])
                #         element.quad(
                #             entity.control_points[i-1],
                #             entity.knots[i]
                #         )
                # elif entity.dxf.degree == 4:
                #     element.move(entity.knots[0])
                #     for i in range(1, entity.dxf.n_knots):
                #         element.quad(
                #             entity.control_points[2 * i - 2],
                #             entity.control_points[2 * i - 1],
                #             entity.knots[i]
                #         )
                # else:
                element.move(entity.control_points[0])
                for i in range(1, entity.dxf.n_control_points):
                    element.line(entity.control_points[i])
                if entity.closed:
                    element.closed()
            else:
                continue
                # Might be something unsupported.
            if entity.rgb is not None:
                element.stroke = Color(entity.rgb)
            else:
                element.stroke = Color('black')
            element.transform.post_scale(MILS_PER_MM, -MILS_PER_MM)
            element.transform.post_translate_y(self.kernel.bed_height * MILS_PER_MM)
            if isinstance(element, SVGText):
                elements.append(element)
            else:
                elements.append(abs(Path(element)))

        return elements, pathname, basename
