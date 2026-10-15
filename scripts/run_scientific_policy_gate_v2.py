#!/usr/bin/env python3
"""Publish a policy-scoped adjudication or register the permitted v3 proposal."""
import argparse
import json
from pathlib import Path
from run_scientific_substrate_calibration_v2 import install_development_file_guard
from nerve_awim.memory_gateway import scientific_policy_gate_v2 as gate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration-directory',required=True)
    parser.add_argument('--directory',required=True)
    parser.add_argument('--proposal',action='store_true')
    args=parser.parse_args()
    protocol=gate._read(Path(args.calibration_directory)/"report.json")["protocol"]
    install_development_file_guard(protocol["bank_directory"])
    print(json.dumps(gate.publish(args.directory,args.calibration_directory,proposal=args.proposal),indent=2,sort_keys=True))


if __name__=='__main__':main()
