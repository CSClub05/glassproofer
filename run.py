from glass_spawnproofer.dpi import enable_high_dpi_awareness


if __name__ == "__main__":
    enable_high_dpi_awareness()

    from glass_spawnproofer.gui import main

    raise SystemExit(main())
