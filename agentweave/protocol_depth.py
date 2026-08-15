from __future__ import annotations
import asyncio, hashlib, hmac, json, time
from dataclasses import dataclass, field
from typing import AsyncIterator

class ProtobufCodec:
    """Codec for generated A2A protobuf modules."""
    def __init__(self,pb2):
        self.pb2=pb2
        from google.protobuf.json_format import MessageToDict,ParseDict
        self._to_dict=MessageToDict; self._parse=ParseDict
    def build(self,class_name,payload):
        cls=getattr(self.pb2,class_name); return self._parse(payload,cls(),ignore_unknown_fields=False)
    def to_dict(self,message): return self._to_dict(message,preserving_proto_field_name=False)

class GrpcA2ALifecycleClient:
    """A2A v1 lifecycle client over generated gRPC stub/protobuf classes.

    Covers SendMessage, SendStreamingMessage, GetTask, ListTasks, CancelTask,
    SubscribeToTask and task push-notification configuration operations.
    """
    def __init__(self,target,stub_cls,pb2,*,secure=False,credentials=None,timeout=120):
        try: import grpc
        except ImportError as exc: raise RuntimeError('Install agentweave[grpc]') from exc
        self.grpc=grpc; self.target=target; self.timeout=timeout; self.codec=ProtobufCodec(pb2)
        self.channel=grpc.aio.secure_channel(target,credentials or grpc.ssl_channel_credentials()) if secure else grpc.aio.insecure_channel(target)
        self.stub=stub_cls(self.channel)
    async def close(self): await self.channel.close()
    async def _unary(self,method,request_name,payload):
        response=await getattr(self.stub,method)(self.codec.build(request_name,payload),timeout=self.timeout); return self.codec.to_dict(response)
    async def send(self,message,configuration=None,metadata=None,tenant=None):
        payload={'message':message}
        if configuration is not None: payload['configuration']=configuration
        if metadata is not None: payload['metadata']=metadata
        if tenant: payload['tenant']=tenant
        return await self._unary('SendMessage','SendMessageRequest',payload)
    async def stream(self,message,configuration=None,metadata=None,tenant=None)->AsyncIterator[dict]:
        payload={'message':message}
        if configuration is not None: payload['configuration']=configuration
        if metadata is not None: payload['metadata']=metadata
        if tenant: payload['tenant']=tenant
        call=getattr(self.stub,'SendStreamingMessage')(self.codec.build('SendMessageRequest',payload),timeout=self.timeout)
        async for event in call: yield self.codec.to_dict(event)
    async def subscribe(self,task_id,tenant=None)->AsyncIterator[dict]:
        payload={'id':task_id}
        if tenant: payload['tenant']=tenant
        call=getattr(self.stub,'SubscribeToTask')(self.codec.build('SubscribeToTaskRequest',payload),timeout=self.timeout)
        async for event in call: yield self.codec.to_dict(event)
    async def get_task(self,task_id,history_length=None,tenant=None):
        payload={'id':task_id}
        if history_length is not None: payload['historyLength']=history_length
        if tenant: payload['tenant']=tenant
        return await self._unary('GetTask','GetTaskRequest',payload)
    async def list_tasks(self,**filters): return await self._unary('ListTasks','ListTasksRequest',filters)
    async def cancel(self,task_id,metadata=None,tenant=None):
        payload={'id':task_id}
        if metadata is not None: payload['metadata']=metadata
        if tenant: payload['tenant']=tenant
        return await self._unary('CancelTask','CancelTaskRequest',payload)
    async def set_push_config(self,task_id,config,tenant=None):
        payload={'taskId':task_id,**dict(config)}
        if tenant: payload['tenant']=tenant
        return await self._unary('CreateTaskPushNotificationConfig','TaskPushNotificationConfig',payload)
    async def get_push_config(self,task_id,config_id,tenant=None):
        payload={'taskId':task_id,'id':config_id}
        if tenant: payload['tenant']=tenant
        return await self._unary('GetTaskPushNotificationConfig','GetTaskPushNotificationConfigRequest',payload)
    async def list_push_configs(self,task_id,tenant=None,page_size=None,page_token=None):
        payload={'taskId':task_id}
        if tenant: payload['tenant']=tenant
        if page_size is not None: payload['pageSize']=page_size
        if page_token: payload['pageToken']=page_token
        return await self._unary('ListTaskPushNotificationConfigs','ListTaskPushNotificationConfigsRequest',payload)
    async def delete_push_config(self,task_id,config_id,tenant=None):
        payload={'taskId':task_id,'id':config_id}
        if tenant: payload['tenant']=tenant
        return await self._unary('DeleteTaskPushNotificationConfig','DeleteTaskPushNotificationConfigRequest',payload)

class PushNotificationConfigClient:
    """Push-notification configuration for JSON-RPC and HTTP+JSON bindings."""
    def __init__(self,timeout=30,protocol_version='1.0'): self.timeout=timeout; self.protocol_version=protocol_version
    def _interface(self,agent):
        card=agent.metadata.get('agent_card',{}); interfaces=card.get('supportedInterfaces') or []; iface=interfaces[0] if interfaces and isinstance(interfaces[0],dict) else {}
        endpoint=agent.execution.endpoint or iface.get('url') or card.get('url'); binding=str(agent.metadata.get('protocol_binding') or iface.get('protocolBinding') or 'JSONRPC').upper()
        if not endpoint: raise ValueError('agent endpoint missing')
        return endpoint.rstrip('/'),binding,iface.get('tenant')
    async def _rpc(self,endpoint,method,params):
        import httpx
        payload={'jsonrpc':'2.0','id':str(time.time_ns()),'method':method,'params':params}
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
            response=await client.post(endpoint,json=payload,headers={'Content-Type':'application/json','A2A-Version':self.protocol_version}); response.raise_for_status(); data=response.json()
        if 'error' in data: raise RuntimeError(str(data['error']))
        return data.get('result',data)
    async def set(self,agent,task_id,config):
        import httpx
        endpoint,binding,tenant=self._interface(agent); payload={'taskId':task_id,**dict(config)}
        if tenant: payload['tenant']=tenant
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.post(f'{endpoint}/tasks/{task_id}/pushNotificationConfigs',json=payload,headers={'Content-Type':'application/a2a+json','A2A-Version':self.protocol_version}); response.raise_for_status(); return response.json()
        return await self._rpc(endpoint,'CreateTaskPushNotificationConfig',payload)
    async def get(self,agent,task_id,config_id):
        import httpx
        endpoint,binding,tenant=self._interface(agent); payload={'taskId':task_id,'id':config_id}
        if tenant: payload['tenant']=tenant
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.get(f'{endpoint}/tasks/{task_id}/pushNotificationConfigs/{config_id}',headers={'A2A-Version':self.protocol_version}); response.raise_for_status(); return response.json()
        return await self._rpc(endpoint,'GetTaskPushNotificationConfig',payload)
    async def list(self,agent,task_id):
        import httpx
        endpoint,binding,tenant=self._interface(agent); payload={'taskId':task_id}
        if tenant: payload['tenant']=tenant
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.get(f'{endpoint}/tasks/{task_id}/pushNotificationConfigs',headers={'A2A-Version':self.protocol_version}); response.raise_for_status(); return response.json()
        return await self._rpc(endpoint,'ListTaskPushNotificationConfigs',payload)
    async def delete(self,agent,task_id,config_id):
        import httpx
        endpoint,binding,tenant=self._interface(agent); payload={'taskId':task_id,'id':config_id}
        if tenant: payload['tenant']=tenant
        if binding in {'HTTP+JSON','HTTP_JSON','REST'}:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response=await client.delete(f'{endpoint}/tasks/{task_id}/pushNotificationConfigs/{config_id}',headers={'A2A-Version':self.protocol_version}); response.raise_for_status(); return {'deleted':True,'status_code':response.status_code}
        return await self._rpc(endpoint,'DeleteTaskPushNotificationConfig',payload)

@dataclass
class PushEvent:
    payload: dict
    received_at: float=field(default_factory=time.time)
    signature_verified: bool=False

class PushNotificationReceiver:
    """ASGI webhook receiver with optional HMAC request authentication."""
    def __init__(self,secret=None,signature_header='x-agentweave-signature',max_body_bytes=1_048_576):
        self.secret=secret.encode() if secret else None; self.signature_header=signature_header.lower(); self.max_body_bytes=max_body_bytes; self.queue:asyncio.Queue[PushEvent]=asyncio.Queue()
    def verify(self,body,signature):
        if self.secret is None: return True
        if not signature: return False
        supplied=signature.split('=',1)[-1]; expected=hmac.new(self.secret,body,hashlib.sha256).hexdigest(); return hmac.compare_digest(expected,supplied)
    def app(self):
        try:
            from starlette.applications import Starlette
            from starlette.requests import Request
            from starlette.responses import JSONResponse
            from starlette.routing import Route
        except ImportError as exc: raise RuntimeError('Install agentweave[api]') from exc
        async def receive(request:Request):
            body=await request.body()
            if len(body)>self.max_body_bytes: return JSONResponse({'error':'payload-too-large'},status_code=413)
            verified=self.verify(body,request.headers.get(self.signature_header))
            if not verified: return JSONResponse({'error':'invalid-signature'},status_code=401)
            try: payload=json.loads(body or b'{}')
            except json.JSONDecodeError: return JSONResponse({'error':'invalid-json'},status_code=400)
            await self.queue.put(PushEvent(payload=payload,signature_verified=verified)); return JSONResponse({'accepted':True},status_code=202)
        return Starlette(routes=[Route('/a2a/push',receive,methods=['POST'])])
    async def next_event(self,timeout=30): return await asyncio.wait_for(self.queue.get(),timeout=timeout)
