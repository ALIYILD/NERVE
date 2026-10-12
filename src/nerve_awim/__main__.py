"""NERVE command entry point; research features require explicit subcommands."""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog='nerve', description='NERVE research tools')
    parser.add_argument('command', choices=['world-model'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == 'world-model':
        from .world_model.cli import main as world_model_main
        return world_model_main(args.arguments)


if __name__ == '__main__':
    raise SystemExit(main())
