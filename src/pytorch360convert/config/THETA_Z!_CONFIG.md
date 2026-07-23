# RICOH THETA Z1 - PTP & gphoto2 Configuration Summary

This summary maps standard libgphoto2 commands and vendor PTP property codes (`0xD000` series) for the **RICOH THETA Z1** (Firmware `3.10.2`).

---

## 1. Essential Exposure Controls

| Feature | `gphoto2` Path | PTP Code | Type | Recommended Values / Choices |
| :--- | :--- | :--- | :--- | :--- |
| **Exposure Program** | `/main/capturesettings/expprogram` | `0x500E` | `RADIO` | `0` = Manual (`M`), `1` = Program (`P`), `2` = Aperture (`A`), `3` = Shutter (`S`) |
| **Shutter Speed** | `/main/other/d00f` | `0xD00F` | `MENU` | Vendor Rational integer values (See Shutter Mapping Table below) |
| **ISO Sensitivity** | `/main/other/d826` | `0xD826` | `MENU` | `200`, `250`, `320`, `400`, `500`, `640`, `800`, `1600`, `3200`, `6400` |
| **Exposure Compensation**| `/main/capturesettings/exposurecompensation` | `0x5010` | `RADIO` | `-2000` to `2000` (-2.0 EV to +2.0 EV) |
| **White Balance** | `/main/imgsettings/whitebalance` | `0x5005` | `RADIO` | `0` = Auto, `1` = Daylight, `4` = Tungsten |
| **Image Size** | `/main/imgsettings/imagesize` | `0x5003` | `RADIO` | `6720x3360` (JPEG/RAW) |
| **Capture Delay** | `/main/capturesettings/capturedelay` | `0x5012` | `RADIO` | `0.000s` (Self-timer off) |

---

## 2. Shutter Speed Index Table (`/main/other/d00f`)

Because Ricoh stores shutter speeds using vendor 64-bit PTP rationals, setting values by **Index** using `gphoto2 --set-config-index /main/other/d00f=<INDEX>` is recommended.

| Choice Index | Speed (sec) | Raw `d00f` Integer Value | Typical Use Case |
| :---: | :---: | :---: | :--- |
| **0** | `1/25000` | `107374182400001` | Direct direct sunlight / outdoor high speed |
| **10** | `1/1000` | `1073741824001` | Fast outdoor movement |
| **13** | `1/500` | `536870912001` | Standard outdoor daylight |
| **16** | `1/250` | `2748779069441` | Outdoor overcast |
| **19** | `1/125` | `1374389534721` | Indoor bright lighting |
| **22** | `1/60` | `687194767361` | Indoor standard lighting |
| **25** | `1/30` | `343597383681` | Indoor dim lighting |
| **26** | `1/25` | `257698037761` | Low light static scene |
| **28** | `1/15` | `171798691841` | Very low light (Tripod required) |
| **34** | `1/4` | `42949672961` | Night scene |
| **44** | `1.0s` | `4294967297` | Night long exposure |

---

## 3. Useful CLI Commands

### View Camera Information
```bash
# Verify camera connectivity
gphoto2 --summary

# Dump all available configurable properties
gphoto2 --list-all-config