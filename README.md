# Macropad HID

Turns an [Adafruit MacroPad RP2040](https://www.adafruit.com/product/5128) into a button box for gaming and sim racing that you set up from a web page. You don't need to write any code or program it with the knob.

- Store as many **configs** on the MacroPad as you like and switch between them with the knob.
- Each config is either a **Keyboard** (each key sends a key or shortcut) or an **HID controller** (each key is a game-controller button).
- Give each key its own LED color: 10 presets or any custom color.
- In Keyboard mode, give each key a 4-letter name. The MacroPad display shows those names in a 3 × 4 grid.
- The MacroPad shows up on your computer as **Macropad HID**.

## What's in this folder

| File | Purpose |
|---|---|
| `firmware/boot.py` | Sets up the USB keyboard and game controller named "Macropad HID". Runs once when the MacroPad is plugged in. |
| `firmware/code.py` | Runs on the MacroPad: reads the keys and knob, loads configs, drives the LEDs, display and speaker. |
| `configurator/index.html` | The web configurator. Open it in Chrome or Edge. |

## Installation

1. Install CircuitPython for the [MacroPad RP2040](https://circuitpython.org/board/adafruit_macropad_rp2040/) (10.x recommended).
2. Back up anything already on the `CIRCUITPY` drive. Then copy **`firmware/boot.py`** and **`firmware/code.py`** to the root of the drive. You don't need anything in `lib/`.
3. Optional: also copy **`configurator/index.html`** to the drive, so the configurator always travels with your MacroPad.
4. **Unplug the MacroPad and plug it back in.** `boot.py` only runs at power-up.
5. Open `index.html` in **Google Chrome** or **Microsoft Edge**, on Windows or macOS. Safari and Firefox can't save to a drive from a web page.

## Using the configurator

1. Click **Select drive** and choose the **CIRCUITPY** drive. Allow the page to view and edit files when the browser asks. Next time you can use **Reconnect to last drive**.
2. If there are no configs yet, the **setup wizard** starts:
   1. Choose **Keyboard** or **HID controller**.
   2. Enter a name (up to 16 characters). It's shown on the MacroPad display.
   3. Choose when the lights dim: never, or after 1–60 minutes (or any number you type).
3. In the **editor** you see the MacroPad with its display, knob and 12 keys. Click a key to edit it:
   - **LED color:** one of the 10 presets, the color picker, or a hex code like `#FF5000`. **Use on all keys** copies the color to every key. "Off" turns that key's LED off.
   - **Shortcut** (Keyboard mode): click **Record shortcut** and press the key or combination, for example Ctrl+Shift+F5. Your computer catches some combinations before the page sees them, such as Ctrl+W, Alt+Tab and Win+L. Use **Add keys by hand** for those.
   - **Display name** (Keyboard mode): up to 4 characters. It's filled in from the shortcut if you leave it empty.
   - In **HID controller** mode, key *n* is game-controller button *n*. Bind the buttons in your game's controls menu.
4. Click **Save to MacroPad** (or press Ctrl+S / Cmd+S). The page plays a short chime. The MacroPad restarts for about a second, loads the saved config and **beeps**.
5. On the overview you can **edit**, **duplicate**, **delete** (with confirmation) and **reorder** (↑ ↓) configs. The order is the order the knob steps through them.

> Saving makes the MacroPad restart for about a second, so don't save in the middle of a race.

## Using the MacroPad

| Action | What happens |
|---|---|
| **Turn the knob** | Loads the next or previous config. The display shows its name and mode, and the LEDs change straight away. The MacroPad remembers the last config, even after you unplug it. |
| **Push the knob** | Sleep: all LEDs and the display turn off and the keys do nothing. Push again to wake up. |
| **Dimming** | After the config's dim time without a key press, the LEDs and display turn off. The keys **keep working**. A key press or knob turn turns the lights back on until the next timeout. |

What the display shows:

```
 Keyboard mode                    HID controller mode
 ┌─────────────────────┐          ┌─────────────────────┐
 │ACC Race          KBD│          │                     │
 │PIT     LGHT    WIPE │          │      GT3 Box        │
 │TC-     MFD     TC+  │          │                     │
 │ABS-    RAD     ABS+ │          │   HID controller    │
 │MAP-    IGN     MAP+ │          │                     │
 └─────────────────────┘          └─────────────────────┘
```

## Keyboard or HID controller?

- **HID controller** is best for sim racing. Game-controller buttons never clash with keyboard shortcuts or chat, and most sims read them even when another window (SimHub, Discord) has focus. Bind them like wheel buttons.
- **Keyboard** is useful for apps and games that only accept keys, such as OBS hotkeys, push-to-talk or the Windows/Mac media controls you have bound to keys. Shortcuts use key **positions**, so they behave the same on QWERTY, AZERTY and other layouts.

The MacroPad always appears as both a keyboard and a game controller, so you can switch between the two kinds of config without replugging.

## Config files

Configs are stored on the MacroPad in the **`configs`** folder, one JSON file per config. You normally don't edit them by hand.

```json
{
  "version": 1,
  "name": "ACC Race",
  "mode": "keyboard",
  "dim_minutes": 5,
  "order": 10,
  "keys": [
    { "color": "#FF0000", "label": "PIT", "codes": [224, 58], "combo": "Ctrl+F1" }
  ]
}
```

- `mode`: `"keyboard"` or `"hid"`.
- `dim_minutes`: `0` means never dim.
- `codes`: USB HID key codes. 224–231 are Ctrl, Shift, Alt and Win/Cmd, left and right. `combo` is only for display.
- `configs/_saved.json` is written after every save. It tells the MacroPad which config to load and that it should beep.

Settings at the top of `firmware/code.py`:

| Setting | Default | Meaning |
|---|---|---|
| `BRIGHTNESS` | `0.3` | LED brightness, from 0.0 to 1.0 |
| `BEEP_ON_SAVE` | `True` | Beep when a newly saved config is loaded |
| `REVERSE_ENCODER` | `False` | Swaps the knob direction |

## Troubleshooting

- **"The MacroPad drive is read-only" when saving:**
  - Allow editing when the browser asks; click **Try again** in the popup.
  - Some other MacroPad projects install a `boot.py` that locks the drive unless a key is held while plugging in. Hold that key (often key 1) while plugging in, then replace `boot.py` with the one from this project.
  - Unplug and replug. If the board is in *safe mode*, press the reset button.
  - Make sure the drive isn't full.
  - On a Mac: eject CIRCUITPY, replug, then reconnect.
- **The display says "Install boot.py":** `boot.py` is missing or the MacroPad wasn't replugged after copying it.
- **The display says "No configs found":** open the configurator and create a config.
- **Windows shows an old name or button layout:** Windows remembers controllers it has seen. Unplug the MacroPad. In Device Manager, choose *View → Show hidden devices* and uninstall the old MacroPad entries, then plug it back in. Don't uninstall your normal keyboard or mouse.
- **The page says the browser can't open drives:** use Chrome or Edge.
- **A config doesn't show up on the MacroPad:** its file may be damaged. The configurator lists unreadable files at the top of the overview, and the serial console (for example in [Mu](https://codewith.mu/)) prints why they were skipped.
- **Test the controller:** on Windows, press `Win+R`, enter `joy.cpl`, select **Macropad HID** and open **Properties**.

## Credits

Made by **Frank Lemmen**, with the help of [Claude Code](https://claude.com/claude-code). Based on the MarcoPad gamepad firmware and ideas from [Macropad Hotkeys](https://github.com/deckerego/Macropad_Hotkeys).
