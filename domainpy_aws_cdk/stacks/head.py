import os
import typing
import shutil
import tempfile

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python

from domainpy_aws_cdk.constructs.head import (
    Gateway,
    ApplicationCommandDefinition,
    IntegrationEventDefinition,
    MessageLake,
    TraceStore, 
    Publisher,
    Resolver
)


class MessageLakeStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.message_lake = MessageLake(self, 'messagelake')
        self.trace_store = TraceStore(self, 'tracestore')
    

class GatewayBusStack(cdk.Stack):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        messages: typing.Sequence[typing.Union[ApplicationCommandDefinition, IntegrationEventDefinition]],
        message_lake_stack: MessageLakeStack,
        share_prefix: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree('/Users/brianestrada/Offline/domainpy/domainpy', os.path.join(tmp, 'domainpy'), dirs_exist_ok=True)
            shutil.copyfile('/Users/brianestrada/Offline/domainpy/setup.py', os.path.join(tmp, 'setup.py'))

            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('aws-xray-sdk==2.8.0\n')
                file.write('typeguard==2.12.1\n')
                file.write('requests==2.26.0\n')

            domainpy_layer = lambda_python.PythonLayerVersion(self, 'domainpy',
                entry=tmp,
                compatible_runtimes=[
                    lambda_.Runtime.PYTHON_3_7,
                    lambda_.Runtime.PYTHON_3_8
                ]
            )

        gateway = Gateway(self, 'gateway', share_prefix=share_prefix)

        for message in messages:
            gateway.add_publisher(
                Publisher(self, message.topic,
                    message=message,
                    trace_store=message_lake_stack.trace_store,
                    share_prefix=share_prefix,
                    domainpy_layer=domainpy_layer
                )
            )
    
        Resolver(self, 'resolver',
            trace_store=message_lake_stack.trace_store,
            message_lake=message_lake_stack.message_lake,
            share_prefix=share_prefix,
            domainpy_layer=domainpy_layer
        )