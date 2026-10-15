"""NERVE command entry point; research features require explicit subcommands."""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog='nerve', description='NERVE research tools')
    parser.add_argument('command', choices=['world-model', 'goal', 'auto-adapt'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command == 'world-model':
        from .world_model.cli import main as world_model_main
        return world_model_main(args.arguments)
    if args.command == 'goal':
        from .goal_learning import main as goal_main
        return goal_main(args.arguments)
    if args.command == 'auto-adapt':
        from .auto_adaptation_goal import main as adaptation_main
        return adaptation_main(args.arguments)


if __name__ == '__main__':
    raise SystemExit(main())
