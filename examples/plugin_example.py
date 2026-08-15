"""Minimal AgentWeave plugin example.

A separately packaged plugin can expose this class under the
``agentweave.plugins`` Python entry-point group.
"""

class ExamplePlugin:
    name='example'
    def register(self,weave):
        weave.observability.audit.record('plugin.loaded',subject=self.name)
        return {'plugin':self.name,'registered':True}
