from glass_spawnproofer.dpi import enable_high_dpi_awareness


def run() -> int:
    enable_high_dpi_awareness()

    from glass_spawnproofer.gui import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
