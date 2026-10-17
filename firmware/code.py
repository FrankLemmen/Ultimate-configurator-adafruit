# MACROPAD-HID-FW v1
"""Macropad HID firmware for the Adafruit MacroPad RP2040 (product 5128).

Requires CircuitPython for this board and boot.py from this project.
Uses only built-in modules; no files are needed in lib/.

Configs are JSON files in /configs, written by the web configurator
(index.html). Each config is either "keyboard" (key combos) or "hid"
(gamepad buttons 1-12).

Knob turn : previous / next config (loads at once, shown on the display).
Knob push : sleep (LEDs and display off, keys ignored) / wake up.
Dimming   : after dim_minutes without input the LEDs and display go off.
            Keys keep working; any key press or knob turn lights them again.
"""

import json
import os
import time
import board
import digitalio
import displayio
import keypad
import microcontroller
import neopixel_write
import pwmio
import rotaryio
import supervisor
import terminalio
import usb_hid

REVERSE_ENCODER = False
BRIGHTNESS = 0.3          # 0.0 - 1.0, applied to all key LEDs.
BEEP_ON_SAVE = True       # Short beep when a newly saved config is loaded.

CONFIG_DIR = "/configs"
SAVED_FILE = CONFIG_DIR + "/_saved.json"
NUM_KEYS = 12
ENCODER_KEY = 12          # keypad index of the encoder push switch.
NVM_DELAY_MS = 1500       # Wait this long after the last turn before saving.

# --- Persistent state in non-volatile memory ------------------------------
# [0:3] magic, [3] name length, [4:52] active filename,
# [52] stamp length, [53:73] stamp of the last save seen.
NVM_MAGIC = b"MH1"
NVM_SIZE = 73


def nvm_read():
    data = bytes(microcontroller.nvm[0:NVM_SIZE])
    if data[0:3] != NVM_MAGIC:
        return "", ""
    n = min(data[3], 48)
    s = min(data[52], 20)
    try:
        return data[4:4 + n].decode(), data[53:53 + s].decode()
    except UnicodeError:
        return "", ""


def nvm_write(filename, stamp):
    name = filename.encode()[:48]
    st = stamp.encode()[:20]
    data = bytearray(NVM_SIZE)
    data[0:3] = NVM_MAGIC
    data[3] = len(name)
    data[4:4 + len(name)] = name
    data[52] = len(st)
    data[53:53 + len(st)] = st
    if bytes(microcontroller.nvm[0:NVM_SIZE]) != data:
        microcontroller.nvm[0:NVM_SIZE] = data


# --- Ticks (no float allocation in the main loop) -------------------------
TICKS_PERIOD = 1 << 29
TICKS_MASK = TICKS_PERIOD - 1
TICKS_HALF = TICKS_PERIOD // 2


def ticks_diff(a, b):
    return ((a - b + TICKS_HALF) & TICKS_MASK) - TICKS_HALF


# --- Display: 21 x 5 text grid from the built-in font ---------------------
display = board.DISPLAY
font = terminalio.FONT
glyph_w, glyph_h = font.get_bounding_box()[:2]
TEXT_COLS = display.width // glyph_w
TEXT_ROWS = display.height // glyph_h
text_palette = displayio.Palette(2)
text_palette[0] = 0x000000
text_palette[1] = 0xFFFFFF
text_grid = displayio.TileGrid(
    font.bitmap,
    pixel_shader=text_palette,
    width=TEXT_COLS,
    height=TEXT_ROWS,
    tile_width=glyph_w,
    tile_height=glyph_h,
    y=(display.height - TEXT_ROWS * glyph_h) // 2,
)
text_group = displayio.Group()
text_group.append(text_grid)
display.root_group = text_group
shown_lines = None
BLANK = ()


def tile_for(char):
    glyph = font.get_glyph(ord(char)) or font.get_glyph(ord(" "))
    return glyph.tile_index


def show_text(lines):
    """Draw up to TEXT_ROWS lines. Pass the same tuple again to skip work."""
    global shown_lines
    if lines is shown_lines:
        return
    shown_lines = lines
    padded = tuple(lines) + ("",) * (TEXT_ROWS - len(lines))
    for row, line in enumerate(padded[:TEXT_ROWS]):
        line = line[:TEXT_COLS]
        for col in range(TEXT_COLS):
            text_grid[col, row] = tile_for(line[col] if col < len(line) else " ")


def centered(text):
    text = text[:TEXT_COLS]
    return " " * ((TEXT_COLS - len(text)) // 2) + text


def pad(text, width):
    return (text + " " * width)[:width]


# --- Configs ---------------------------------------------------------------
class Config:
    def __init__(self, filename, data):
        self.filename = filename
        self.name = str(data.get("name") or filename[:-5])
        self.keyboard = data.get("mode") == "keyboard"
        self.order = data.get("order", 0)
        if not isinstance(self.order, (int, float)):
            self.order = 0
        dim = data.get("dim_minutes", 0) or 0
        self.dim_ms = int(float(dim) * 60000) if float(dim) > 0 else 0

        keys = data.get("keys") or []
        self.pixels = bytearray(3 * NUM_KEYS)
        self.mods = [0] * NUM_KEYS
        self.codes = [()] * NUM_KEYS
        labels = [""] * NUM_KEYS
        for i in range(NUM_KEYS):
            k = keys[i] if i < len(keys) and isinstance(keys[i], dict) else {}
            r, g, b = parse_color(k.get("color"))
            # The MacroPad NeoPixels expect GRB byte order.
            self.pixels[3 * i] = int(g * BRIGHTNESS)
            self.pixels[3 * i + 1] = int(r * BRIGHTNESS)
            self.pixels[3 * i + 2] = int(b * BRIGHTNESS)
            if self.keyboard:
                mods = 0
                codes = []
                for code in k.get("codes") or ():
                    code = int(code)
                    if 0xE0 <= code <= 0xE7:
                        mods |= 1 << (code - 0xE0)
                    elif 0 < code < 0xE0 and code not in codes and len(codes) < 6:
                        codes.append(code)
                self.mods[i] = mods
                self.codes[i] = tuple(codes)
                labels[i] = str(k.get("label") or "")[:4]
        self.pixels = bytes(self.pixels)

        if self.keyboard:
            mode = "KBD"
            head = pad(self.name, TEXT_COLS - len(mode) - 1) + " " + mode
            c2 = (TEXT_COLS - 4) // 2
            c3 = TEXT_COLS - 4
            rows = [head]
            for r in range(4):
                a, b, c = labels[3 * r:3 * r + 3]
                rows.append(pad(a, c2) + pad(b, c3 - c2) + pad(c, 4))
            self.lines = tuple(rows)
        else:
            self.lines = ("", centered(self.name), "", centered("HID controller"), "")


def parse_color(value):
    try:
        v = str(value).lstrip("#")
        if len(v) == 6:
            v = int(v, 16)
            return (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF
    except ValueError:
        pass
    return 0, 0, 0


def load_configs():
    configs = []
    try:
        names = os.listdir(CONFIG_DIR)
    except OSError:
        return configs
    for fn in names:
        if not fn.endswith(".json") or fn.startswith("_") or fn.startswith("."):
            continue
        try:
            with open(CONFIG_DIR + "/" + fn) as f:
                configs.append(Config(fn, json.load(f)))
        except Exception as err:  # Bad file: skip it, keep the rest working.
            print("Skipping", fn, "-", err)
    configs.sort(key=lambda c: (c.order, c.filename))
    return configs


def read_saved():
    try:
        with open(SAVED_FILE) as f:
            data = json.load(f)
        return str(data.get("stamp", "")), str(data.get("select", ""))
    except Exception:
        return "", ""


def beep():
    try:
        enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
        enable.switch_to_output(value=True)
        tone = pwmio.PWMOut(board.SPEAKER, frequency=1319, duty_cycle=0x8000,
                            variable_frequency=True)
        time.sleep(0.06)
        tone.frequency = 1760
        time.sleep(0.08)
        tone.deinit()
        enable.value = False
        enable.deinit()
    except Exception as err:
        print("Beep failed:", err)


# --- Hardware --------------------------------------------------------------
pins = tuple(getattr(board, "KEY{}".format(i)) for i in range(1, 13))
keys = keypad.Keys(
    pins + (board.BUTTON,),
    value_when_pressed=False,
    pull=True,
    interval=0.010,
    max_events=64,
)
encoder = rotaryio.IncrementalEncoder(board.ROTA, board.ROTB)

pixel_pin = digitalio.DigitalInOut(board.NEOPIXEL)
pixel_pin.direction = digitalio.Direction.OUTPUT
LEDS_OFF = bytes(3 * NUM_KEYS)
shown_pixels = None


def show_pixels(buf):
    global shown_pixels
    if buf is not shown_pixels:
        neopixel_write.neopixel_write(pixel_pin, buf)
        shown_pixels = buf


keyboard = None
gamepad = None
for device in usb_hid.devices:
    if device.usage_page == 0x01 and device.usage == 0x06:
        keyboard = device
    elif device.usage_page == 0x01 and device.usage == 0x05:
        gamepad = device

configs = load_configs()

if not configs or keyboard is None or gamepad is None:
    show_pixels(LEDS_OFF)
    if keyboard is None or gamepad is None:
        show_text(("Macropad HID", "", "Install boot.py,", "then unplug and", "replug USB."))
        print("Keyboard/gamepad not found. Install boot.py, then unplug/replug USB.")
    else:
        show_text(("Macropad HID", "", "No configs found.", "Open index.html", "in Chrome or Edge."))
    while True:  # Saving a config auto-reloads this file.
        time.sleep(1)

# Pick the active config: a fresh save wins, then the remembered one.
active_name, seen_stamp = nvm_read()
saved_stamp, saved_select = read_saved()
just_saved = saved_stamp and saved_stamp != seen_stamp
if just_saved and saved_select:
    active_name = saved_select
active = 0
for i, c in enumerate(configs):
    if c.filename == active_name:
        active = i
        break
cfg = configs[active]
nvm_write(cfg.filename, saved_stamp or seen_stamp)
if just_saved and BEEP_ON_SAVE:
    beep()

# --- Main loop -------------------------------------------------------------
kb_report = bytearray(8)
gp_report = bytearray(2)
ZERO8 = bytes(8)
ZERO2 = bytes(2)

event = keypad.Event()
held = 0                  # Bitmask of keys 0-11 currently pressed.
dirty = True              # A report must be (re)sent.
sleeping = False
lit = True
last_activity = supervisor.ticks_ms()
nvm_pending_at = None
last_gp_sent = 0
last_position = encoder.position


def build_kb_report():
    kb_report[0] = 0
    n = 2
    for i in range(2, 8):
        kb_report[i] = 0
    for i in range(NUM_KEYS):
        if held & (1 << i):
            kb_report[0] |= cfg.mods[i]
            for code in cfg.codes[i]:
                if n < 8:
                    kb_report[n] = code
                    n += 1


def release_all():
    """Send empty reports on both devices (used on config switch / sleep)."""
    global held, dirty
    held = 0
    for dev, rep in ((keyboard, ZERO8), (gamepad, ZERO2)):
        try:
            dev.send_report(rep)
        except OSError:
            pass
    dirty = False


def show_config():
    show_text(cfg.lines)
    show_pixels(cfg.pixels)


show_config()

while True:
    now = supervisor.ticks_ms()
    activity = False

    # One event per loop, so a quick tap still sends press and release.
    if keys.events.get_into(event):
        n = event.key_number
        if n == ENCODER_KEY:
            if event.pressed:
                sleeping = not sleeping
                if sleeping:
                    release_all()
                    lit = False  # Wake-up redraws everything.
                    show_pixels(LEDS_OFF)
                    show_text(BLANK)
                else:
                    activity = True
        elif not sleeping:
            bit = 1 << n
            if event.pressed:
                held |= bit
                activity = True
                dirty = True
            elif held & bit:
                held &= ~bit
                dirty = True

    # Knob turn: previous / next config.
    position = encoder.position
    delta = position - last_position
    if delta:
        last_position = position
        if REVERSE_ENCODER:
            delta = -delta
        if not sleeping:
            release_all()
            active = (active + delta) % len(configs)
            cfg = configs[active]
            nvm_pending_at = now
            activity = True
            lit = False  # Forces a redraw below.

    if not sleeping:
        if activity:
            last_activity = now
            if not lit:
                lit = True
                show_config()
        elif lit and cfg.dim_ms and ticks_diff(now, last_activity) >= cfg.dim_ms:
            lit = False
            show_pixels(LEDS_OFF)
            show_text(BLANK)

        if cfg.keyboard:
            if dirty:
                build_kb_report()
                try:
                    keyboard.send_report(kb_report)
                    dirty = False
                except OSError:
                    pass  # USB busy or enumerating; retry next loop.
        elif dirty or ticks_diff(now, last_gp_sent) >= 1000:
            gp_report[0] = held & 0xFF
            gp_report[1] = (held >> 8) & 0x0F
            try:
                gamepad.send_report(gp_report)
                dirty = False
                last_gp_sent = now
            except OSError:
                pass

    if nvm_pending_at is not None and ticks_diff(now, nvm_pending_at) >= NVM_DELAY_MS:
        nvm_pending_at = None
        nvm_write(cfg.filename, saved_stamp or seen_stamp)

    if sleeping:
        time.sleep(0.01)
