import asyncio, hashlib, hmac, json, pathlib
from agentweave import GrpcA2ALifecycleClient, PushNotificationReceiver

class FakeCodec:
    def build(self,name,payload): return {'type':name,**payload}
    def to_dict(self,message): return message

class FakeStub:
    def __init__(self,channel): self.channel=channel; self.calls=[]
    async def SendMessage(self,request,timeout=None): self.calls.append(('send',request)); return {'task':{'id':'t1','status':{'state':'TASK_STATE_COMPLETED'}}}
    def SendStreamingMessage(self,request,timeout=None):
        self.calls.append(('stream',request))
        async def gen():
            yield {'task':{'id':'t2'}}
            yield {'statusUpdate':{'taskId':'t2','status':{'state':'TASK_STATE_COMPLETED'}}}
        return gen()
    def SubscribeToTask(self,request,timeout=None):
        self.calls.append(('subscribe',request))
        async def gen(): yield {'statusUpdate':{'taskId':request['id'],'status':{'state':'TASK_STATE_WORKING'}}}
        return gen()
    async def GetTask(self,request,timeout=None): self.calls.append(('get',request)); return {'id':request['id'],'status':{'state':'TASK_STATE_COMPLETED'}}
    async def ListTasks(self,request,timeout=None): self.calls.append(('list',request)); return {'tasks':[],'nextPageToken':''}
    async def CancelTask(self,request,timeout=None): self.calls.append(('cancel',request)); return {'id':request['id'],'status':{'state':'TASK_STATE_CANCELED'}}
    async def CreateTaskPushNotificationConfig(self,request,timeout=None): self.calls.append(('push-create',request)); return {'id':'p1','taskId':request['taskId'],'url':request['url']}
    async def GetTaskPushNotificationConfig(self,request,timeout=None): self.calls.append(('push-get',request)); return {'id':request['id'],'taskId':request['taskId']}
    async def ListTaskPushNotificationConfigs(self,request,timeout=None): self.calls.append(('push-list',request)); return {'configs':[{'id':'p1'}]}
    async def DeleteTaskPushNotificationConfig(self,request,timeout=None): self.calls.append(('push-delete',request)); return {}

async def main():
    client=GrpcA2ALifecycleClient('127.0.0.1:65535',FakeStub,object(),timeout=1); client.codec=FakeCodec()
    message={'messageId':'m1','role':'ROLE_USER','parts':[{'text':'hello'}]}
    send=await client.send(message); events=[x async for x in client.stream(message)]; subscribed=[x async for x in client.subscribe('t2')]; task=await client.get_task('t1'); tasks=await client.list_tasks(pageSize=10); cancel=await client.cancel('t1')
    push=await client.set_push_config('t1',{'url':'https://receiver.example/a2a/push'}); push_get=await client.get_push_config('t1','p1'); push_list=await client.list_push_configs('t1'); push_delete=await client.delete_push_config('t1','p1'); await client.close()
    receiver=PushNotificationReceiver('secret'); body=b'{"taskId":"t1"}'; signature=hmac.new(b'secret',body,hashlib.sha256).hexdigest(); hmac_ok=receiver.verify(body,'sha256='+signature) and not receiver.verify(body,'sha256='+'00'*32)
    report={'send':bool(send),'stream_events':len(events),'subscribe_events':len(subscribed),'get':bool(task),'list':bool(tasks),'cancel':bool(cancel),'push_create':bool(push),'push_get':bool(push_get),'push_list':bool(push_list),'push_delete':push_delete=={},'receiver_hmac':hmac_ok,'grpc_operations':[x[0] for x in client.stub.calls]}
    report['passed']=all([report['send'],report['stream_events']>=2,report['subscribe_events']>=1,report['get'],report['list'],report['cancel'],report['push_create'],report['push_get'],report['push_list'],report['push_delete'],report['receiver_hmac']])
    pathlib.Path('protocol-depth-proof.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); return 0 if report['passed'] else 1

raise SystemExit(asyncio.run(main()))
