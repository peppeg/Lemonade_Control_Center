# Tested Environment

Lemonade Control Center is designed for Linux inference hosts. The current development and manual testing environment is listed here so users can understand the hardware and software baseline behind the project.

This is not a minimum requirement.

## Primary Development Machine

| Item | Value |
|---|---|
| Workstation | Corsaier AI Workstation 300 |
| Operating system | Fedora Linux 44 Workstation |
| Kernel | 7.0.9-202.fc44.x86_64 |
| Processor | AMD Ryzen AI Max+ 395 with Radeon 8060S |
| Memory | 128 GB unified memory |
| Lemonade Server | 10.5.1 |
| Runtime backend used most often | Lemonade llama.cpp backend |
| Main development workflow | LCC unified FastAPI runtime on localhost, browser from local machine or SSH tunnel |

## Notes

- AMD Strix Halo is the main target hardware during development.
- LCC should run on other Linux hosts, but hardware monitoring depends on what the host exposes through `/proc`, `/sys`, `psutil`, systemd, journal logs, and sensor tooling.
- GPU load and temperature support is currently focused on AMD Linux `sysfs` data.
- Public documentation avoids committing raw probe output because it may include model names, process command lines, local paths, service logs, and host-specific details.
