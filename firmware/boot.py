"""CircuitPython USB setup for the Adafruit MacroPad RP2040 (Macropad HID).

Exposes one keyboard and one 15-button gamepad, both named "Macropad HID".
Each config on the board uses one of them, so switching configs with the
knob never needs a replug. Reconnect USB after changing this file.

The CIRCUITPY drive stays writable from the computer so the web
configurator can save configs. The serial console stays enabled too.
"""

import supervisor
import usb_hid

supervisor.set_usb_identification(manufacturer="Adafruit", product="Macropad HID")
usb_hid.set_interface_name("Macropad HID")

GAMEPAD_REPORT_ID = 4

GAMEPAD_REPORT_DESCRIPTOR = bytes((
    0x05, 0x01,  # Usage Page: Generic Desktop
    0x09, 0x05,  # Usage: Game Pad
    0xA1, 0x01,  # Collection: Application
    0x85, GAMEPAD_REPORT_ID,  # Report ID (needed: shares the interface with the keyboard)
    0x05, 0x09,  #   Usage Page: Button
    0x19, 0x01,  #   Usage Minimum: Button 1
    0x29, 0x0F,  #   Usage Maximum: Button 15
    0x15, 0x00,  #   Logical Minimum: 0
    0x25, 0x01,  #   Logical Maximum: 1
    0x75, 0x01,  #   Report Size: 1 bit
    0x95, 0x0F,  #   Report Count: 15 buttons
    0x81, 0x02,  #   Input: Data, Variable, Absolute
    0x75, 0x01,  #   Report Size: 1 bit
    0x95, 0x01,  #   Report Count: 1 padding bit
    0x81, 0x03,  #   Input: Constant padding
    0xC0,        # End Collection
))

gamepad = usb_hid.Device(
    report_descriptor=GAMEPAD_REPORT_DESCRIPTOR,
    usage_page=0x01,
    usage=0x05,
    report_ids=(GAMEPAD_REPORT_ID,),
    in_report_lengths=(2,),  # 15 button bits plus 1 padding bit.
    out_report_lengths=(0,),
)

# Standard keyboard (Report ID 1, 8-byte report) plus the gamepad.
# boot_device=0 means normal HID, not the BIOS boot-keyboard protocol.
usb_hid.enable((usb_hid.Device.KEYBOARD, gamepad), boot_device=0)
