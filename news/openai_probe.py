"""Isolated synthetic connectivity probe. Never reads application records."""
import json
import math
import sys
import urllib.error
from .analysis_provider import post_json


def probe(models):
    results=[]
    for kind,path,payload in [
        ('analysis','/chat/completions',{'model':models['analysis'],'messages':[{'role':'user','content':'Reply with OK.'}],'max_completion_tokens':16}),
        ('embeddings','/embeddings',{'model':models['embeddings'],'input':'Synthetic SecurityAdvisor connection test','dimensions':256}),
    ]:
        try:
            result=post_json(path,payload)
            if kind=='analysis':
                valid=bool(result['choices'][0]['message']['content'].strip()) and result['choices'][0]['finish_reason']=='stop'
            else:
                vector=result['data'][0]['embedding']
                valid=len(vector)==256 and all(type(v) in (int,float) and math.isfinite(v) for v in vector)
            results.append({'kind':kind,'status':'ok' if valid else 'invalid_response'})
        except urllib.error.HTTPError as exc:
            code={401:'authentication_failed',403:'access_denied',404:'model_unavailable',429:'quota_or_rate_limit'}.get(exc.code,'provider_error')
            results.append({'kind':kind,'status':code})
        except Exception:
            results.append({'kind':kind,'status':'request_failed'})
    return results


if __name__=='__main__':
    try:
        print(json.dumps(probe(json.loads(sys.stdin.buffer.read(4096)))))
    except Exception:
        sys.exit(1)
