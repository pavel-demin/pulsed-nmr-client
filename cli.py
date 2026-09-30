import sys

from app.cli_app import CliApp


def main():
    sys.exit(CliApp(sys.argv[1:]).run())


if __name__ == "__main__":
    main()
