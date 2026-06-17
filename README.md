# main.py

## Light schedule script

Run `python light_schedule.py` to set lights to:
- **Day:** cool white at **5500K**
- **Night:** a custom RGB color

Example dry run:

```bash
python light_schedule.py --day-start 07:00 --night-start 20:00 --day-kelvin 5500 --night-rgb 255,80,0 --night-brightness 30
```

To apply settings in Home Assistant, provide:
- `--ha-url`
- `--ha-token`
- one or more `--entity light.some_light`