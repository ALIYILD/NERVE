#!/usr/bin/env python3
"""Register finite scientific hypotheses without inference or promotion."""
import argparse
import json
from nerve_awim.memory_gateway.scientific_candidate_registration import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--episode-directory', required=True)
    parser.add_argument('--disable-research-agent', action='store_true')
    parser.add_argument('--max-proposals', type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(args.directory, args.episode_directory,
                         research_agent_enabled=not args.disable_research_agent,
                         max_proposals=args.max_proposals), sort_keys=True, indent=2))


if __name__ == '__main__': main()
