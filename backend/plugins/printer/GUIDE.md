# Printer plugin

Tools: `discover_printers`, `print_stl`, `get_print_status`.

- Discovers OctoPrint/Moonraker/PrusaLink printers on the network.
- Call `discover_printers` first if you don't already know a target printer for this session.
- Verify printer state with `get_print_status` when possible before starting a new print.
- `print_stl` slices and starts the print - only call it once the target file and printer are confirmed.
