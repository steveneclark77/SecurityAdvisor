"""Network-only embedding subprocess; inherits the fixed provider transport."""
import json
import sys
from .analysis_provider import post_json

if __name__=='__main__':
    try:
        result=post_json('/embeddings',json.loads(sys.stdin.buffer.read(256*1024)))
        sys.stdout.write(json.dumps({'vector':result['data'][0]['embedding'],'tokens':result['usage']['total_tokens']}))
    except Exception:
        sys.stderr.write('Embedding request failed.\n')
        sys.exit(1)
