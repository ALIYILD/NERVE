#!/usr/bin/env python3
"""Current gated proposal entrypoint; historical registration scripts are replay tools."""
import argparse
import json
from pathlib import Path
from nerve_awim.memory_gateway import scientific_substrate_gate as gate
from nerve_awim.memory_gateway import scientific_episode_import as importer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation',choices=('adjudicate','propose'),required=True)
    parser.add_argument('--study-directory',required=True)
    parser.add_argument('--output-directory')
    parser.add_argument('--episode-directory')
    args=parser.parse_args()
    report=json.loads(gate.study._read(Path(args.study_directory)/'report.json'))
    protocol=report['protocol']
    common=(args.study_directory,protocol['expected_digest'],protocol['journal'])
    if args.operation=='adjudicate':
        if not args.output_directory:parser.error('--output-directory required for adjudicate')
        result=gate.publish_adjudication(args.output_directory,*common,**protocol['paths'])
    else:
        if not args.episode_directory:parser.error('--episode-directory required for propose')
        episodes=Path(args.episode_directory).resolve()
        original=json.loads(gate.study._read(episodes/'report.json'))
        checked=importer.run(episodes,original['validation_directory'],original['validation_journal'],original['expected_digest'])
        if gate.study.canonical(original)!=gate.study.canonical(checked):raise ValueError('verified_episode_import_required')
        gateway,_,_,_,reader=importer.pilot._state(episodes/'authority.sqlite')
        store=importer.ExperienceStore(episodes/'experiences.sqlite',gateway,importer.SCOPE)
        result=gate.gated_propose(store,reader,study_directory=common[0],expected_digest=common[1],journal=common[2],
                                 substrate_metadata=gate.study.metadata,**protocol['paths'])
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
