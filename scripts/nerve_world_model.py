"""Launch the opt-in NERVE world-model CLI from a source checkout."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from nerve_awim.world_model.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
