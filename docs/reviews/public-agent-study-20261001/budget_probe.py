import json
import sys
sys.path.insert(0, '/root/bittensor/ridges/src')
from quarry.llm import ModelRoute, ProxyClient
from quarry.wallet import BudgetExhausted, Wallet

results=[]
for label,code in [('temporary reservation','in_flight_budget_exhausted'),('hard spending cap','budget_exhausted')]:
    wallet=Wallet(0.29, {'probe/model':(0.2,1.2)})
    calls=[]
    def transport(*args):
        calls.append(1)
        if len(calls)==1:
            return 402,json.dumps({'error':{'code':code}})
        return 200,json.dumps({'choices':[{'message':{'content':'recovered'}}],'usage':{'cost':0.001}})
    client=ProxyClient(wallet,{},transport=transport,sleep=lambda _:None)
    try:
        client.complete([{'role':'user','content':'test'}],ModelRoute('probe/model'))
        outcome='recovered'
    except BudgetExhausted:
        outcome='terminal_budget_exhaustion'
    results.append({'scenario':label,'http_status':402,'error_code':code,'outcome':outcome,
                    'transport_calls':len(calls),'wallet_marked_spent':wallet.spent})
print(json.dumps(results,indent=2))
open('/tmp/quarry-budget-probe.json','w').write(json.dumps(results,indent=2)+'\n')
