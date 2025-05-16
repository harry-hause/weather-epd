import argparse
from display.display_manager import DisplayManager

def main(dev_mode: bool):
    display_manager = DisplayManager(dev_mode=dev_mode)
    display_manager.render_display()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Main application entry point")
    parser.add_argument(
        "--dev", "--dev-mode",
        dest="dev_mode",
        action="store_true",
        help="Enable development mode"
    )
    args = parser.parse_args()

    main(dev_mode=args.dev_mode)
