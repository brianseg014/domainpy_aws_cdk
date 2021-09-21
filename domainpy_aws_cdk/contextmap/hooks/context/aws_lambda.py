
from aws_cdk import core as cdk

from domainpy_aws_cdk.contextmap.base import IContextMap, IContextHook
from domainpy_aws_cdk.contextmap.aws_lambda import LambdaContextMapBase
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase


class LambdaContextHook(IContextHook):

    def __init__(
        self,
        context: LambdaContextBase
    ) -> None:
        self.context = context

    def bind(self, context_map: IContextMap):
        if isinstance(context_map, LambdaContextMapBase):
            self._bind_lambda_context_map(context_map)
        else:
            cdk.ValidationError('contextmap-context incompatible')

    def _bind_lambda_context_map(self, context_map: LambdaContextMapBase):
        context_queue = self.context.queue
        context_map_microservice = context_map.microservice

        context_map_microservice.add_environment('CONTEXT_QUEUE_URL', context_queue.queue_url)
        context_queue.grant_send_messages(context_map_microservice)
