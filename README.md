# main.py

## Light schedule script

Run `/home/runner/work/main.py/main.py/light_schedule.py` to set lights to:
- **Day:** cool white at **5500K**
- **Night:** a custom RGB color

Example dry run:

```bash
python light_schedule.py --day-start 07:00 --night-start 20:00 --night-rgb 255,80,0
```

To apply settings in Home Assistant, provide:
- `--ha-url`
- `--ha-token`
- one or more `--entity light.some_light`